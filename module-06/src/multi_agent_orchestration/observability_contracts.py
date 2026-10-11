"""Closed, payload-free application contracts; telemetry never grants authority."""

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import Field, model_validator

from .contracts import Contract, GraphTopology, RuntimeId

Count = Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]
SpanId = Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{16}$")]


class Outcome(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    DENIED = "denied"


class Role(StrEnum):
    FIXTURE = "fixture_agent"
    WORKER = "deterministic_worker"
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    CRITIC = "critic"
    COORDINATOR = "adk_coordinator"
    SPECIALIST = "adk_specialist"
    VALIDATOR = "adk_validator"
    GRAPH_RESEARCHER = "graph_researcher"
    GRAPH_ANALYST = "graph_analyst"
    GRAPH_CRITIC = "graph_critic"
    GRAPH_AGGREGATOR = "graph_aggregator"
    GRAPH_LEFT = "graph_left"
    GRAPH_RIGHT = "graph_right"
    GRAPH_SUPERVISOR = "graph_supervisor"
    GRAPH_LEAD = "graph_lead"
    GRAPH_SPECIALIST = "graph_specialist"
    LEFT = "left_counter"
    RIGHT = "right_counter"


class Accounting(Contract):
    """None means unobserved, never zero, free pricing, or provider billing."""

    model_calls: Annotated[int, Field(strict=True, ge=0, le=0)] | None = None
    provider_calls: Annotated[int, Field(strict=True, ge=0, le=0)] | None = None
    external_calls: Annotated[int, Field(strict=True, ge=0, le=0)] | None = None
    retries: Annotated[int, Field(strict=True, ge=0, le=0)] | None = None
    input_tokens: None = None
    output_tokens: None = None
    estimated_cost_usd: None = None
    provider_reported_cost_usd: None = None


class StepTrace(Contract):
    """Validated completion provenance, not reconstructed execution timing."""

    role: Role
    sequence: Annotated[int, Field(strict=True, ge=1, le=3)]
    span_id: SpanId
    worker_pid: Annotated[int, Field(strict=True, ge=1)] | None = None
    assignment_id: UUID | None = None

    @model_validator(mode="after")
    def worker_pair(self):
        if (self.worker_pid is None) != (self.assignment_id is None):
            raise ValueError("Worker provenance must be complete.")
        if int(self.span_id, 16) == 0:
            raise ValueError("Span identity must be nonzero.")
        return self


class RunTrace(Contract):
    """One bounded observation correlated with validated evidence when available."""

    workflow_id: UUID
    task_id: UUID
    trace_id: UUID
    span_id: SpanId
    runtime: RuntimeId
    topology: GraphTopology
    distributed: Annotated[bool, Field(strict=True)] = False
    outcome: Outcome
    started_ns: Annotated[int, Field(strict=True, ge=1)]
    ended_ns: Annotated[int, Field(strict=True, ge=1)]
    duration_ms: Annotated[float, Field(strict=True, ge=0, le=3_600_000)]
    accounting: Accounting = Field(default_factory=Accounting)
    steps: Annotated[tuple[StepTrace, ...], Field(max_length=3)] = ()
    workers_at_barrier: Annotated[int, Field(strict=True, ge=2, le=2)] | None = None
    workers_reaped: Annotated[int, Field(strict=True, ge=2, le=2)] | None = None

    @model_validator(mode="after")
    def consistency(self):
        spans = (self.span_id, *(step.span_id for step in self.steps))
        if (
            self.trace_id.int == 0
            or any(int(span, 16) == 0 for span in spans)
            or len(set(spans)) != len(spans)
            or self.ended_ns < self.started_ns
            or tuple(step.sequence for step in self.steps)
            != tuple(range(1, len(self.steps) + 1))
        ):
            raise ValueError("Trace correlation/order is invalid.")
        if self.outcome != Outcome.COMPLETED and (
            self.steps
            or self.accounting != Accounting()
            or self.workers_at_barrier is not None
            or self.workers_reaped is not None
        ):
            raise ValueError("Failed execution cannot invent completion accounting.")
        if self.distributed and self.outcome == Outcome.COMPLETED:
            if (
                self.runtime != RuntimeId.GOOGLE_ADK
                or tuple(step.role for step in self.steps) != (Role.LEFT, Role.RIGHT)
                or len({step.worker_pid for step in self.steps}) != 2
                or any(step.worker_pid is None for step in self.steps)
                or len({step.assignment_id for step in self.steps}) != 2
                or self.workers_at_barrier != 2
                or self.workers_reaped != 2
            ):
                raise ValueError("Distributed trace contradicts worker evidence.")
        elif (
            any(step.worker_pid is not None for step in self.steps)
            or self.workers_at_barrier is not None
            or self.workers_reaped is not None
        ):
            raise ValueError("Worker observations require distributed completion.")
        if self.outcome == Outcome.COMPLETED:
            if self.accounting != Accounting(
                model_calls=0,
                external_calls=0,
                retries=0,
                provider_calls=0 if self.distributed else None,
            ):
                raise ValueError("Accounting must match accepted offline evidence.")
            if not self.distributed:
                from .topologies import topology_plan

                roles = (
                    tuple(
                        Role(role.value) for role in topology_plan(self.topology).roles
                    )
                    if self.runtime == RuntimeId.LANGGRAPH
                    and self.topology != GraphTopology.COORDINATOR_WORKER
                    else {
                        RuntimeId.FIXTURE: (Role.FIXTURE,),
                        RuntimeId.LANGGRAPH: (Role.WORKER,),
                        RuntimeId.CREWAI: (Role.RESEARCHER, Role.ANALYST, Role.CRITIC),
                        RuntimeId.GOOGLE_ADK: (
                            Role.COORDINATOR,
                            Role.SPECIALIST,
                            Role.VALIDATOR,
                        ),
                    }[self.runtime]
                )
                if tuple(step.role for step in self.steps) != roles:
                    raise ValueError(
                        "Trace roles contradict accepted runtime ownership."
                    )
        if (
            self.runtime != RuntimeId.LANGGRAPH
            and self.topology != GraphTopology.COORDINATOR_WORKER
        ):
            raise ValueError("Trace topology contradicts runtime selection.")
        return self


class MetricLabels(Contract):
    """At most 4 runtimes x 4 topologies x 2 paths x 5 terminal outcomes."""

    runtime: RuntimeId
    topology: GraphTopology
    distributed: Annotated[bool, Field(strict=True)]
    outcome: Outcome


class MetricSnapshot(Contract):
    started: Count
    active: Annotated[int, Field(strict=True, ge=0, le=16)]
    completed: Count
    failed: Count
    timed_out: Count
    cancelled: Count
    denied: Count
    observation_drops: Count
    adapter_failures: Count


class CollectionBoundary(Contract):
    """Infrastructure handoff, no address/credential or routing in workflow data."""

    protocol: Annotated[str, Field(pattern=r"^otlp-compatible$")] = "otlp-compatible"
    delivery_enabled: Annotated[bool, Field(strict=True)] = False
    max_retained_runs: Annotated[int, Field(strict=True, ge=1, le=32)] = 32

    @model_validator(mode="after")
    def offline_only(self):
        if self.delivery_enabled:
            raise ValueError("Remote delivery is outside this authorized story.")
        return self
