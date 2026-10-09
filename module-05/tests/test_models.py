"""Tests for Module 5 typed run-state contracts."""

import pytest
from ai_agent_engineering.models import AgentRunState, AgentStatus


def test_state_normalizes_goal_and_starts_received() -> None:
    """A valid run starts in RECEIVED with normalized goal text."""
    state = AgentRunState(goal="  Find the answer.  ")

    assert state.goal == "Find the answer."
    assert state.status is AgentStatus.RECEIVED
    assert state.current_step == 0
    assert state.steps_remaining == 8
    assert state.is_terminal is False
    assert state.run_id


@pytest.mark.parametrize("goal", ["", " ", "\n\t"])
def test_empty_goal_is_rejected(goal: str) -> None:
    """Empty goals cannot create autonomous runs."""
    with pytest.raises(ValueError, match="must not be empty"):
        AgentRunState(goal=goal)


@pytest.mark.parametrize("max_steps", [0, -1, -10])
def test_invalid_step_budget_is_rejected(max_steps: int) -> None:
    """Execution requires a positive bounded step budget."""
    with pytest.raises(ValueError, match="at least 1"):
        AgentRunState(goal="Do bounded work.", max_steps=max_steps)


def test_step_budget_is_consumed_without_exceeding_limit() -> None:
    """Step consumption cannot exceed the configured execution budget."""
    state = AgentRunState(goal="Do bounded work.", max_steps=2)

    state.consume_step()
    state.consume_step()

    assert state.current_step == 2
    assert state.steps_remaining == 0

    with pytest.raises(RuntimeError, match="budget is exhausted"):
        state.consume_step()

    assert state.current_step == 2


def test_mutable_state_collections_are_not_shared_between_runs() -> None:
    """Each run receives independent mutable state containers."""
    first = AgentRunState(goal="First.")
    second = AgentRunState(goal="Second.")

    first.observations.append("observation")
    first.selected_tools.append("calculator")
    first.short_term_context["key"] = "value"
    first.retrieved_long_term_memories.append("memory")
    first.episodic_events.append({"event": "created"})
    first.fallback_history.append("fallback")

    assert second.observations == []
    assert second.selected_tools == []
    assert second.short_term_context == {}
    assert second.retrieved_long_term_memories == []
    assert second.episodic_events == []
    assert second.fallback_history == []
