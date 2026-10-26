"""Bounded observation state, separate from execution results and authority."""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from uuid import UUID, uuid4

from .contracts import ValidatedWorkflowResult, WorkflowRequest
from .distributed_contracts import DistributedResult
from .observability_contracts import (
    Accounting,
    MetricSnapshot,
    Outcome,
    Role,
    RunTrace,
    StepTrace,
)

if TYPE_CHECKING:
    from .canonical_contracts import LiveWorkflowEvent
    from .live_observation import LiveTerminalObservation

CEILING = 1_000_000_000


class ObservationAdapter(Protocol):
    """Trusted bounded synchronous local infrastructure, never request data."""

    def emit(self, trace: RunTrace) -> None:
        """Record one validated completed trace locally; no remote I/O."""
        ...

    def state(self, snapshot: MetricSnapshot) -> None:
        """Record one bounded metric snapshot locally."""
        ...


class LiveObservationAdapter(Protocol):
    """Trusted bounded synchronous local sink; no remote I/O or authority."""

    def emit_live(self, event: LiveWorkflowEvent) -> None:
        """Record one revalidated live workflow event locally."""
        ...


def span_id() -> str:
    """Return a fresh random 16-hex-digit local span identifier."""
    return f"{uuid4().int >> 64:016x}"


@dataclass(frozen=True)
class ObservationHandle:
    """Opaque owned handle for one active deterministic observation."""

    request: WorkflowRequest
    trace_id: UUID
    span_id: str
    distributed: bool
    started_ns: int
    clock: float


