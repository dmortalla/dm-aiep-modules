"""Local-only SDK adapters; no client, remote exporter, endpoint or background IO."""

import asyncio
import threading
from collections import deque
from contextvars import ContextVar
from datetime import UTC, datetime
from importlib import import_module
from typing import TYPE_CHECKING
from uuid import UUID

from .observability_contracts import (
    Accounting,
    MetricLabels,
    MetricSnapshot,
    RunTrace,
    StepTrace,
)

if TYPE_CHECKING:
    from opentelemetry.sdk.metrics.export import MetricsData


def checked_trace(trace: RunTrace) -> RunTrace:
    """Rebuild a trace from its exact declared fields before any SDK use.

    Args:
        trace: A retained trace, untrusted until rebuilt.

    Returns:
        A freshly validated trace.

    Raises:
        ValueError: Unowned fields or types, more than three steps, or a
            validation failure.
    """
    # Inspect closed fields before any SDK/Pydantic serialization can warn with
    # rejected values. Revalidate nested objects from plain data, not instances.
    def fields(record, schema):
        if type(record) is not schema or set(record.__dict__) != set(
            schema.model_fields
        ):
            raise ValueError("Observation contains unowned fields or types.")
        return dict(record.__dict__)

    raw = fields(trace, RunTrace)
    if type(trace.steps) is not tuple or len(trace.steps) > 3:
        raise ValueError("Observation exceeds the closed completion bound.")
    raw["steps"] = tuple(fields(step, StepTrace) for step in trace.steps)
    raw["accounting"] = fields(trace.accounting, Accounting)
    return RunTrace.model_validate(raw)


def timestamp(nanoseconds: int) -> datetime:
    """Convert a wall-clock nanosecond marker to an aware UTC datetime."""
    return datetime.fromtimestamp(nanoseconds / 1_000_000_000, UTC)


class LocalLangSmith:
    """Actual RunTree construction/end/child APIs; never post/patch/client/URL.

    Fixed project and empty inputs/outputs, no environment-enabled transport.
    At most 32 trees with at most three completion-provenance child runs each.
    Read-only application traces are the public view, SDK objects stay private.
    """

    def __init__(self):
        self._trees = deque(maxlen=32)
        self._lock = threading.Lock()

    def emit(self, trace: RunTrace) -> None:
        """Build one local RunTree with payload-free metadata; never sent.

        Raises:
            ValueError: The trace failed revalidation.
        """
        # Match the repository's lazy SDK boundary; no domain-level SDK import.
        RunTree = import_module("langsmith.run_trees").RunTree

        trace = checked_trace(trace)
        metadata = {
            "workflow_id": str(trace.workflow_id),
            "task_id": str(trace.task_id),
            "runtime": trace.runtime.value,
            "otel_trace_id": trace.trace_id.hex,
            "otel_span_id": trace.span_id,
            "outcome": trace.outcome.value,
            "evidence_class": "offline_validated_completion",
        }
        tree = RunTree(
            id=trace.trace_id,
            trace_id=trace.trace_id,
            name="module6.workflow",
            run_type="chain",
            project_name="module6-offline",
            inputs={},
            outputs={},
            extra={"metadata": metadata},
            start_time=timestamp(trace.started_ns),
            replicas=[],
            tags=[],
            attachments={},
        )
        for step in trace.steps:
            child = tree.create_child(
                name=step.role.value,
                run_type="chain",
                run_id=UUID(int=int(step.span_id, 16)),
                inputs={},
                outputs={},
                start_time=timestamp(trace.ended_ns),
                extra={
                    "metadata": {
                        "otel_span_id": step.span_id,
                        "observation": "validated_completion",
                    }
                },
            )
            child.end(end_time=timestamp(trace.ended_ns))
        tree.end(
            end_time=timestamp(trace.ended_ns),
            error=None if trace.outcome.value == "completed" else trace.outcome.value,
        )
        with self._lock:
            self._trees.append(tree)

    def state(self, snapshot: MetricSnapshot) -> None:
        """Ignore operational aggregates, which LangSmith does not own."""


