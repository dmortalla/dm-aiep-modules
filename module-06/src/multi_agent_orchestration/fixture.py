"""A single-step offline fixture; never a substitute for framework execution."""

from .contracts import (
    AgentTaskResult,
    ExecutionStatus,
    RuntimeId,
    RuntimeInfo,
    RuntimeOutput,
    WorkflowRequest,
)
from .errors import InvalidWorkflowRequestError


class FixtureRuntime:
    """Return a fixed result without evaluating or copying caller instructions."""

    @property
    def info(self) -> RuntimeInfo:
        """Return application-owned deterministic execution metadata."""
        return RuntimeInfo(
            runtime=RuntimeId.FIXTURE,
            execution_available=True,
            evidence_class="deterministic_fixture",
        )

    async def execute(self, request: WorkflowRequest) -> RuntimeOutput:
        """Complete exactly one fixture step with zero model/network calls.

        Args:
            request: Application request; the runtime must explicitly be fixture.

        Returns:
            A fixed candidate result carrying the request's identities.

        Raises:
            InvalidWorkflowRequestError: A different runtime was requested.
        """
        if request.runtime != RuntimeId.FIXTURE:
            raise InvalidWorkflowRequestError(
                "Fixture requires explicit fixture selection."
            )
        return RuntimeOutput(
            workflow_id=request.workflow_id,
            runtime=RuntimeId.FIXTURE,
            result=AgentTaskResult(
                task_id=request.task.task_id,
                agent_id="fixture_agent",
                status=ExecutionStatus.COMPLETED,
                output="Fixture task completed; no model or external calls were made.",
            ),
        )
