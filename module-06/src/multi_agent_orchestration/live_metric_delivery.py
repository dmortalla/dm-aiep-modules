"""Explicit one-shot OTLP/HTTP live metric delivery to operator-owned loopback.

Uses the installed SDK encoder, not its retrying HTTP exporter. No imports,
credentials or environment exporter settings can activate delivery.
"""

import asyncio
import threading
import time
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .live_contracts import LiveContract
from .live_metrics import MAX_BATCH_BYTES, LiveOperationalMetrics, sdk_disabled
from .telemetry_delivery import DeliveryConfig

MAX_RESPONSE_BYTES = 1024
_SLOTS = threading.BoundedSemaphore(3)
WriteOutcome = Literal["accepted", "partial", "export_failed", "invalid_response"]


class LiveMetricDeliveryConfig(LiveContract):
    """Explicit trusted selection; uses the established fixed loopback endpoint.

    No defaults for mode/destination. Timeout bounds whole application waiting,
    including DNS, response disposal and shutdown, not merely socket operations.
    """

    mode: Literal["loopback-otlp-http"]
    endpoint: Annotated[str, Field(strict=True, max_length=40)]
    timeout_ms: Annotated[int, Field(strict=True, ge=100, le=5000)] = 2000

    @model_validator(mode="after")
    def loopback(self):
        DeliveryConfig(
            mode=self.mode,
            endpoint=self.endpoint,
            export_timeout_ms=self.timeout_ms,
            export_interval_ms=60000,
        )
        return self


@dataclass(frozen=True)
class LiveMetricDeliveryResult:
    """Protocol acknowledgement only, never storage, query or workflow proof."""

    status: Literal["accepted", "failed", "refused"]
    failure: (
        Literal[
            "invalid_config",
            "invalid_collection",
            "busy",
            "closed",
            "already_attempted",
            "sdk_disabled",
            "sdk_unavailable",
            "no_data",
            "collection_failed",
            "capacity_spent",
            "timed_out",
            "export_failed",
            "invalid_response",
            "partial",
        ]
        | None
    ) = None
    attempts: int = 0
    evidence_class: Literal["otlp_write_unverified"] = "otlp_write_unverified"


def _send_once(batch: bytes, config: LiveMetricDeliveryConfig) -> WriteOutcome:
    """One no-retry, no-redirect request; bounded protocol reply, no diagnostics."""
    import requests
    from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
        ExportMetricsServiceResponse,
    )

    class NoRedirectSession(requests.Session):
        def resolve_redirects(self, *args, **kwargs):
            # Requests 2.34.2 calls this even with allow_redirects=False to
            # prepare Response.next. Its resolver consumes resp.content BEFORE
            # checking max_redirects. Never enter that body-consuming path.
            return iter(())

    with NoRedirectSession() as session:
        session.trust_env = False
        session.max_redirects = 0
        # Default adapters have max_retries=0. No auth, netrc, proxy or TLS lookup.
        with session.post(
            config.endpoint,
            data=batch,
            headers={
                "Content-Type": "application/x-protobuf",
                "Accept-Encoding": "identity",
            },
            timeout=config.timeout_ms / 1000,
            allow_redirects=False,
            stream=True,
        ) as reply:
            if not 200 <= reply.status_code <= 299:
                return "export_failed"
            # Adapter.send has preload_content=False and decode_content=False.
            # Read only the cap plus one overflow probe byte; do not invoke
            # Requests' content buffering or automatic decompression pipeline.
            body = reply.raw.read(MAX_RESPONSE_BYTES + 1, decode_content=False)
            if len(body) > MAX_RESPONSE_BYTES:
                return "invalid_response"
            response = ExportMetricsServiceResponse()
            try:
                response.ParseFromString(body)
            except Exception:
                return "invalid_response"
            if (
                response.partial_success.rejected_data_points
                or response.partial_success.error_message
            ):
                return "partial"
            return "accepted"


def _bounded_send(batch: bytes, config: LiveMetricDeliveryConfig) -> str:
    """Bound waiting and surviving I/O globally, with no pending queue.

    Arbitrarily blocked Python I/O cannot safely be cancelled. A timed-out worker
    keeps its permit until actual exit; late results cannot mutate collection or
    the returned result. The originally authorized write may still finish late.
    """
    deadline = time.monotonic() + config.timeout_ms / 1000
    if not _SLOTS.acquire(blocking=False):
        return "capacity_spent"
    done = threading.Event()
    cell = ["export_failed"]

    def execute():
        try:
            result = _send_once(batch, config)
            if type(result) is str and result in (
                "accepted",
                "partial",
                "export_failed",
                "invalid_response",
            ):
                cell[0] = result
        except BaseException:
            pass  # No arbitrary exception or transport object escapes the worker.
        finally:
            _SLOTS.release()
            done.set()

    worker = threading.Thread(target=execute, name="module6-live-metrics", daemon=True)
    try:
        worker.start()
    except BaseException:
        _SLOTS.release()
        return "export_failed"
    if (
        not done.wait(max(0.0, deadline - time.monotonic()))
        or time.monotonic() >= deadline
    ):
        return "timed_out"
    return cell[0]


def deliver_live_metrics(
    metrics: LiveOperationalMetrics, config: LiveMetricDeliveryConfig
) -> LiveMetricDeliveryResult:
    """Seal one local cumulative window and claim its only delivery attempt.

    Args:
        metrics: Exact application-owned live collection, separate from execution.
        config: Exact validated operator config; arbitrary mappings/subclasses refuse.

    Returns:
        Payload-free one-shot delivery result. Accepted means only OTLP protocol
        acknowledgement; partial, timeout and failure never authorize a retry.
        No SDK/Collector/storage/production acceptance is implied.
    """
    try:
        if type(config) is not LiveMetricDeliveryConfig or set(config.__dict__) != set(
            LiveMetricDeliveryConfig.model_fields
        ):
            raise ValueError
        config = LiveMetricDeliveryConfig.model_validate(dict(config.__dict__))
        config = LiveMetricDeliveryConfig.model_validate_json(config.model_dump_json())
    except (Exception, asyncio.CancelledError):
        return LiveMetricDeliveryResult("refused", "invalid_config")
    if type(metrics) is not LiveOperationalMetrics:
        return LiveMetricDeliveryResult("refused", "invalid_collection")
    if not metrics._lock.acquire(blocking=False):
        return LiveMetricDeliveryResult("refused", "busy")
    try:
        if metrics._closed:
            return LiveMetricDeliveryResult("refused", "closed")
        if metrics._sealed:
            return LiveMetricDeliveryResult("refused", "already_attempted")
        if sdk_disabled():
            return LiveMetricDeliveryResult("refused", "sdk_disabled")
        if metrics._damaged:
            return LiveMetricDeliveryResult("failed", "collection_failed")
        try:
            batch = metrics._batch()
            if type(batch) is not bytes or len(batch) > MAX_BATCH_BYTES:
                raise ValueError
        except ImportError:
            return LiveMetricDeliveryResult("failed", "sdk_unavailable")
        except (Exception, asyncio.CancelledError):
            return LiveMetricDeliveryResult("failed", "collection_failed")
        if not batch:
            return LiveMetricDeliveryResult("refused", "no_data")
        metrics._sealed = True  # Irreversible before admission or any I/O.
    finally:
        metrics._lock.release()
    try:
        result = _bounded_send(batch, config)
    except (Exception, asyncio.CancelledError):
        result = "export_failed"
    return LiveMetricDeliveryResult(
        "accepted" if result == "accepted" else "failed",
        None if result == "accepted" else result,
        1,
    )
