"""Explicit operator-selected OTLP metric delivery to a loopback collection boundary.

Nothing here runs by default. The accepted offline ``LocalOpenTelemetry`` adapter
is unchanged; delivery exists only when trusted operator code constructs
``OtlpMetricDelivery`` from a validated ``DeliveryConfig``. Workflow requests,
runtime output, credentials and environment variables cannot select delivery or
choose its destination.
"""

import math
import re
import threading
from os import environ
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from .contracts import Contract
from .observability_adapters import checked_trace
from .observability_contracts import Count, MetricLabels, MetricSnapshot, RunTrace

CEILING = 1_000_000_000
DURATION_BUCKETS_MS = (1, 10, 100, 1000, 10000, 30000)
LABEL_KEYS = frozenset({"runtime", "topology", "distributed", "outcome"})
DASHBOARD_UID = "module6-operations"
_ENDPOINT = re.compile(r"^http://127\.0\.0\.1:([1-9][0-9]{3,4})/v1/metrics$")
_REFERENCE = re.compile(rf"^http://127\.0\.0\.1:([1-9][0-9]{{3,4}})/d/{DASHBOARD_UID}$")


class TelemetryDeliveryError(ValueError):
    """Delivery selection or a curated telemetry value failed validation."""


def _loopback_port(pattern: re.Pattern[str], value: object) -> int:
    match = pattern.fullmatch(value) if type(value) is str else None
    if match is None or not 1024 <= int(match.group(1)) <= 65535:
        raise ValueError("Only the fixed loopback form is permitted.")
    return int(match.group(1))


class DeliveryConfig(Contract):
    """Operator-owned delivery selection; never part of workflow or runtime data.

    Attributes:
        mode: Required explicit selection. There is no default and no
            environment variable that supplies it.
        endpoint: Plain-HTTP OTLP metrics URL on ``127.0.0.1`` with an
            unprivileged port and the fixed ``/v1/metrics`` path.
        export_interval_ms: Period between cumulative metric exports.
        export_timeout_ms: Total budget for one export including SDK retries.
    """

    # A rejected destination may embed a secret; never echo it in errors.
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    mode: Literal["loopback-otlp-http"]
    endpoint: Annotated[str, Field(strict=True, max_length=40)]
    export_interval_ms: Annotated[int, Field(strict=True, ge=1000, le=60000)] = 5000
    export_timeout_ms: Annotated[int, Field(strict=True, ge=100, le=5000)] = 2000

    @model_validator(mode="after")
    def bounded_loopback(self):
        _loopback_port(_ENDPOINT, self.endpoint)
        if self.export_timeout_ms >= self.export_interval_ms:
            raise ValueError("Export timeout must be shorter than the interval.")
        return self


class DeliveryStatus(Contract):
    """Payload-free delivery health; never authority, evidence or a result."""

    exports_succeeded: Count
    exports_failed: Count
    last_export: Literal["none", "succeeded", "failed"]


