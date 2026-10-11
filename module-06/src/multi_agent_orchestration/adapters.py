"""Lazy SDK boundaries for deterministic graph execution and construction probes."""

import asyncio
import json
import os
import subprocess
import sys
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import ValidationError

from .collaboration import expected_messages
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
    InvalidRuntimeOutputError,
    InvalidWorkflowRequestError,
    RuntimeFoundationError,
    RuntimeUnavailableError,
    StepBudgetExceededError,
)
from .orchestration import expected_orchestration


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
    """Execute a real deterministic Crew in an isolated, cancellable local process."""

    def __init__(self) -> None:
        """Check availability without CrewAI's import-time analytics side effect."""
        try:
            if import_module("importlib.util").find_spec("crewai") is None:
                raise ModuleNotFoundError("CrewAI unavailable")
            framework_version = version("crewai")
        except (ImportError, PackageNotFoundError) as exc:
            raise RuntimeUnavailableError(
                "crewai is unavailable; synchronize the accepted uv lock."
            ) from exc
        self._info = RuntimeInfo(
            runtime=RuntimeId.CREWAI,
            execution_available=True,
            evidence_class="deterministic_collaboration",
            framework_version=framework_version,
        )

    async def _invoke(self, expected: WorkflowRequest) -> object:
        """Reap the child before deleting temporary logs, including cancellation."""
        with TemporaryDirectory(prefix="module06-crewai-") as directory:
            local_data = Path(directory, "AppData", "Local")
            roaming_data = Path(directory, "AppData", "Roaming")
            local_data.mkdir(parents=True)
            roaming_data.mkdir(parents=True)
            environment = {
                key: os.environ[key]
                for key in ("SYSTEMROOT", "WINDIR")
                if key in os.environ
            }
            environment.update(
                TEMP=directory,
                TMP=directory,
                HOME=directory,
                USERPROFILE=directory,
                LOCALAPPDATA=str(local_data),
                APPDATA=str(roaming_data),
                CREWAI_STORAGE_DIR=directory,
                CREWAI_TESTING="true",
                CREWAI_TRACING_ENABLED="false",
                CREWAI_DISABLE_TELEMETRY="true",
                CREWAI_DISABLE_TRACKING="true",
                OTEL_SDK_DISABLED="true",
                LITELLM_LOCAL_MODEL_COST_MAP="true",
                DO_NOT_TRACK="1",
                LANGSMITH_TRACING="false",
                LANGCHAIN_TRACING_V2="false",
            )
            spawning = asyncio.create_task(
                asyncio.create_subprocess_exec(
                    sys.executable,
                    "-I",
                    "-m",
                    "multi_agent_orchestration._crewai_worker",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=environment,
                    cwd=directory,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            )
            try:
                process = await asyncio.shield(spawning)
            except asyncio.CancelledError:
                # Cancellation during spawn must still acquire/reap the child.
                process = await spawning
                if process.returncode is None:
                    process.kill()
                await process.communicate()
                raise
            try:
                stdout, stderr = await process.communicate(
                    expected.model_dump_json().encode()
                )
                if process.returncode != 0 or len(stdout) > 16_000:
                    raise ExecutionFailureError(
                        "CrewAI worker failed its bounded process contract."
                    ) from RuntimeError(stderr.decode(errors="replace")[:4096])
                packet = json.loads(stdout)
                if not isinstance(packet, dict) or set(packet) != {"output"}:
                    if (
                        isinstance(packet, dict)
                        and packet.get("error_type") == "InvalidRuntimeOutputError"
                    ):
                        raise InvalidRuntimeOutputError(
                            "CrewAI collaborator/state validation failed."
                        ) from RuntimeError(str(packet)[:4096])
                    raise ExecutionFailureError(
                        "CrewAI worker failed; inspect the internal cause."
                    ) from RuntimeError(str(packet)[:4096])
                return packet["output"]
            finally:
                if process.returncode is None:
                    process.kill()
                await process.communicate()

    async def execute(self, request: WorkflowRequest) -> RuntimeOutput:
        """Run three offline collaborative tasks under application-owned budgets.

        Raises:
            InvalidWorkflowRequestError: Explicit runtime or request schema fails.
            StepBudgetExceededError: Fewer than three tasks/messages/steps allowed.
            RuntimeFoundationError: Process execution or output validation fails.
        """
        try:
            expected = WorkflowRequest.model_validate(request.model_dump())
        except ValidationError as exc:
            raise InvalidWorkflowRequestError(
                "CrewAI request failed contract validation."
            ) from exc
        if expected.runtime != RuntimeId.CREWAI:
            raise InvalidWorkflowRequestError(
                "CrewAI requires explicit matching runtime selection."
            )
        if (
            min(
                expected.limits.max_steps,
                expected.limits.max_tasks,
                expected.limits.max_messages,
            )
            < 3
        ):
            raise StepBudgetExceededError(
                "CrewAI collaboration requires three authorized steps/tasks/messages."
            )
        try:
            output = RuntimeOutput.model_validate(await self._invoke(expected))
            messages = expected_messages(expected)
            if (
                output.workflow_id != expected.workflow_id
                or output.runtime != RuntimeId.CREWAI
                or output.result.task_id != expected.task.task_id
                or output.result.agent_id != "critic"
                or output.result.output != messages[-1].content
                or output.transitions
                or output.collaboration != messages
            ):
                raise InvalidRuntimeOutputError(
                    "CrewAI output contradicts authorized collaboration."
                )
            return output
        except RuntimeFoundationError:
            raise
        except ValidationError as exc:
            raise InvalidRuntimeOutputError(
                "CrewAI runtime output failed validation."
            ) from exc
        except Exception as exc:
            raise ExecutionFailureError(
                "CrewAI execution failed; inspect the internal cause."
            ) from exc


class GoogleADKRuntime(_ConstructionOnlyRuntime):
    """Execute a native ADK Workflow in an isolated, cancellable local process."""

    def __init__(self) -> None:
        """Check availability while keeping SDK execution inside the isolated child."""
        try:
            if import_module("importlib.util").find_spec("google.adk.workflow") is None:
                raise ModuleNotFoundError("Google ADK unavailable")
            framework_version = version("google-adk")
        except (ImportError, PackageNotFoundError) as exc:
            raise RuntimeUnavailableError(
                "google-adk is unavailable; synchronize the accepted uv lock."
            ) from exc
        self._info = RuntimeInfo(
            runtime=RuntimeId.GOOGLE_ADK,
            execution_available=True,
            evidence_class="deterministic_multi_agent",
            framework_version=framework_version,
        )

    async def _invoke(self, expected: WorkflowRequest) -> object:
        """Reap the child before deleting temporary logs, including cancellation."""
        with TemporaryDirectory(prefix="module06-adk-") as directory:
            local_data = Path(directory, "AppData", "Local")
            roaming_data = Path(directory, "AppData", "Roaming")
            local_data.mkdir(parents=True)
            roaming_data.mkdir(parents=True)
            environment = {
                key: os.environ[key]
                for key in ("SYSTEMROOT", "WINDIR")
                if key in os.environ
            }
            environment.update(
                TEMP=directory,
                TMP=directory,
                HOME=directory,
                USERPROFILE=directory,
                LOCALAPPDATA=str(local_data),
                APPDATA=str(roaming_data),
                ADK_TELEMETRY_IGNORE_RUN_CONFIG="false",
                ADK_EXPERIMENTAL_TELEMETRY="false",
                OTEL_SDK_DISABLED="true",
                LITELLM_LOCAL_MODEL_COST_MAP="true",
                DO_NOT_TRACK="1",
                LANGSMITH_TRACING="false",
                LANGCHAIN_TRACING_V2="false",
            )
            spawning = asyncio.create_task(
                asyncio.create_subprocess_exec(
                    sys.executable,
                    "-I",
                    "-m",
                    "multi_agent_orchestration._adk_worker",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=environment,
                    cwd=directory,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            )
            try:
                process = await asyncio.shield(spawning)
            except asyncio.CancelledError:
                # Cancellation during spawn must still acquire/reap the child.
                process = await spawning
                if process.returncode is None:
                    process.kill()
                await process.communicate()
                raise
            try:
                stdout, stderr = await process.communicate(
                    expected.model_dump_json().encode()
                )
                if process.returncode != 0 or len(stdout) > 16_000:
                    raise ExecutionFailureError(
                        "Google ADK worker failed its bounded process contract."
                    ) from RuntimeError(stderr.decode(errors="replace")[:4096])
                packet = json.loads(stdout)
                if not isinstance(packet, dict) or set(packet) != {"output"}:
                    if (
                        isinstance(packet, dict)
                        and packet.get("error_type") == "InvalidRuntimeOutputError"
                    ):
                        raise InvalidRuntimeOutputError(
                            "Google ADK collaborator/state validation failed."
                        ) from RuntimeError(str(packet)[:4096])
                    raise ExecutionFailureError(
                        "Google ADK worker failed; inspect the internal cause."
                    ) from RuntimeError(str(packet)[:4096])
                return packet["output"]
            finally:
                if process.returncode is None:
                    process.kill()
                await process.communicate()

    async def execute(self, request: WorkflowRequest) -> RuntimeOutput:
        """Run three offline ADK roles under application-owned budgets.

        Raises:
            InvalidWorkflowRequestError: Explicit runtime or request schema fails.
            StepBudgetExceededError: Fewer than three tasks/messages/steps allowed.
            RuntimeFoundationError: Process execution or output validation fails.
        """
        try:
            expected = WorkflowRequest.model_validate(request.model_dump())
        except ValidationError as exc:
            raise InvalidWorkflowRequestError(
                "Google ADK request failed contract validation."
            ) from exc
        if expected.runtime != RuntimeId.GOOGLE_ADK:
            raise InvalidWorkflowRequestError(
                "Google ADK requires explicit matching runtime selection."
            )
        if (
            min(
                expected.limits.max_steps,
                expected.limits.max_tasks,
                expected.limits.max_messages,
            )
            < 3
        ):
            raise StepBudgetExceededError(
                "Google ADK requires three authorized steps/tasks/messages."
            )
        try:
            raw = await self._invoke(expected)
            output = RuntimeOutput.model_validate(
                raw.model_dump() if isinstance(raw, RuntimeOutput) else raw
            )
            messages = expected_orchestration(expected)
            if (
                output.workflow_id != expected.workflow_id
                or output.runtime != RuntimeId.GOOGLE_ADK
                or output.result.task_id != expected.task.task_id
                or output.result.agent_id != "adk_validator"
                or output.result.output != messages[-1].content
                or output.transitions
                or output.collaboration
                or output.orchestration != messages
            ):
                raise InvalidRuntimeOutputError(
                    "Google ADK output contradicts authorized orchestration."
                )
            return output
        except RuntimeFoundationError:
            raise
        except ValidationError as exc:
            raise InvalidRuntimeOutputError(
                "Google ADK runtime output failed validation."
            ) from exc
        except Exception as exc:
            raise ExecutionFailureError(
                "Google ADK execution failed; inspect the internal cause."
            ) from exc
