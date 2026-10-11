"""Explicit, closed runtime selection; environment credentials are irrelevant."""

from .contracts import RuntimeId
from .errors import UnknownRuntimeError
from .fixture import FixtureRuntime
from .runtime import Runtime


def create_runtime(identifier: RuntimeId | str = RuntimeId.FIXTURE) -> Runtime:
    """Construct the selected runtime without automatic fallback.

    Args:
        identifier: Explicit runtime choice; omission selects the offline fixture.

    Returns:
        An application-owned adapter implementing Runtime.

    Raises:
        UnknownRuntimeError: The identifier is unknown or incorrectly typed.
        RuntimeUnavailableError: The selected SDK is unavailable.
        ExecutionFailureError: SDK construction fails.
    """
    try:
        selected = RuntimeId(identifier)
    except (ValueError, TypeError) as exc:
        raise UnknownRuntimeError(
            "Unknown runtime; choose fixture, langgraph, crewai, or google_adk."
        ) from exc
    if selected == RuntimeId.FIXTURE:
        return FixtureRuntime()
    # Avoid even importing framework adapter machinery on the default path.
    from .adapters import CrewAIRuntime, GoogleADKRuntime, LangGraphRuntime

    constructors = {
        RuntimeId.LANGGRAPH: LangGraphRuntime,
        RuntimeId.CREWAI: CrewAIRuntime,
        RuntimeId.GOOGLE_ADK: GoogleADKRuntime,
    }
    return constructors[selected]()
