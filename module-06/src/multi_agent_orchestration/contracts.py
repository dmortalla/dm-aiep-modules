"""Immutable contracts separating caller input, runtime output, and evidence."""

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RuntimeId(StrEnum):
    """Explicit application-owned runtime choices."""

    FIXTURE = "fixture"
    LANGGRAPH = "langgraph"
    CREWAI = "crewai"
    GOOGLE_ADK = "google_adk"


class ExecutionStatus(StrEnum):
    """Application lifecycle vocabulary; no framework state types escape."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class Contract(BaseModel):
    """Reject unknown fields and prevent mutation of validated state."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ExecutionLimits(Contract):
    """Caller-supplied bounds within the foundation's hard resource ceilings."""

    max_steps: Annotated[int, Field(strict=True, ge=1, le=32)] = 1
    timeout_ms: Annotated[int, Field(strict=True, ge=1, le=30_000)] = 1_000


class TaskInput(Contract):
    """Single bounded task input; instructions are data, never authority."""

    task_id: UUID = Field(default_factory=uuid4)
    instruction: Annotated[str, Field(strict=True, min_length=1, max_length=4096)] = (
        Field(repr=False)
    )

    @model_validator(mode="after")
    def require_nonblank_instruction(self) -> "TaskInput":
        """Reject whitespace-only task input without including it in errors."""
        if not self.instruction.strip():
            raise ValueError("Task instruction must contain non-whitespace text.")
        return self


class WorkflowRequest(Contract):
    """Application request for one bounded fixture or coordinator-worker task."""

    workflow_id: UUID = Field(default_factory=uuid4)
    runtime: RuntimeId = RuntimeId.FIXTURE
    task: TaskInput
    limits: ExecutionLimits = Field(default_factory=ExecutionLimits)


class RuntimeInfo(Contract):
    """Application capability metadata, independent of framework objects."""

    runtime: RuntimeId
    execution_available: bool
    evidence_class: Literal[
        "deterministic_fixture", "deterministic_graph", "adapter_construction"
    ]
    framework_version: Annotated[str, Field(max_length=64)] | None = None


class AgentTaskResult(Contract):
    """Untrusted candidate output until checked against the application request."""

    task_id: UUID
    agent_id: Literal["fixture_agent", "deterministic_worker"]
    status: Literal[ExecutionStatus.COMPLETED]
    output: Annotated[str, Field(strict=True, min_length=1, max_length=4096)] = Field(
        repr=False
    )


class WorkflowTransition(StrEnum):
    """Finite application-owned coordinator-worker transition vocabulary."""

    DELEGATED = "coordinator_delegated"
    WORKED = "worker_completed"
    VALIDATED = "coordinator_validated"


class WorkflowPhase(StrEnum):
    """Application state phases independent of LangGraph machinery."""

    PENDING = "pending"
    DELEGATED = "delegated"
    WORKED = "worked"
    COMPLETED = "completed"


class WorkflowState(Contract):
    """Bounded context passed between nodes; never trusted without revalidation."""

    request: WorkflowRequest
    phase: WorkflowPhase = WorkflowPhase.PENDING
    delegated_to: Literal["deterministic_worker"] | None = None
    result: AgentTaskResult | None = None
    transitions: Annotated[tuple[WorkflowTransition, ...], Field(max_length=3)] = ()


class RuntimeOutput(Contract):
    """Candidate execution result; deliberately contains no policy or evidence."""

    workflow_id: UUID
    runtime: RuntimeId
    result: AgentTaskResult
    transitions: Annotated[tuple[WorkflowTransition, ...], Field(max_length=3)] = ()


class ExecutionEvidence(Contract):
    """Application-created metadata; no instructions, payloads, or credentials."""

    workflow_id: UUID
    task_id: UUID
    requested_runtime: RuntimeId
    actual_runtime: RuntimeId
    status: Literal[ExecutionStatus.COMPLETED]
    mode: Literal["deterministic_offline"] = "deterministic_offline"
    steps_consumed: Annotated[int, Field(strict=True, ge=1, le=32)] = 1
    limits: ExecutionLimits
    retries: Literal[0] = 0
    model_calls: Literal[0] = 0
    external_calls: Literal[0] = 0
    transitions: Annotated[tuple[WorkflowTransition, ...], Field(max_length=3)] = ()


class ValidatedWorkflowResult(Contract):
    """Successful application result with internally consistent evidence."""

    result: AgentTaskResult
    evidence: ExecutionEvidence

    @model_validator(mode="after")
    def consistent_evidence(self) -> "ValidatedWorkflowResult":
        """Reject task or runtime identity contradictions."""
        if self.result.task_id != self.evidence.task_id:
            raise ValueError("Result and evidence task identities must match.")
        if self.evidence.requested_runtime != self.evidence.actual_runtime:
            raise ValueError("Implicit runtime fallback is forbidden.")
        if self.evidence.steps_consumed > self.evidence.limits.max_steps:
            raise ValueError("Evidence cannot exceed the application step budget.")
        if self.evidence.actual_runtime == RuntimeId.FIXTURE:
            if (
                self.result.agent_id != "fixture_agent"
                or self.evidence.steps_consumed != 1
                or self.evidence.transitions
            ):
                raise ValueError(
                    "Fixture evidence must describe exactly one fixture step."
                )
        elif self.evidence.actual_runtime == RuntimeId.LANGGRAPH:
            if (
                self.result.agent_id != "deterministic_worker"
                or self.evidence.steps_consumed != 3
                or self.evidence.transitions != tuple(WorkflowTransition)
            ):
                raise ValueError(
                    "LangGraph evidence must describe the validated three-step flow."
                )
        else:
            raise ValueError("This runtime does not support execution.")
        return self
