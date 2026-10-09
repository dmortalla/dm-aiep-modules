"""Tests for Module 5 lifecycle control."""

import pytest
from ai_agent_engineering.agent.lifecycle import allowed_transitions, transition
from ai_agent_engineering.errors import InvalidStateTransitionError
from ai_agent_engineering.models import AgentRunState, AgentStatus


def test_happy_path_reaches_completed() -> None:
    """A valid bounded lifecycle can reach successful completion."""
    state = AgentRunState(goal="Calculate a result.")

    path = (
        AgentStatus.INITIALIZED,
        AgentStatus.CONTEXT_READY,
        AgentStatus.REASONING,
        AgentStatus.TOOL_SELECTED,
        AgentStatus.VALIDATED,
        AgentStatus.EXECUTING,
        AgentStatus.OBSERVED,
        AgentStatus.COMPLETED,
    )

    for target in path:
        transition(state, target)

    assert state.status is AgentStatus.COMPLETED
    assert state.is_terminal is True


def test_observation_can_continue_reasoning() -> None:
    """An observation can return to reasoning for multi-step execution."""
    state = AgentRunState(goal="Complete two steps.")
    state.status = AgentStatus.OBSERVED

    transition(state, AgentStatus.REASONING)

    assert state.status is AgentStatus.REASONING


@pytest.mark.parametrize(
    "terminal_status",
    [
        AgentStatus.COMPLETED,
        AgentStatus.FAILED,
        AgentStatus.TIMED_OUT,
        AgentStatus.BUDGET_EXHAUSTED,
    ],
)
def test_terminal_states_have_no_outgoing_transitions(
    terminal_status: AgentStatus,
) -> None:
    """Terminal states cannot authorize additional lifecycle work."""
    assert allowed_transitions(terminal_status) == frozenset()


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    [
        (AgentStatus.RECEIVED, AgentStatus.EXECUTING),
        (AgentStatus.INITIALIZED, AgentStatus.COMPLETED),
        (AgentStatus.TOOL_SELECTED, AgentStatus.OBSERVED),
        (AgentStatus.COMPLETED, AgentStatus.REASONING),
        (AgentStatus.FAILED, AgentStatus.INITIALIZED),
        (AgentStatus.TIMED_OUT, AgentStatus.REASONING),
        (AgentStatus.BUDGET_EXHAUSTED, AgentStatus.REASONING),
    ],
)
def test_invalid_transition_is_rejected(
    current_status: AgentStatus,
    target_status: AgentStatus,
) -> None:
    """Invalid transitions fail deterministically."""
    state = AgentRunState(goal="Test lifecycle.")
    state.status = current_status

    with pytest.raises(InvalidStateTransitionError) as exc_info:
        transition(state, target_status)

    assert exc_info.value.current_status == current_status.value
    assert exc_info.value.target_status == target_status.value
    assert state.status is current_status


def test_provider_like_string_cannot_be_used_as_transition() -> None:
    """Untrusted arbitrary text cannot become lifecycle authority."""
    state = AgentRunState(goal="Remain controlled.")

    with pytest.raises(InvalidStateTransitionError):
        transition(state, "executing")  # type: ignore[arg-type]

    assert state.status is AgentStatus.RECEIVED
