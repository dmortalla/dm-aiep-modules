"""Minimal asynchronous runtime boundary owned by the application."""

from typing import Protocol, runtime_checkable

from .contracts import RuntimeInfo, RuntimeOutput, WorkflowRequest


@runtime_checkable
class Runtime(Protocol):
    """Trusted adapter code returns untrusted, application-shaped candidates."""

    @property
    def info(self) -> RuntimeInfo:
        """Return construction capabilities, never framework-specific objects."""
        ...

    async def execute(self, request: WorkflowRequest) -> RuntimeOutput:
        """Execute a bounded request or fail explicitly without runtime fallback.

        Args:
            request: Validated application-owned request.

        Returns:
            Candidate output requiring application validation.

        Raises:
            RuntimeUnavailableError: Execution is not supported.
            ExecutionFailureError: Runtime execution fails.
        """
        ...
