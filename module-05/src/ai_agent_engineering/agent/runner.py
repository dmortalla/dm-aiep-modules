"""Bounded deterministic ReAct runner for Module 5."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ai_agent_engineering.agent.lifecycle import transition
from ai_agent_engineering.agent.react import (
    AgentDecision,
    DecisionKind,
    DecisionRecord,
)
from ai_agent_engineering.models import AgentRunState, AgentStatus
from ai_agent_engineering.tools import ToolRegistry

DecisionProvider = Callable[[AgentRunState], AgentDecision]


class AgentExecutionError(RuntimeError):
    """Raised when bounded agent execution cannot safely continue."""


def _prepare_state(state: AgentRunState) -> None:
    """Advance a fresh state to its reasoning phase."""
    if state.status is not AgentStatus.RECEIVED:
        raise AgentExecutionError(
            "Agent runner requires a fresh RECEIVED state."
        )

    transition(state, AgentStatus.INITIALIZED)
    transition(state, AgentStatus.CONTEXT_READY)
    transition(state, AgentStatus.REASONING)


def run_agent(
    state: AgentRunState,
    registry: ToolRegistry,
    decide: DecisionProvider,
) -> tuple[AgentRunState, tuple[DecisionRecord, ...]]:
    """Execute a bounded application-controlled ReAct loop.

    The decision provider may propose actions, but lifecycle authority,
    execution budgets, tool authorization, argument validation, and actual
    execution remain application-owned.

    Args:
        state: Fresh application-owned run state.
        registry: Application-owned allowlisted tool registry.
        decide: Decision provider used to propose the next action.

    Returns:
        Final run state and immutable application-visible decision records.

    Raises:
        AgentExecutionError: If execution begins from an invalid state or the
            decision provider returns an invalid object.
        Tool-related exceptions: If a proposed tool call fails application
            authorization or validation.
    """
    _prepare_state(state)
    records: list[DecisionRecord] = []

    while not state.is_terminal:
        if state.steps_remaining <= 0:
            transition(state, AgentStatus.BUDGET_EXHAUSTED)
            state.terminal_failure = "Execution-step budget exhausted."
            break

        decision = decide(state)

        if not isinstance(decision, AgentDecision):
            transition(state, AgentStatus.FAILED)
            state.terminal_failure = (
                "Decision provider returned an invalid decision object."
            )
            raise AgentExecutionError(state.terminal_failure)

        state.consume_step()

        records.append(
            DecisionRecord(
                step=state.current_step,
                kind=decision.kind,
                rationale=decision.rationale,
                tool_name=decision.tool_name,
            )
        )

        if decision.kind is DecisionKind.FINISH:
            state.final_result = decision.final_result
            transition(state, AgentStatus.COMPLETED)
            break

        transition(state, AgentStatus.TOOL_SELECTED)

        assert decision.tool_name is not None
        assert decision.arguments is not None

        tool, validated = registry.validate_call(
            decision.tool_name,
            decision.arguments,
        )

        transition(state, AgentStatus.VALIDATED)
        transition(state, AgentStatus.EXECUTING)

        observation: Any = tool.handler(validated)

        state.selected_tools.append(tool.name)
        state.observations.append(
            {
                "tool": tool.name,
                "result": observation,
            }
        )

        transition(state, AgentStatus.OBSERVED)

        if state.steps_remaining <= 0:
            transition(state, AgentStatus.BUDGET_EXHAUSTED)
            state.terminal_failure = "Execution-step budget exhausted."
            break

        transition(state, AgentStatus.REASONING)

    return state, tuple(records)


def build_deterministic_decider(goal: str) -> DecisionProvider:
    """Build a deterministic Story 3 decision provider.

    This local provider demonstrates the ReAct execution mechanics without
    claiming live model reasoning.

    Args:
        goal: Goal used to choose the deterministic demonstration path.

    Returns:
        Callable that proposes bounded application-visible decisions.
    """
    normalized = goal.casefold()

    def decide(state: AgentRunState) -> AgentDecision:
        """Return the next deterministic demonstration decision."""
        if not state.observations:
            if "calculate" in normalized or "math" in normalized:
                return AgentDecision(
                    kind=DecisionKind.TOOL,
                    rationale="Use the calculator for the requested arithmetic.",
                    tool_name="calculator",
                    arguments={
                        "operation": "multiply",
                        "left": 6,
                        "right": 7,
                    },
                )

            if "note" in normalized or "context" in normalized:
                return AgentDecision(
                    kind=DecisionKind.TOOL,
                    rationale="Retrieve the bounded safety note.",
                    tool_name="note_lookup",
                    arguments={"key": "safety_rule"},
                )

            return AgentDecision(
                kind=DecisionKind.TOOL,
                rationale="Use bounded local knowledge for the requested topic.",
                tool_name="knowledge_lookup",
                arguments={"topic": "react"},
            )

        observation = state.observations[-1]

        return AgentDecision(
            kind=DecisionKind.FINISH,
            rationale="The bounded tool observation is sufficient to finish.",
            final_result=f"Completed with observation: {observation['result']}",
        )

    return decide