class LocalOpenTelemetry:
    """Private SDK providers and bounded in-memory collection, never global state.

    OTEL_SDK_DISABLED is respected. No periodic reader/batch processor, remote
    exporter, environment endpoint, auto resource detector or exception capture.
    Metric dimensions are closed and trace IDs are excluded from exemplars.
    """

    def __init__(self):
        from opentelemetry.metrics import NoOpMeterProvider
        from opentelemetry.sdk.metrics import AlwaysOffExemplarFilter, MeterProvider
        from opentelemetry.sdk.metrics.export import InMemoryMetricReader
        from opentelemetry.sdk.metrics.view import (
            ExplicitBucketHistogramAggregation,
            View,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import SpanLimits, TracerProvider
        from opentelemetry.sdk.trace.export import (
            SimpleSpanProcessor,
            SpanExporter,
            SpanExportResult,
        )
        from opentelemetry.sdk.trace.id_generator import IdGenerator
        from opentelemetry.sdk.trace.sampling import ALWAYS_ON

        self._spans = deque(maxlen=128)
        self._collection_failures = 0
        self._collection_failure_marker = None
        self._identity = ContextVar("module6_local_span_identity")
        self._lock = threading.RLock()
        self._live_attempted = set()
        self._closed = False
        identity, adapter = self._identity, self

        class ApplicationIds(IdGenerator):
            def generate_span_id(self):
                return identity.get()[1]

            def generate_trace_id(self):
                return identity.get()[0]

        class BoundedCollection(SpanExporter):
            def export(self, batch):
                try:
                    adapter._retain_spans(batch)
                except (Exception, asyncio.CancelledError):
                    adapter._collection_failure_marker = object()
                    adapter._collection_failures = min(
                        1_000_000_000, adapter._collection_failures + 1
                    )
                    return SpanExportResult.FAILURE
                return SpanExportResult.SUCCESS

            def shutdown(self):
                pass

        resource = Resource({"service.name": "module6-offline"})
        self._traces = TracerProvider(
            resource=resource,
            shutdown_on_exit=False,
            id_generator=ApplicationIds(),
            sampler=ALWAYS_ON,
            span_limits=SpanLimits(
                max_attributes=10,
                max_events=2,
                max_links=0,
                max_span_attributes=10,
                max_event_attributes=2,
                max_link_attributes=0,
                max_attribute_length=64,
                max_span_attribute_length=64,
            ),
        )
        self._traces.add_span_processor(
            SimpleSpanProcessor(BoundedCollection(), meter_provider=NoOpMeterProvider())
        )
        self._tracer = self._traces.get_tracer("module6.observability")
        self._reader = InMemoryMetricReader()
        self._meters = MeterProvider(
            metric_readers=(self._reader,),
            resource=resource,
            shutdown_on_exit=False,
            exemplar_filter=AlwaysOffExemplarFilter(),
            views=(
                View(
                    instrument_name="module6.workflow.duration",
                    attribute_keys={"runtime", "topology", "distributed", "outcome"},
                    aggregation=ExplicitBucketHistogramAggregation(
                        boundaries=(1, 10, 100, 1000, 10000, 30000),
                        record_min_max=False,
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
        self._last_state = (0, 0)

    def _retain_spans(self, batch):
        self._spans.extend(batch)

    def state(self, snapshot: MetricSnapshot) -> None:
        """Record active/started deltas from one revalidated snapshot."""
        snapshot = MetricSnapshot.model_validate(snapshot.model_dump())
        with self._lock:
            active, started = self._last_state
            self._active.add(snapshot.active - active)
            if snapshot.started > started:
                self._started.add(snapshot.started - started)
            self._last_state = (snapshot.active, snapshot.started)

    def emit(self, trace: RunTrace) -> None:
        """Record local spans and closed-dimension metrics for one trace.

        Raises:
            ValueError: The trace failed revalidation.
            RuntimeError: Local span collection failed; the observer counts it
                as an adapter failure without changing the workflow.
        """
        from opentelemetry.context import Context
        from opentelemetry.trace import (
            NonRecordingSpan,
            SpanContext,
            Status,
            StatusCode,
            set_span_in_context,
        )

        trace = checked_trace(trace)
        labels = MetricLabels(
            runtime=trace.runtime,
            topology=trace.topology,
            distributed=trace.distributed,
            outcome=trace.outcome,
        ).model_dump(mode="json")
        with self._lock:
            failures_before = self._collection_failures
            token = self._identity.set((trace.trace_id.int, int(trace.span_id, 16)))
            try:
                root = self._tracer.start_span(
                    "module6.workflow",
                    context=Context(),
                    start_time=trace.started_ns,
                    attributes={
                        **labels,
                        "workflow_id": str(trace.workflow_id),
                        "task_id": str(trace.task_id),
                    },
                )
                root.add_event("workflow.started", timestamp=trace.started_ns)
                root.add_event(
                    f"workflow.{trace.outcome.value}", timestamp=trace.ended_ns
                )
                root.set_status(
                    Status(
                        StatusCode.OK
                        if trace.outcome.value == "completed"
                        else StatusCode.ERROR
                    )
                )
                root.end(end_time=trace.ended_ns)
                parent = set_span_in_context(
                    NonRecordingSpan(
                        SpanContext(
                            trace_id=trace.trace_id.int,
                            span_id=int(trace.span_id, 16),
                            is_remote=False,
                            trace_flags=root.get_span_context().trace_flags,
                        )
                    ),
                    Context(),
                )
                for step in trace.steps:
                    self._identity.set((trace.trace_id.int, int(step.span_id, 16)))
                    child = self._tracer.start_span(
                        "module6.validated_completion",
                        context=parent,
                        start_time=trace.ended_ns,
                        attributes={"role": step.role.value, "sequence": step.sequence},
                    )
                    child.end(end_time=trace.ended_ns)
                self._runs.add(1, labels)
                self._duration.record(trace.duration_ms, labels)
                if trace.accounting.model_calls is not None:
                    self._models.add(trace.accounting.model_calls, labels)
                if trace.accounting.retries is not None:
                    self._retries.add(trace.accounting.retries, labels)
                if trace.workers_reaped is not None:
                    self._workers.add(trace.workers_reaped, labels)
                if self._collection_failures != failures_before:
                    raise RuntimeError("Local span collection failed.")
            finally:
                self._identity.reset(token)

    def collect_metrics(self) -> "MetricsData | None":
        """Local SDK collection data; infrastructure must curate before presentation."""
        with self._lock:
            return self._reader.get_metrics_data()

    def close(self) -> None:
        """Shut down the private providers once; later calls do nothing."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._traces.shutdown()
            self._meters.shutdown()
