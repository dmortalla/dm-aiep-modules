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
from ai_agent_engineering.resilience import (
    RetryExhaustedError,
    run_with_fallback,
    run_with_retry,
)
from ai_agent_engineering.tools import ToolRegistry

DecisionProvider = Callable[[AgentRunState], AgentDecision]

DEFAULT_DECISION_MAX_ATTEMPTS = 3
DEFAULT_DECISION_RETRY_ON: tuple[type[Exception], ...] = (ConnectionError,)


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


def _decide_with_reliability(
    state: AgentRunState,
    decide: DecisionProvider,
    *,
    fallback_decide: DecisionProvider | None,
    max_attempts: int,
    retry_on: tuple[type[Exception], ...],
) -> AgentDecision:
    """Obtain one decision through bounded retry and optional fallback.

    The decision provider is synchronous, so this boundary intentionally does
    not claim cancellable timeout enforcement. Genuine deadlines remain at
    genuinely cancellable provider/async boundaries.

    Args:
        state: Application-owned run state supplied to decision providers.
        decide: Preferred decision provider.
        fallback_decide: Optional application-owned recovery provider.
        max_attempts: Maximum preferred-provider attempts per decision.
        retry_on: Explicit exception types eligible for retry.

    Returns:
        Decision produced by the preferred or fallback provider.

    Raises:
        RetryExhaustedError: If retryable failures exhaust the attempt budget
            and no fallback provider is configured.
        Exception: If a non-retryable provider failure or fallback failure
            occurs.
    """

    def primary() -> AgentDecision:
        try:
            result = run_with_retry(
                lambda: decide(state),
                max_attempts=max_attempts,
                retry_on=retry_on,
            )
        except RetryExhaustedError as exc:
            state.retry_count += max(exc.attempts - 1, 0)
            raise

        state.retry_count += max(result.attempts - 1, 0)
        return result.value

    if fallback_decide is None:
        return primary()

    def fallback() -> AgentDecision:
        state.fallback_history.append("decision_provider")
        return fallback_decide(state)

    return run_with_fallback(
        primary,
        fallback,
        fallback_on=(RetryExhaustedError,),
    ).value


def run_agent(
    state: AgentRunState,
    registry: ToolRegistry,
    decide: DecisionProvider,
    *,
    fallback_decide: DecisionProvider | None = None,
    decision_max_attempts: int = DEFAULT_DECISION_MAX_ATTEMPTS,
    decision_retry_on: tuple[type[Exception], ...] = DEFAULT_DECISION_RETRY_ON,
) -> tuple[AgentRunState, tuple[DecisionRecord, ...]]:
    """Execute a bounded application-controlled ReAct loop.

    The decision provider may propose actions, but lifecycle authority,
    execution budgets, tool authorization, argument validation, and actual
    execution remain application-owned. Decision-provider calls use bounded,
    exception-selective retry and may use an explicit application-owned
    fallback provider after retry exhaustion.

    The current DecisionProvider contract is synchronous. This runner therefore
    does not claim a cancellable timeout around decision execution; genuine
    timeout enforcement belongs at an awaitable or provider boundary that can
    actually be cancelled.

    Args:
        state: Fresh application-owned run state.
        registry: Application-owned allowlisted tool registry.
        decide: Preferred decision provider used to propose the next action.
        fallback_decide: Optional application-owned provider used only after
            retryable preferred-provider failures exhaust their attempt budget.
        decision_max_attempts: Maximum preferred-provider attempts per decision.
        decision_retry_on: Explicit exception types eligible for retry.

    Returns:
        Final run state and immutable application-visible decision records.

    Raises:
        AgentExecutionError: If execution begins from an invalid state or the
            decision provider returns an invalid object.
        RetryExhaustedError: If retryable decision-provider failures exhaust
            the attempt budget and no fallback provider is configured.
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

        decision = _decide_with_reliability(
            state,
            decide,
            fallback_decide=fallback_decide,
            max_attempts=decision_max_attempts,
            retry_on=decision_retry_on,
        )

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
