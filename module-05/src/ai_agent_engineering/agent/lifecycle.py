"""Finite lifecycle control for autonomous agent execution."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from ai_agent_engineering.errors import InvalidStateTransitionError
from ai_agent_engineering.models import AgentRunState, AgentStatus

_ALLOWED_TRANSITIONS: Final[Mapping[AgentStatus, frozenset[AgentStatus]]] = {
    AgentStatus.RECEIVED: frozenset(
        {
            AgentStatus.INITIALIZED,
            AgentStatus.FAILED,
        }
    ),
    AgentStatus.INITIALIZED: frozenset(
        {
            AgentStatus.CONTEXT_READY,
            AgentStatus.FAILED,
        }
    ),
    AgentStatus.CONTEXT_READY: frozenset(
        {
            AgentStatus.REASONING,
            AgentStatus.FAILED,
        }
    ),
    AgentStatus.REASONING: frozenset(
        {
            AgentStatus.TOOL_SELECTED,
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
            AgentStatus.TIMED_OUT,
            AgentStatus.BUDGET_EXHAUSTED,
        }
    ),
    AgentStatus.TOOL_SELECTED: frozenset(
        {
            AgentStatus.VALIDATED,
            AgentStatus.FAILED,
            AgentStatus.TIMED_OUT,
        }
    ),
    AgentStatus.VALIDATED: frozenset(
        {
            AgentStatus.EXECUTING,
            AgentStatus.FAILED,
            AgentStatus.TIMED_OUT,
        }
    ),
    AgentStatus.EXECUTING: frozenset(
        {
            AgentStatus.OBSERVED,
            AgentStatus.FAILED,
            AgentStatus.TIMED_OUT,
        }
    ),
    AgentStatus.OBSERVED: frozenset(
        {
            AgentStatus.REASONING,
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
            AgentStatus.TIMED_OUT,
            AgentStatus.BUDGET_EXHAUSTED,
        }
    ),
    AgentStatus.COMPLETED: frozenset(),
    AgentStatus.FAILED: frozenset(),
    AgentStatus.TIMED_OUT: frozenset(),
    AgentStatus.BUDGET_EXHAUSTED: frozenset(),
}


def allowed_transitions(status: AgentStatus) -> frozenset[AgentStatus]:
    """Return lifecycle states reachable directly from a status.

    Args:
        status: Current lifecycle status.

    Returns:
        Immutable set of directly permitted target states.
    """
    return _ALLOWED_TRANSITIONS[status]


def transition(
    state: AgentRunState,
    target_status: AgentStatus,
) -> AgentRunState:
    """Apply one validated lifecycle transition.

    The application owns lifecycle authority. Provider, model, memory, and tool
    output must pass through this function rather than mutating lifecycle state
    directly.

    Args:
        state: Mutable application-owned run state.
        target_status: Requested next lifecycle status.

    Returns:
        The same state instance after the valid transition.

    Raises:
        InvalidStateTransitionError: If the requested transition is forbidden.
    """
    if not isinstance(target_status, AgentStatus):
        raise InvalidStateTransitionError(
            current_status=state.status.value,
            target_status=str(target_status),
        )

    if target_status not in allowed_transitions(state.status):
        raise InvalidStateTransitionError(
            current_status=state.status.value,
            target_status=target_status.value,
        )

    state.status = target_status
    return state