class OtlpMetricDelivery:
    """Observation adapter that exports bounded workflow metrics over OTLP/HTTP.

    A private ``MeterProvider`` aggregates the same closed-dimension instruments
    as the offline adapter and a periodic reader exports cumulative state. There
    is no queue: a failed export is dropped and the next interval resends current
    totals, so an unavailable collector cannot cause a backlog or retry storm.
    Each export is bounded by ``export_timeout_ms``. No spans, identifiers, task
    content or exception text are exported. Bind one instance to one
    ``Observability`` for the life of the process and call ``close``.

    Args:
        config: A validated ``DeliveryConfig`` instance built by operator code.

    Raises:
        TelemetryDeliveryError: If the configuration is not an owned, valid
            ``DeliveryConfig`` or the OpenTelemetry SDK is disabled.
    """

    def __init__(self, config: DeliveryConfig):
        if type(config) is not DeliveryConfig or set(config.__dict__) != set(
            DeliveryConfig.model_fields
        ):
            raise TelemetryDeliveryError("Delivery requires an operator configuration.")
        try:
            config = DeliveryConfig.model_validate(dict(config.__dict__))
        except ValueError as exc:
            raise TelemetryDeliveryError("Delivery configuration is invalid.") from exc
        if environ.get("OTEL_SDK_DISABLED", "").strip().lower() == "true":
            raise TelemetryDeliveryError("The OpenTelemetry SDK is disabled.")

        import requests
        from opentelemetry.exporter.otlp.proto.http import Compression
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter,
        )
        from opentelemetry.sdk.metrics import AlwaysOffExemplarFilter, MeterProvider
        from opentelemetry.sdk.metrics.export import (
            MetricExporter,
            MetricExportResult,
            PeriodicExportingMetricReader,
        )
        from opentelemetry.sdk.metrics.view import (
            ExplicitBucketHistogramAggregation,
            View,
        )
        from opentelemetry.sdk.resources import Resource

        self.config = config
        self._lock = threading.RLock()
        self._succeeded = self._failed = 0
        self._last: Literal["none", "succeeded", "failed"] = "none"
        self._last_state = (0, 0, 0, 0)
        self._closed = False
        delivery, timeout_ms = self, config.export_timeout_ms

        # Explicit arguments stop the SDK reading endpoint, header, credential,
        # proxy or certificate settings from the environment.
        session = requests.Session()
        session.trust_env = False
        exporter = OTLPMetricExporter(
            endpoint=config.endpoint,
            headers={"X-Module6-Delivery": config.mode},
            timeout=timeout_ms / 1000,
            compression=Compression.NoCompression,
            session=session,
        )

        class Guarded(MetricExporter):
            """Count outcomes and keep exporter faults inside the telemetry path."""

            def export(self, metrics_data, timeout_millis=timeout_ms, **kwargs):
                try:
                    ok = (
                        exporter.export(metrics_data, timeout_millis=timeout_ms)
                        is MetricExportResult.SUCCESS
                    )
                except Exception:
                    ok = False  # Counted below; never propagated to execution.
                delivery._record(ok)
                return MetricExportResult.SUCCESS if ok else MetricExportResult.FAILURE

            def force_flush(self, timeout_millis=timeout_ms):
                return True

            def shutdown(self, timeout_millis=timeout_ms, **kwargs):
                exporter.shutdown(timeout_millis=timeout_ms)

        self._reader = PeriodicExportingMetricReader(
            Guarded(),
            export_interval_millis=config.export_interval_ms,
            export_timeout_millis=timeout_ms,
        )
        self._meters = MeterProvider(
            metric_readers=(self._reader,),
            resource=Resource({"service.name": "module6"}),
            shutdown_on_exit=False,
            exemplar_filter=AlwaysOffExemplarFilter(),
            views=(
                View(
                    instrument_name="module6.workflow.duration",
                    attribute_keys=set(LABEL_KEYS),
                    aggregation=ExplicitBucketHistogramAggregation(
                        boundaries=DURATION_BUCKETS_MS, record_min_max=False
                    ),
                ),
            ),
        )
        meter = self._meters.get_meter("module6.observability")
        self._runs = meter.create_counter("module6.workflow.finished", unit="1")
        self._duration = meter.create_histogram("module6.workflow.duration", unit="ms")
        self._models = meter.create_counter("module6.model.calls", unit="1")
        self._retries = meter.create_counter("module6.workflow.retries", unit="1")
        self._workers = meter.create_counter("module6.worker.reaped", unit="1")
        self._active = meter.create_up_down_counter("module6.workflow.active", unit="1")
        self._started = meter.create_counter("module6.workflow.started", unit="1")
        self._drops = meter.create_counter("module6.observation.drops", unit="1")
        self._adapter_failures = meter.create_counter(
            "module6.observation.adapter_failures", unit="1"
        )

    def _record(self, ok: bool) -> None:
        with self._lock:
            if ok:
                self._succeeded = min(CEILING, self._succeeded + 1)
            else:
                self._failed = min(CEILING, self._failed + 1)
            self._last = "succeeded" if ok else "failed"

    def state(self, snapshot: MetricSnapshot) -> None:
        """Record lifecycle and observation-loss deltas from one observer."""
        snapshot = MetricSnapshot.model_validate(snapshot.model_dump())
        with self._lock:
            active, started, drops, failures = self._last_state
            self._active.add(snapshot.active - active)
            if snapshot.started > started:
                self._started.add(snapshot.started - started)
            if snapshot.observation_drops > drops:
                self._drops.add(snapshot.observation_drops - drops)
            if snapshot.adapter_failures > failures:
                self._adapter_failures.add(snapshot.adapter_failures - failures)
            self._last_state = (
                snapshot.active,
                snapshot.started,
                snapshot.observation_drops,
                snapshot.adapter_failures,
            )

    def emit(self, trace: RunTrace) -> None:
        """Aggregate one validated run; only the four closed labels are used."""
        trace = checked_trace(trace)
        labels = MetricLabels(
            runtime=trace.runtime,
            topology=trace.topology,
            distributed=trace.distributed,
            outcome=trace.outcome,
        ).model_dump(mode="json")
        with self._lock:
            self._runs.add(1, labels)
            self._duration.record(trace.duration_ms, labels)
            # None means unobserved and is never exported as zero.
            if trace.accounting.model_calls is not None:
                self._models.add(trace.accounting.model_calls, labels)
            if trace.accounting.retries is not None:
                self._retries.add(trace.accounting.retries, labels)
            if trace.workers_reaped is not None:
                self._workers.add(trace.workers_reaped, labels)

    def flush(self) -> bool:
        """Export current totals once, bounded by the configured timeout.

        Returns:
            True when the collection boundary accepted this export.
        """
        with self._lock:
            before = self._succeeded
        try:
            self._meters.force_flush(timeout_millis=self.config.export_timeout_ms)
        except Exception:
            return False  # Delivery health is reported through ``status``.
        with self._lock:
            return self._succeeded > before

    @property
    def status(self) -> DeliveryStatus:
        """Bounded payload-free export counts for operator display."""
        with self._lock:
            return DeliveryStatus(
                exports_succeeded=self._succeeded,
                exports_failed=self._failed,
                last_export=self._last,
            )

    def close(self) -> None:
        """Stop the export thread after one final bounded export attempt."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._meters.shutdown(timeout_millis=self.config.export_timeout_ms)


def grafana_reference(candidate: object) -> str:
    """Validate a local Grafana dashboard reference before it is displayed.

    Args:
        candidate: Untrusted reference text.

    Returns:
        The unchanged reference when it is exactly the provisioned dashboard on
        ``127.0.0.1`` with an unprivileged port, no query, fragment or userinfo.

    Raises:
        TelemetryDeliveryError: For any other value.
    """
    try:
        _loopback_port(_REFERENCE, candidate)
    except ValueError as exc:
        raise TelemetryDeliveryError("Grafana reference is not permitted.") from exc
    return str(candidate)


def prometheus_scalar(payload: object) -> float | None:
    """Curate one unlabelled instant-query value from an untrusted response.

    Args:
        payload: Decoded JSON from a Prometheus-compatible instant query.

    Returns:
        A finite non-negative number, or ``None`` when the series is absent.
        Absent is reported as unavailable, never as zero.

    Raises:
        TelemetryDeliveryError: If the response is not a successful vector of
            at most one label-free sample.
    """
    try:
        if type(payload) is not dict or payload.get("status") != "success":
            raise ValueError
        data = payload["data"]
        if data["resultType"] != "vector" or type(data["result"]) is not list:
            raise ValueError
        if not data["result"]:
            return None
        (sample,) = data["result"]
        if sample["metric"] != {} or type(sample["value"][1]) is not str:
            raise ValueError
        value = float(sample["value"][1])
        if not math.isfinite(value) or not 0 <= value <= 1e12:
            raise ValueError
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        raise TelemetryDeliveryError("Metric response failed validation.") from exc
    return value


def grafana_scalar(payload: object) -> float | None:
    """Curate one unlabelled instant value from an untrusted Grafana query reply.

    Args:
        payload: Decoded JSON from Grafana's data source query API for one
            query with reference ``A``.

    Returns:
        A finite non-negative number, or ``None`` when the series is absent.

    Raises:
        TelemetryDeliveryError: If the reply is not one successful frame holding
            at most one label-free numeric sample.
    """
    try:
        if type(payload) is not dict:
            raise ValueError
        result = payload["results"]["A"]
        (frame,) = result["frames"]
        if result["status"] != 200:
            raise ValueError
        values = frame["data"]["values"]
        if values == []:
            return None
        (_, (value,)) = values
        (_, field) = frame["schema"]["fields"]
        if field.get("labels", {}) != {} or type(value) not in (int, float):
            raise ValueError
        if not math.isfinite(value) or not 0 <= value <= 1e12:
            raise ValueError
    except (ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
        raise TelemetryDeliveryError("Metric response failed validation.") from exc
    return float(value)
