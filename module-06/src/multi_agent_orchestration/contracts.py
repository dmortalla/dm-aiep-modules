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
    max_tasks: Annotated[int, Field(strict=True, ge=1, le=3)] = 3
    max_messages: Annotated[int, Field(strict=True, ge=1, le=3)] = 3
    max_concurrency: Annotated[int, Field(strict=True, ge=1, le=2)] = 2
    max_hierarchy_depth: Annotated[int, Field(strict=True, ge=0, le=2)] = 2


class GraphTopology(StrEnum):
    """Closed explicit LangGraph choices; existing coordinator-worker is default."""

    COORDINATOR_WORKER = "coordinator_worker"
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HIERARCHICAL = "hierarchical"


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
    """Application request for bounded fixture, graph, or collaborative execution."""

    workflow_id: UUID = Field(default_factory=uuid4)
    runtime: RuntimeId = RuntimeId.FIXTURE
    task: TaskInput
    limits: ExecutionLimits = Field(default_factory=ExecutionLimits)
    topology: GraphTopology = GraphTopology.COORDINATOR_WORKER

    @model_validator(mode="after")
    def topology_matches_runtime(self) -> "WorkflowRequest":
        """Topology selection cannot silently route to another runtime."""
        if (
            self.runtime != RuntimeId.LANGGRAPH
            and self.topology != GraphTopology.COORDINATOR_WORKER
        ):
            raise ValueError(
                "Expanded topologies require explicit LangGraph selection."
            )
        return self


class RuntimeInfo(Contract):
    """Application capability metadata, independent of framework objects."""

    runtime: RuntimeId
    execution_available: bool
    evidence_class: Literal[
        "deterministic_fixture",
        "deterministic_graph",
        "deterministic_collaboration",
        "deterministic_multi_agent",
        "adapter_construction",
    ]
    framework_version: Annotated[str, Field(max_length=64)] | None = None


class AgentTaskResult(Contract):
    """Untrusted candidate output until checked against the application request."""

    task_id: UUID
    agent_id: Literal[
        "fixture_agent",
        "deterministic_worker",
        "critic",
        "adk_validator",
        "graph_critic",
        "graph_aggregator",
        "graph_supervisor",
    ]
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


class CollaboratorRole(StrEnum):
    """Closed application collaborator ownership and ordering."""

    RESEARCHER = "researcher"
    ANALYST = "analyst"
    CRITIC = "critic"


class ContributionRecord(Contract):
    """Payload-free provenance for one validated contribution."""

    workflow_id: UUID
    task_id: UUID
    role: CollaboratorRole
    sequence: Annotated[int, Field(strict=True, ge=1, le=3)]
    sources: Annotated[tuple[CollaboratorRole, ...], Field(max_length=2)] = ()


class CollaborationMessage(ContributionRecord):
    """Bounded candidate role output; revalidate before shared-state insertion."""

    content: Annotated[str, Field(strict=True, min_length=1, max_length=256)] = Field(
        repr=False
    )


class CollaborationState(Contract):
    """Immutable workflow-scoped shared context; no persistent/global memory."""

    request: WorkflowRequest
    messages: Annotated[tuple[CollaborationMessage, ...], Field(max_length=3)] = ()


class OrchestrationRole(StrEnum):
    """Application-owned identities for local ADK delegation and validation."""

    COORDINATOR = "adk_coordinator"
    SPECIALIST = "adk_specialist"
    VALIDATOR = "adk_validator"


class OrchestrationRecord(Contract):
    """Payload-free ordered ownership and upstream provenance."""

    workflow_id: UUID
    task_id: UUID
    role: OrchestrationRole
    sequence: Annotated[int, Field(strict=True, ge=1, le=3)]
    sources: Annotated[tuple[OrchestrationRole, ...], Field(max_length=2)] = ()


class OrchestrationMessage(OrchestrationRecord):
    """Candidate event data, never policy, authority, or trusted evidence."""

    content: Annotated[str, Field(strict=True, min_length=1, max_length=256)] = Field(
        repr=False
    )


class OrchestrationState(Contract):
    """Immutable context transported by a fresh, in-memory ADK session."""

    request: WorkflowRequest
    messages: Annotated[tuple[OrchestrationMessage, ...], Field(max_length=3)] = ()


class GraphRole(StrEnum):
    """Fixed ownership, not a grant of application privilege."""

    RESEARCHER = "graph_researcher"
    ANALYST = "graph_analyst"
    CRITIC = "graph_critic"
    AGGREGATOR = "graph_aggregator"
    LEFT = "graph_left"
    RIGHT = "graph_right"
    SUPERVISOR = "graph_supervisor"
    LEAD = "graph_lead"
    SPECIALIST = "graph_specialist"


class GraphRecord(Contract):
    """Payload-free bounded topology contribution provenance."""

    workflow_id: UUID
    task_id: UUID
    role: GraphRole
    sequence: Annotated[int, Field(strict=True, ge=1, le=3)]
    parent: GraphRole | None = None
    sources: Annotated[tuple[GraphRole, ...], Field(max_length=2)] = ()


class GraphMessage(GraphRecord):
    """Untrusted bounded role contribution."""

    content: Annotated[str, Field(strict=True, min_length=1, max_length=256)] = Field(
        repr=False
    )


class GraphDelegation(Contract):
    """Application-fixed parent/child scope, never supplied authority."""

    parent: GraphRole
    child: GraphRole
    depth: Annotated[int, Field(strict=True, ge=1, le=2)]


