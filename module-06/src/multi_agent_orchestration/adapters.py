"""Lazy construction probes for real SDK objects; no framework execution claim."""

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version

from .contracts import RuntimeId, RuntimeInfo, RuntimeOutput, WorkflowRequest
from .errors import ExecutionFailureError, RuntimeUnavailableError


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
    """Construct a real StateGraph builder without compiling/invoking a workflow."""

    def __init__(self) -> None:
        """Construct the private SDK object without a model or telemetry client."""
        super().__init__(
            RuntimeId.LANGGRAPH,
            "langgraph",
            "langgraph.graph",
            "StateGraph",
            state_schema=dict,
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
