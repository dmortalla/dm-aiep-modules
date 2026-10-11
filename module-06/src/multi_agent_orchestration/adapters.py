"""Lazy SDK boundaries for deterministic graph execution and construction probes."""

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version

from pydantic import ValidationError

from .contracts import (
    RuntimeId,
    RuntimeInfo,
    RuntimeOutput,
    WorkflowPhase,
    WorkflowRequest,
    WorkflowState,
)
from .coordinator_worker import advance, validate_state
from .errors import (
    ExecutionFailureError,
    InvalidWorkflowRequestError,
    RuntimeFoundationError,
    RuntimeUnavailableError,
    StepBudgetExceededError,
)


class _ConstructionOnlyRuntime:
    """Keep native construction objects private and deny unsupported execution."""

    def __init__(
        self,
        runtime: RuntimeId,
        package: str,
        module: str,
        symbol: str,
        **kwargs: object,
    ) -> None:
        try:
            constructor = getattr(import_module(module), symbol)
            framework_version = version(package)
            self._native = constructor(**kwargs)
        except (ImportError, AttributeError, PackageNotFoundError) as exc:
            raise RuntimeUnavailableError(
                f"{runtime.value} is unavailable; synchronize the accepted uv lock."
            ) from exc
        except Exception as exc:
            # This is the SDK construction boundary, not blanket error swallowing.
            raise ExecutionFailureError(
                f"{runtime.value} SDK construction failed; inspect the internal cause."
            ) from exc
        self._info = RuntimeInfo(
            runtime=runtime,
            execution_available=False,
            evidence_class="adapter_construction",
            framework_version=framework_version,
        )

    @property
    def info(self) -> RuntimeInfo:
        """Return only application-owned capability and version information."""
        return self._info

    async def execute(self, request: WorkflowRequest) -> RuntimeOutput:
        """Refuse execution until a later application-owned workflow is implemented.

        Args:
            request: Application request; it cannot enable execution or providers.

        Raises:
            RuntimeUnavailableError: This adapter only proves SDK construction.
        """
        raise RuntimeUnavailableError(
            f"{self.info.runtime.value} execution is not implemented; "
            "add application-owned workflow/model/policy integration in a later story."
        )


class LangGraphRuntime(_ConstructionOnlyRuntime):
    """Run a finite, deterministic coordinator-worker graph without providers."""

    def __init__(self) -> None:
        """Construct the private SDK object without a model or telemetry client."""
        super().__init__(
            RuntimeId.LANGGRAPH,
            "langgraph",
            "langgraph.graph",
            "StateGraph",
            state_schema=WorkflowState,
        )
        self._info = RuntimeInfo(
            runtime=RuntimeId.LANGGRAPH,
            execution_available=True,
            evidence_class="deterministic_graph",
            framework_version=self.info.framework_version,
        )

    def _compile(self, expected: WorkflowRequest):
        """Compile isolated nodes whose trusted request is outside graph state."""
        graph = type(self._native)(state_schema=WorkflowState)
        graph.add_node(
            "coordinator",
            lambda state: advance(state, expected, WorkflowPhase.PENDING).model_dump(),
        )
        graph.add_node(
            "worker",
            lambda state: advance(
                state, expected, WorkflowPhase.DELEGATED
            ).model_dump(),
        )
        graph.add_node(
            "coordinator_validate",
            lambda state: advance(state, expected, WorkflowPhase.WORKED).model_dump(),
        )
        graph.add_edge("__start__", "coordinator")
        graph.add_edge("coordinator", "worker")
        graph.add_edge("worker", "coordinator_validate")
        graph.add_edge("coordinator_validate", "__end__")
        return graph.compile()

    async def execute(self, request: WorkflowRequest) -> RuntimeOutput:
        """Execute three validated local transitions, without retries or network.

        Args:
            request: Application request, revalidated even for Pydantic objects.

        Returns:
            Validated application output without framework objects or authority.

        Raises:
            InvalidWorkflowRequestError: Request schema or runtime is invalid.
            StepBudgetExceededError: Fewer than three steps are authorized.
            RuntimeFoundationError: State validation or graph execution fails.
        """
        try:
            expected = WorkflowRequest.model_validate(request.model_dump())
        except ValidationError as exc:
            raise InvalidWorkflowRequestError(
                "Graph request failed contract validation."
            ) from exc
        if expected.runtime != RuntimeId.LANGGRAPH:
            raise InvalidWorkflowRequestError(
                "LangGraph requires explicit matching runtime selection."
            )
        if expected.limits.max_steps < 3:
            raise StepBudgetExceededError(
                "Coordinator-worker execution requires three authorized steps."
            )
        try:
            compiled = self._compile(expected)
            # LangGraph's transitive tracing dependency honors ambient flags. Disable
            # tracing explicitly so credentials/flags never authorize external calls.
            with import_module("langsmith").tracing_context(enabled=False):
                raw = await compiled.ainvoke(
                    WorkflowState(request=expected).model_dump(),
                    config={"recursion_limit": expected.limits.max_steps + 1},
                )
            state = validate_state(raw, expected, WorkflowPhase.COMPLETED)
        except RuntimeFoundationError:
            raise
        except Exception as exc:
            raise ExecutionFailureError(
                "LangGraph execution failed; inspect the internal cause."
            ) from exc
        return RuntimeOutput(
            workflow_id=expected.workflow_id,
            runtime=RuntimeId.LANGGRAPH,
            result=state.result,
            transitions=state.transitions,
        )


class CrewAIRuntime(_ConstructionOnlyRuntime):
    """Construct a real task definition without an agent, LLM, crew, or kickoff."""

    def __init__(self) -> None:
        """Construct a static definition; never infer provider choices from keys."""
        super().__init__(
            RuntimeId.CREWAI,
            "crewai",
            "crewai",
            "Task",
            description="Runtime foundation construction probe; do not execute.",
            expected_output="Construction evidence only.",
        )


class GoogleADKRuntime(_ConstructionOnlyRuntime):
    """Construct a real BaseAgent definition without a runner or model."""

    def __init__(self) -> None:
        """Construct an agent definition; no distributed execution is implied."""
        super().__init__(
            RuntimeId.GOOGLE_ADK,
            "google-adk",
            "google.adk.agents",
            "BaseAgent",
            name="foundation_probe",
            sub_agents=[],
        )
