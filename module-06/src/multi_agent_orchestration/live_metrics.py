"""Explicit finalized live operational metrics; no inference or automatic I/O."""

import asyncio
import os
import threading
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import model_validator

from .canonical_contracts import EvidenceSource
from .contracts import GraphTopology, RuntimeId
from .live_contracts import CanonicalUUID, LiveContract
from .live_errors import LiveValidationError
from .live_observation import (
    Calls,
    Duration,
    LiveTerminalObservation,
    Repairs,
    checked_observation,
)
from .observability import Observability
from .observability_contracts import MetricLabels, Outcome
from .telemetry_delivery import DURATION_BUCKETS_MS, LABEL_KEYS

MAX_OBSERVATIONS = 32
MAX_BATCH_BYTES = 65536
NAMESPACES = {
    EvidenceSource.SYNTHETIC_OFFLINE: "module6.live.synthetic",
    EvidenceSource.LOCAL_PROVIDER_EXECUTION: "module6.live.local",
}


class LiveMetricObservation(LiveContract):
    """Narrow live sibling, never coerced into deterministic zero-call accounting.

    UUID is local replay bookkeeping only. It never enters SDK attributes.
    None means unknown, including when other runs in an aggregate are known.
    """

    trace_id: CanonicalUUID
    evidence_source: EvidenceSource
    outcome: Outcome
    duration_ms: Duration
    model_calls: Calls | None
    repair_attempts: Repairs | None

    @model_validator(mode="after")
    def paired(self) -> "LiveMetricObservation":
        """Require a nonzero trace and paired call/repair availability."""
        if self.trace_id.int == 0 or (
            (self.model_calls is None) != (self.repair_attempts is None)
        ):
            raise ValueError("Live metric accounting must be paired.")
        return self


def project_metric_observation(
    terminal: LiveTerminalObservation,
) -> LiveMetricObservation:
    """Revalidate and minimize a terminal observation without SDK or transport.

    Args:
        terminal: Exact finalized application contract, not execution authority.

    Returns:
        Immutable fields needed for the five bounded operational instruments.

    Raises:
        LiveValidationError: Unowned, malformed or bypass-constructed data.
    """
    result = None
    try:
        if type(terminal) is not LiveTerminalObservation:
            raise ValueError
        checked = checked_observation(LiveTerminalObservation, terminal)
        checked = LiveTerminalObservation.model_validate_json(checked.model_dump_json())
        result = LiveMetricObservation(
            trace_id=checked.trace_id,
            evidence_source=checked.evidence_source,
            outcome=checked.outcome,
            duration_ms=checked.duration_ms,
            model_calls=checked.facts.model_calls,
            repair_attempts=checked.facts.repair_attempts,
        )
    except (Exception, asyncio.CancelledError):
        pass
    if result is None:
        raise LiveValidationError() from None
    return result


@dataclass(frozen=True)
class LiveMetricResult:
    """Collection diagnostics, never workflow or delivery evidence."""

    status: Literal["recorded", "refused", "failed"]
    failure: (
        Literal[
            "invalid_observation",
            "busy",
            "closed",
            "sealed",
            "already_attempted",
            "capacity_spent",
            "sdk_disabled",
            "sdk_unavailable",
            "collection_failed",
        ]
        | None
    ) = None
    trace_id: UUID | None = None
    evidence_class: Literal["local_sdk_metrics"] = "local_sdk_metrics"


def sdk_disabled() -> bool:
    """Read only the SDK disable flag, never exporter or credential settings."""
    return os.environ.get("OTEL_SDK_DISABLED", "").strip().lower() == "true"


