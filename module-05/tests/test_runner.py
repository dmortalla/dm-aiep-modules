"""Tests for bounded ReAct execution."""

import pytest
from ai_agent_engineering.agent.react import AgentDecision, DecisionKind
from ai_agent_engineering.agent.runner import (
    AgentExecutionError,
    build_deterministic_decider,
    run_agent,
)
from ai_agent_engineering.models import AgentRunState, AgentStatus
from ai_agent_engineering.tools import (
    ToolValidationError,
    UnknownToolError,
    build_default_registry,
)


def test_runner_executes_tool_observes_and_finishes() -> None:
    """The deterministic loop performs tool -> observation -> finish."""
    state = AgentRunState(
        goal="Calculate the demonstration math.",
        max_steps=4,
    )

    final_state, records = run_agent(
        state,
        build_default_registry(),
        build_deterministic_decider(state.goal),
    )

    assert final_state.status is AgentStatus.COMPLETED
    assert final_state.current_step == 2
    assert final_state.selected_tools == ["calculator"]
    assert final_state.observations[0]["result"]["result"] == 42.0
    assert final_state.final_result is not None
    assert [record.kind for record in records] == [
        DecisionKind.TOOL,
        DecisionKind.FINISH,
    ]


def test_runner_supports_multi_step_reasoning_cycle() -> None:
    """An observation returns control to reasoning for another decision."""
    decisions = iter(
        (
            AgentDecision(
                kind=DecisionKind.TOOL,
                rationale="Retrieve bounded knowledge.",
                tool_name="knowledge_lookup",
                arguments={"topic": "react"},
            ),
            AgentDecision(
                kind=DecisionKind.TOOL,
                rationale="Retrieve the safety note.",
                tool_name="note_lookup",
                arguments={"key": "safety_rule"},
            ),
            AgentDecision(
                kind=DecisionKind.FINISH,
                rationale="Both observations are sufficient.",
                final_result="Two-step tool workflow completed.",
            ),
        )
    )

    state = AgentRunState(
        goal="Use two tools before finishing.",
        max_steps=5,
    )

    final_state, records = run_agent(
        state,
        build_default_registry(),
        lambda _: next(decisions),
    )

    assert final_state.status is AgentStatus.COMPLETED
    assert final_state.current_step == 3
    assert final_state.selected_tools == [
        "knowledge_lookup",
        "note_lookup",
    ]
    assert len(final_state.observations) == 2
    assert len(records) == 3


def test_execution_budget_terminates_loop() -> None:
    """A provider cannot continue beyond the application-owned step budget."""
    state = AgentRunState(
        goal="Keep trying forever.",
        max_steps=1,
    )

    def always_use_tool(_: AgentRunState) -> AgentDecision:
        return AgentDecision(
            kind=DecisionKind.TOOL,
            rationale="Attempt another bounded lookup.",
            tool_name="knowledge_lookup",
            arguments={"topic": "react"},
        )

    final_state, records = run_agent(
        state,
        build_default_registry(),
        always_use_tool,
    )

    assert final_state.status is AgentStatus.BUDGET_EXHAUSTED
    assert final_state.current_step == 1
    assert len(records) == 1
    assert len(final_state.observations) == 1


def test_unknown_tool_proposal_cannot_gain_authority() -> None:
    """A decision provider cannot invent a new executable tool."""
    state = AgentRunState(
        goal="Attempt forged authority.",
        max_steps=3,
    )

    def forge_tool(_: AgentRunState) -> AgentDecision:
        return AgentDecision(
            kind=DecisionKind.TOOL,
            rationale="Propose an untrusted tool name.",
            tool_name="shell",
            arguments={"command": "whoami"},
        )

    with pytest.raises(UnknownToolError):
        run_agent(
            state,
            build_default_registry(),
            forge_tool,
        )

    assert state.status is AgentStatus.TOOL_SELECTED
    assert state.selected_tools == []
    assert state.observations == []


def test_invalid_tool_arguments_never_execute() -> None:
    """Schema-invalid provider arguments fail before tool execution."""
    state = AgentRunState(
        goal="Attempt argument injection.",
        max_steps=3,
    )

    def inject_argument(_: AgentRunState) -> AgentDecision:
        return AgentDecision(
            kind=DecisionKind.TOOL,
            rationale="Propose unexpected calculator input.",
            tool_name="calculator",
            arguments={
                "operation": "add",
                "left": 1,
                "right": 2,
                "command": "whoami",
            },
        )

    with pytest.raises(ToolValidationError):
        run_agent(
            state,
            build_default_registry(),
            inject_argument,
        )

    assert state.selected_tools == []
    assert state.observations == []


def test_invalid_decision_object_fails_run() -> None:
    """Malformed provider output cannot become an executable decision."""
    state = AgentRunState(
        goal="Reject malformed provider output.",
        max_steps=3,
    )

    def malformed(_: AgentRunState):
        return {
            "kind": "tool",
            "tool_name": "calculator",
        }

    with pytest.raises(AgentExecutionError):
        run_agent(
            state,
            build_default_registry(),
            malformed,  # type: ignore[arg-type]
        )

    assert state.status is AgentStatus.FAILED
    assert state.selected_tools == []


def test_runner_rejects_nonfresh_state() -> None:
    """A partially controlled state cannot be silently reused."""
    state = AgentRunState(goal="Reject unsafe resume.")
    state.status = AgentStatus.REASONING

    with pytest.raises(AgentExecutionError):
        run_agent(
            state,
            build_default_registry(),
            build_deterministic_decider(state.goal),
        )
