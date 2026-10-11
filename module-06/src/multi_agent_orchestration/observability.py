"""Bounded observation state, separate from execution results and authority."""

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Protocol
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

CEILING = 1_000_000_000


class ObservationAdapter(Protocol):
    """Trusted bounded synchronous local infrastructure, never request data."""

    def emit(self, trace: RunTrace) -> None: ...

    def state(self, snapshot: MetricSnapshot) -> None: ...


def span_id():
    return f"{uuid4().int >> 64:016x}"


@dataclass(frozen=True)
class ObservationHandle:
    request: WorkflowRequest
    trace_id: UUID
    span_id: str
    distributed: bool
    started_ns: int
    clock: float


class Observability:
    """Trusted code constructs local adapters; request/runtime data never does.

    At most 16 active observations, 32 completed records, four spans per run.
    Excess observations are dropped, not execution requests. Adapter exceptions
    increment a saturated counter, never log exception text or alter execution.
    Adapters must be bounded, synchronous local operations; remote exporters are
    deliberately unavailable. No background tasks, queues or retry machinery.
    """

    def __init__(self, *, adapters: tuple[ObservationAdapter, ...] = ()):
        if len(adapters) > 2:
            raise ValueError("At most two local observability adapters are supported.")
        self._adapters = tuple(adapters)
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

    def _increment(self, name):
        self._counts[name] = min(CEILING, self._counts[name] + 1)

    def _publish_state(self):
        for adapter in self._adapters:
            try:
                adapter.state(self.metrics)
            except (Exception, asyncio.CancelledError):
                self._increment("adapter_failures")

    def begin(self, request: WorkflowRequest, distributed: bool):
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

    def finish(self, handle, outcome: Outcome, result=None):
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

    def abandon(self, handle):
        """Release bookkeeping after observation failure without exposing content."""
        with self._lock:
            if handle is not None and self._active.get(handle.trace_id) is handle:
                del self._active[handle.trace_id]
            self._increment("observation_drops")
            self._publish_state()

    @property
    def records(self):
        with self._lock:
            return tuple(self._records)

    @property
    def metrics(self):
        with self._lock:
            return MetricSnapshot(active=len(self._active), **self._counts)
