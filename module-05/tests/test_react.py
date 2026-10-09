"""Tests for application-visible ReAct decision contracts."""

import pytest
from ai_agent_engineering.agent.react import AgentDecision, DecisionKind


def test_tool_decision_requires_structured_call() -> None:
    """A valid tool decision contains an explicit structured action."""
    decision = AgentDecision(
        kind=DecisionKind.TOOL,
        rationale="Use bounded arithmetic.",
        tool_name="calculator",
        arguments={
            "operation": "add",
            "left": 1,
            "right": 2,
        },
    )

    assert decision.tool_name == "calculator"
    assert decision.arguments is not None


def test_finish_decision_requires_result() -> None:
    """A finish decision carries a visible final result."""
    decision = AgentDecision(
        kind=DecisionKind.FINISH,
        rationale="The goal is satisfied.",
        final_result="Done.",
    )

    assert decision.final_result == "Done."


@pytest.mark.parametrize(
    "decision",
    [
        lambda: AgentDecision(
            kind=DecisionKind.TOOL,
            rationale="Missing tool.",
            arguments={},
        ),
        lambda: AgentDecision(
            kind=DecisionKind.TOOL,
            rationale="Missing arguments.",
            tool_name="calculator",
        ),
        lambda: AgentDecision(
            kind=DecisionKind.FINISH,
            rationale="Missing result.",
        ),
        lambda: AgentDecision(
            kind=DecisionKind.FINISH,
            rationale="Invalid mixed decision.",
            tool_name="calculator",
            arguments={},
            final_result="Done.",
        ),
    ],
)
def test_invalid_decision_shapes_are_rejected(decision) -> None:
    """Malformed provider-like decisions fail before execution."""
    with pytest.raises(ValueError):
        decision()


def test_reasoning_record_is_application_visible_not_private_cot() -> None:
    """Decision rationale remains concise application-visible metadata."""
    decision = AgentDecision(
        kind=DecisionKind.FINISH,
        rationale="The validated observation satisfies the goal.",
        final_result="Complete.",
    )

    assert decision.rationale == (
        "The validated observation satisfies the goal."
    )