class LiveOperationalMetrics:
    """One bounded local cumulative window, explicitly sealed by delivery.

    Trusted operator code owns this object. Construction performs no SDK setup,
    environment-enabled export, background work, or execution. At most 32 terminal
    attempts, ten closed dimension groups and fifty SDK points per window.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._attempted: set[UUID] = set()
        self._closed = self._sealed = False
        self._damaged = False
        self._provider = self._reader = None
        self._instruments = {}

    def _initialize(self) -> None:
        from opentelemetry.sdk.metrics import AlwaysOffExemplarFilter, MeterProvider
        from opentelemetry.sdk.metrics.export import InMemoryMetricReader
        from opentelemetry.sdk.metrics.view import (
            ExplicitBucketHistogramAggregation,
            View,
        )
        from opentelemetry.sdk.resources import Resource

        reader = InMemoryMetricReader()
        provider = MeterProvider(
            metric_readers=(reader,),
            resource=Resource({"service.name": "module6-live"}),
            shutdown_on_exit=False,
            exemplar_filter=AlwaysOffExemplarFilter(),
            views=tuple(
                View(
                    instrument_name=f"{prefix}.workflow.duration",
                    attribute_keys=set(LABEL_KEYS),
                    aggregation=ExplicitBucketHistogramAggregation(
                        boundaries=DURATION_BUCKETS_MS, record_min_max=False
                    ),
                )
                for prefix in NAMESPACES.values()
            ),
        )
        meter = provider.get_meter("module6.live.observability")
        instruments = {}
        for source, prefix in NAMESPACES.items():
            instruments[source] = (
                meter.create_counter(f"{prefix}.workflow.finished", unit="1"),
                meter.create_histogram(f"{prefix}.workflow.duration", unit="ms"),
                meter.create_counter(f"{prefix}.accounting.observed", unit="1"),
                meter.create_counter(f"{prefix}.model.calls", unit="1"),
                meter.create_counter(f"{prefix}.workflow.repair_attempts", unit="1"),
            )
        self._reader, self._provider, self._instruments = reader, provider, instruments

    def record(self, observer: Observability, trace_id: UUID) -> LiveMetricResult:
        """Collect one retained terminal after workflow return, without I/O.

        Args:
            observer: Exact application-owned observation retention.
            trace_id: Trusted UUID selecting a finalized retained observation.

        Returns:
            Sanitized collection result. Failed attempts may leave partial metrics
            and remain spent; they never trigger execution or collection retry.
        """
        if not self._lock.acquire(blocking=False):
            return LiveMetricResult("refused", "busy")
        try:
            if self._closed or self._sealed:
                return LiveMetricResult(
                    "refused", "closed" if self._closed else "sealed"
                )
            if sdk_disabled():
                return LiveMetricResult("refused", "sdk_disabled")
            if type(observer) is not Observability or type(trace_id) is not UUID:
                return LiveMetricResult("refused", "invalid_observation")
            if not observer._lock.acquire(blocking=False):
                return LiveMetricResult("refused", "busy")
            try:
                try:
                    terminal = next(
                        item
                        for item in observer.live_terminal_records
                        if item.trace_id == trace_id
                    )
                finally:
                    observer._lock.release()
                point = project_metric_observation(terminal)
            except (Exception, asyncio.CancelledError):
                return LiveMetricResult("refused", "invalid_observation")
            if trace_id in self._attempted:
                return LiveMetricResult("refused", "already_attempted", trace_id)
            if len(self._attempted) >= MAX_OBSERVATIONS:
                return LiveMetricResult("refused", "capacity_spent", trace_id)
            if self._damaged:
                return LiveMetricResult("refused", "collection_failed", trace_id)
            try:
                if self._provider is None:
                    self._initialize()
            except ImportError:
                return LiveMetricResult("failed", "sdk_unavailable", trace_id)
            except (Exception, asyncio.CancelledError):
                self._damaged = True
                return LiveMetricResult("failed", "collection_failed", trace_id)
            self._attempted.add(trace_id)
            try:
                labels = MetricLabels(
                    runtime=RuntimeId.LANGGRAPH,
                    topology=GraphTopology.SEQUENTIAL,
                    distributed=False,
                    outcome=point.outcome,
                ).model_dump(mode="json")
                finished, duration, observed, calls, repairs = self._instruments[
                    point.evidence_source
                ]
                finished.add(1, labels)
                duration.record(point.duration_ms, labels)
                if point.model_calls is not None:
                    observed.add(1, labels)
                    calls.add(point.model_calls, labels)
                    repairs.add(point.repair_attempts, labels)
                return LiveMetricResult("recorded", trace_id=trace_id)
            except (Exception, asyncio.CancelledError):
                self._damaged = True
                return LiveMetricResult("failed", "collection_failed", trace_id)
        finally:
            self._lock.release()

    def _batch(self) -> bytes:
        from opentelemetry.exporter.otlp.proto.common.metrics_encoder import (
            encode_metrics,
        )

        data = self._reader.get_metrics_data() if self._reader is not None else None
        if data is None:
            return b""
        packet = encode_metrics(data)
        # SDK 1.42.1 encodes disabled min/max as +/-inf optional protobuf fields.
        # Omit these unavailable measures instead of exporting sentinel values.
        for resource in packet.resource_metrics:
            for scope in resource.scope_metrics:
                for metric in scope.metrics:
                    if metric.HasField("histogram"):
                        for point in metric.histogram.data_points:
                            point.ClearField("min")
                            point.ClearField("max")
        batch = packet.SerializeToString()
        if len(batch) > MAX_BATCH_BYTES:
            raise ValueError("Metric batch exceeds bound.")
        return batch

    def close(self) -> bool:
        """Close local SDK state without exporting or waiting for network work.

        Returns:
            False on contention, otherwise True. Repeated close is harmless.
            An already admitted delivery owns its frozen batch independently.
        """
        if not self._lock.acquire(blocking=False):
            return False
        try:
            if not self._closed:
                self._closed = True
                if self._provider is not None:
                    self._provider.shutdown()
            return True
        finally:
            self._lock.release()