class TopologyState(Contract):
    """Immutable context with finite phases and bounded shared contributions."""

    request: WorkflowRequest
    phase: Annotated[int, Field(strict=True, ge=0, le=5)] = 0
    delegations: Annotated[tuple[GraphDelegation, ...], Field(max_length=2)] = ()
    contributions: Annotated[tuple[GraphMessage, ...], Field(max_length=3)] = ()


class RuntimeOutput(Contract):
    """Candidate execution result; deliberately contains no policy or evidence."""

    workflow_id: UUID
    runtime: RuntimeId
    result: AgentTaskResult
    transitions: Annotated[tuple[WorkflowTransition, ...], Field(max_length=3)] = ()
    collaboration: Annotated[tuple[CollaborationMessage, ...], Field(max_length=3)] = ()
    orchestration: Annotated[tuple[OrchestrationMessage, ...], Field(max_length=3)] = ()
    topology: GraphTopology = GraphTopology.COORDINATOR_WORKER
    contributions: Annotated[tuple[GraphMessage, ...], Field(max_length=3)] = ()


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
    collaboration: Annotated[tuple[ContributionRecord, ...], Field(max_length=3)] = ()
    orchestration: Annotated[tuple[OrchestrationRecord, ...], Field(max_length=3)] = ()
    topology: GraphTopology = GraphTopology.COORDINATOR_WORKER
    contributions: Annotated[tuple[GraphRecord, ...], Field(max_length=3)] = ()


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
        expanded = self.evidence.topology != GraphTopology.COORDINATOR_WORKER
        if expanded:
            from .topologies import topology_plan

            plan = topology_plan(self.evidence.topology)
            expected_records = tuple(
                GraphRecord(
                    workflow_id=self.evidence.workflow_id,
                    task_id=self.evidence.task_id,
                    role=role,
                    sequence=index + 1,
                    parent=plan.parents[index],
                    sources=plan.sources[index],
                )
                for index, role in enumerate(plan.roles)
            )
            if (
                self.evidence.actual_runtime != RuntimeId.LANGGRAPH
                or self.result.agent_id != plan.roles[-1].value
                or self.evidence.steps_consumed != plan.steps
                or self.evidence.transitions
                or self.evidence.collaboration
                or self.evidence.orchestration
                or self.evidence.contributions != expected_records
                or self.evidence.limits.max_tasks < 3
                or self.evidence.limits.max_messages < 3
                or self.evidence.limits.max_concurrency < plan.concurrency
                or self.evidence.limits.max_hierarchy_depth < plan.depth
            ):
                raise ValueError(
                    "Expanded graph evidence contradicts its bounded topology."
                )
            return self
        if self.evidence.contributions:
            raise ValueError(
                "Topology contributions require explicit expanded selection."
            )
        if (
            self.evidence.actual_runtime != RuntimeId.GOOGLE_ADK
            and self.evidence.orchestration
        ):
            raise ValueError("ADK provenance requires explicit ADK execution.")
        if self.evidence.actual_runtime == RuntimeId.FIXTURE:
            if (
                self.result.agent_id != "fixture_agent"
                or self.evidence.steps_consumed != 1
                or self.evidence.transitions
                or self.evidence.collaboration
            ):
                raise ValueError(
                    "Fixture evidence must describe exactly one fixture step."
                )
        elif self.evidence.actual_runtime == RuntimeId.LANGGRAPH:
            if (
                self.result.agent_id != "deterministic_worker"
                or self.evidence.steps_consumed != 3
                or self.evidence.transitions != tuple(WorkflowTransition)
                or self.evidence.collaboration
            ):
                raise ValueError(
                    "LangGraph evidence must describe the validated three-step flow."
                )
        elif self.evidence.actual_runtime == RuntimeId.CREWAI:
            roles = tuple(CollaboratorRole)
            expected = tuple(
                ContributionRecord(
                    workflow_id=self.evidence.workflow_id,
                    task_id=self.evidence.task_id,
                    role=role,
                    sequence=index + 1,
                    sources=roles[:index],
                )
                for index, role in enumerate(roles)
            )
            if (
                self.result.agent_id != "critic"
                or self.evidence.steps_consumed != 3
                or self.evidence.transitions
                or self.evidence.collaboration != expected
                or self.evidence.limits.max_tasks < 3
                or self.evidence.limits.max_messages < 3
            ):
                raise ValueError(
                    "CrewAI evidence must describe three validated role contributions."
                )
        elif self.evidence.actual_runtime == RuntimeId.GOOGLE_ADK:
            roles = tuple(OrchestrationRole)
            expected = tuple(
                OrchestrationRecord(
                    workflow_id=self.evidence.workflow_id,
                    task_id=self.evidence.task_id,
                    role=role,
                    sequence=index + 1,
                    sources=roles[:index],
                )
                for index, role in enumerate(roles)
            )
            if (
                self.result.agent_id != "adk_validator"
                or self.evidence.steps_consumed != 3
                or self.evidence.transitions
                or self.evidence.collaboration
                or self.evidence.orchestration != expected
                or min(
                    self.evidence.limits.max_tasks, self.evidence.limits.max_messages
                )
                < 3
            ):
                raise ValueError("ADK evidence requires three validated role events.")
        else:
            raise ValueError("This runtime does not support execution.")
        return self