class Observability:
    """Trusted code constructs local adapters; request/runtime data never does.

    At most 16 active observations, 32 completed records, four spans per run.
    The separate live channel retains 32 events and supports two local sinks;
    it never converts live counts into deterministic trace accounting.
    Excess observations are dropped, not execution requests. Adapter exceptions
    increment a saturated counter, never log exception text or alter execution.
    Adapters must be bounded, synchronous local operations; remote exporters are
    deliberately unavailable. No background tasks, queues or retry machinery.
    """

    def __init__(
        self,
        *,
        adapters: tuple[ObservationAdapter, ...] = (),
        live_adapters: tuple[LiveObservationAdapter, ...] = (),
    ):
        if len(adapters) > 2 or len(live_adapters) > 2:
            raise ValueError("At most two local adapters per channel are supported.")
        self._adapters = tuple(adapters)
        self._live_adapters = tuple(live_adapters)
        self._live_records = deque(maxlen=32)
        self._live_terminal = deque(maxlen=32)
        self._live_active = {}
        self._records = deque(maxlen=32)
        self._active = {}
        self._counts = dict.fromkeys(
            (
                "started",
                "completed",
                "failed",
                "timed_out",
                "cancelled",
                "denied",
                "observation_drops",
                "adapter_failures",
            ),
            0,
        )
        self._lock = threading.RLock()

    def begin_live(self, identity: object) -> object | None:
        """Own an opaque invocation handle; a valid UUID is not ownership.

        Args:
            identity: Untrusted live observation identity data.

        Returns:
            A new opaque handle, or ``None`` when the bounded active set is
            full or the trace identifier is already active or finalized (the
            drop is counted).

        Raises:
            LiveValidationError: The identity failed validation.
        """
        from .live_observation import LiveObservationIdentity, checked_observation

        checked = checked_observation(LiveObservationIdentity, identity)
        with self._lock:
            if (
                len(self._live_active) >= 16
                or any(
                    LiveObservationIdentity.model_validate_json(record).trace_id
                    == checked.trace_id
                    for record in self._live_active.values()
                )
                or any(
                    record.trace_id == checked.trace_id
                    for record in self.live_terminal_records
                )
            ):
                self._increment("observation_drops")
                return None
            handle = object()
            self._live_active[handle] = checked.model_dump_json()
            return handle

    def finish_live(
        self, handle: object, observation: object
    ) -> LiveTerminalObservation:
        """Validate linkage and finalize once; no adapter or SDK is called.

        Args:
            handle: The exact opaque handle returned by ``begin_live``.
            observation: Untrusted terminal observation data.

        Returns:
            A fresh validated snapshot of the retained terminal observation.

        Raises:
            LiveValidationError: Unowned/replayed handle, invalid observation
                or identity mismatch; no cause is exposed.
        """
        from .live_errors import LiveValidationError
        from .live_observation import LiveTerminalObservation, checked_observation

        with self._lock:
            # Identity lookup, never equality supplied by an untrusted handle.
            owned = next((key for key in self._live_active if key is handle), None)
            if owned is None:
                raise LiveValidationError() from None
            checked = checked_observation(LiveTerminalObservation, observation)
            identity = self._live_active[owned]
            from .live_observation import LiveObservationIdentity

            expected = LiveObservationIdentity.model_validate_json(identity)
            if any(
                getattr(checked, field) != getattr(expected, field)
                for field in LiveObservationIdentity.model_fields
            ):
                raise LiveValidationError() from None
            packet = checked.model_dump_json()
            del self._live_active[owned]
            if len(self._live_terminal) == self._live_terminal.maxlen:
                self._increment("observation_drops")
            self._live_terminal.append(packet)
            return LiveTerminalObservation.model_validate_json(packet)

    def abandon_live(self, handle: object) -> None:
        """Release local bookkeeping without changing execution authority."""
        with self._lock:
            owned = next((key for key in self._live_active if key is handle), None)
            if owned is not None:
                del self._live_active[owned]
            self._increment("observation_drops")

    @property
    def live_terminal_records(self) -> tuple[LiveTerminalObservation, ...]:
        """Fresh immutable snapshots; independent of deterministic traces."""
        from .live_observation import LiveTerminalObservation

        with self._lock:
            return tuple(
                LiveTerminalObservation.model_validate_json(packet)
                for packet in self._live_terminal
            )

    def emit_live(self, event: LiveWorkflowEvent) -> None:
        """Retain bounded local events separately from legacy zero-call traces.

        No SDK exporter or legacy trace/accounting conversion is invoked. Each
        sink gets its own revalidated copy; sink mutations cannot affect another
        sink, retained observations, or the workflow. Failures increment only
        the existing saturated observation-failure counter.
        """
        # Deterministic startup must not load the additive live contract family.
        from .canonical_contracts import LiveWorkflowEvent

        with self._lock:
            try:
                if type(event) is not LiveWorkflowEvent or set(event.__dict__) != set(
                    LiveWorkflowEvent.model_fields
                ):
                    raise ValueError("Unowned observation.")
                checked = LiveWorkflowEvent.model_validate(dict(event.__dict__))
                packet = checked.model_dump_json()
            except (ValueError, TypeError, AttributeError):
                self._increment("observation_drops")
                return
            if len(self._live_records) == self._live_records.maxlen:
                self._increment("observation_drops")
            self._live_records.append(packet)
            for adapter in self._live_adapters:
                try:
                    adapter.emit_live(LiveWorkflowEvent.model_validate_json(packet))
                except (Exception, asyncio.CancelledError):
                    self._increment("adapter_failures")

    @property
    def live_records(self) -> tuple[LiveWorkflowEvent, ...]:
        """Return fresh snapshots, not mutable references to retained events."""
        from .canonical_contracts import LiveWorkflowEvent

        with self._lock:
            return tuple(
                LiveWorkflowEvent.model_validate_json(packet)
                for packet in self._live_records
            )

    def _increment(self, name):
        self._counts[name] = min(CEILING, self._counts[name] + 1)

    def _publish_state(self):
        for adapter in self._adapters:
            try:
                adapter.state(self.metrics)
            except (Exception, asyncio.CancelledError):
                self._increment("adapter_failures")

    def begin(
        self, request: WorkflowRequest, distributed: bool
    ) -> ObservationHandle | None:
        """Start observing one revalidated request.

        Args:
            request: The workflow request about to execute.
            distributed: Whether execution uses the distributed service.

        Returns:
            An owned handle, or ``None`` when 16 observations are already
            active (the drop is counted; execution is unaffected).
        """
        # Revalidate even nested model_construct/model_copy inputs.
        checked = WorkflowRequest.model_validate(request.model_dump(warnings="error"))
        checked = WorkflowRequest.model_validate(checked.model_dump())
        with self._lock:
            self._increment("started")
            if len(self._active) == 16:
                self._increment("observation_drops")
                self._publish_state()
                return None
            handle = ObservationHandle(
                checked,
                uuid4(),
                span_id(),
                distributed,
                time.time_ns(),
                time.perf_counter(),
            )
            self._active[handle.trace_id] = handle
            self._publish_state()
            return handle

    def finish(
        self,
        handle: ObservationHandle | None,
        outcome: Outcome,
        result: ValidatedWorkflowResult | DistributedResult | None = None,
    ) -> RunTrace | None:
        """Finalize one observation from validated execution evidence.

        Args:
            handle: The owned handle from ``begin``, or ``None`` (no-op).
            outcome: The closed workflow outcome.
            result: Validated success result; only with ``completed``.

        Returns:
            The bounded payload-free trace, or ``None`` for a ``None`` handle.

        Raises:
            ValueError: Unowned/replayed handle, evidence correlation failure
                or success evidence on a failure outcome.
        """
        if handle is None:
            return
        with self._lock:
            if self._active.get(handle.trace_id) is not handle:
                raise ValueError("Unowned or replayed observation handle.")
            request = handle.request
            steps, accounting = (), Accounting()
            barrier = reaped = None
            if outcome == Outcome.COMPLETED:
                if handle.distributed:
                    checked = DistributedResult.model_validate(
                        result.model_dump(warnings="error")
                    )
                    checked = DistributedResult.model_validate(checked.model_dump())
                    evidence = checked.evidence
                    records = evidence.workers
                    steps = tuple(
                        StepTrace(
                            role=Role(record.role.value),
                            sequence=record.sequence,
                            span_id=span_id(),
                            worker_pid=record.pid,
                            assignment_id=record.assignment_id,
                        )
                        for record in records
                    )
                    barrier = reaped = 2  # Service returns only after process reaping.
                else:
                    checked = ValidatedWorkflowResult.model_validate(
                        result.model_dump(warnings="error")
                    )
                    checked = ValidatedWorkflowResult.model_validate(
                        checked.model_dump()
                    )
                    evidence = checked.evidence
                    records = (
                        evidence.contributions
                        or evidence.collaboration
                        or evidence.orchestration
                    )
                    roles = tuple(record.role.value for record in records) or (
                        checked.result.agent_id,
                    )
                    steps = tuple(
                        StepTrace(
                            role=Role(role), sequence=index + 1, span_id=span_id()
                        )
                        for index, role in enumerate(roles)
                    )
                actual_runtime = (
                    evidence.runtime if handle.distributed else evidence.actual_runtime
                )
                if (
                    evidence.workflow_id != request.workflow_id
                    or evidence.task_id != request.task.task_id
                    or actual_runtime != request.runtime
                    or evidence.limits != request.limits
                    or (
                        not handle.distributed and evidence.topology != request.topology
                    )
                ):
                    raise ValueError("Observation/evidence correlation failed.")
                accounting = Accounting(
                    model_calls=evidence.model_calls,
                    provider_calls=evidence.provider_calls
                    if handle.distributed
                    else None,
                    external_calls=evidence.external_calls,
                    retries=evidence.retries,
                )
            elif result is not None:
                raise ValueError("Failure observation cannot carry success evidence.")
            trace = RunTrace(
                workflow_id=request.workflow_id,
                task_id=request.task.task_id,
                trace_id=handle.trace_id,
                span_id=handle.span_id,
                runtime=request.runtime,
                topology=request.topology,
                distributed=handle.distributed,
                outcome=outcome,
                started_ns=handle.started_ns,
                ended_ns=max(handle.started_ns, time.time_ns()),
                duration_ms=min(
                    3_600_000.0, (time.perf_counter() - handle.clock) * 1000
                ),
                steps=steps,
                accounting=accounting,
                workers_at_barrier=barrier,
                workers_reaped=reaped,
            )
            del self._active[handle.trace_id]
            self._increment(outcome.value)
            if len(self._records) == self._records.maxlen:
                self._increment("observation_drops")
            self._records.append(trace)
            self._publish_state()
            for adapter in self._adapters:
                try:
                    adapter.emit(trace)
                except (Exception, asyncio.CancelledError):
                    self._increment("adapter_failures")
            return trace

    def abandon(self, handle: ObservationHandle | None) -> None:
        """Release bookkeeping after observation failure without exposing content."""
        with self._lock:
            if handle is not None and self._active.get(handle.trace_id) is handle:
                del self._active[handle.trace_id]
            self._increment("observation_drops")
            self._publish_state()

    @property
    def records(self) -> tuple[RunTrace, ...]:
        """Retained completed traces (at most 32), oldest first."""
        with self._lock:
            return tuple(self._records)

    @property
    def metrics(self) -> MetricSnapshot:
        """A bounded snapshot of the saturated observation counters."""
        with self._lock:
            return MetricSnapshot(active=len(self._active), **self._counts)
