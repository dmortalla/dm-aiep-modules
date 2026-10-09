"""Tests for reliability integrated into the primary ReAct runner."""

from collections.abc import Mapping
from typing import Any

import pytest
from ai_agent_engineering.agent.react import AgentDecision, DecisionKind
from ai_agent_engineering.agent.runner import run_agent
from ai_agent_engineering.models import AgentRunState, AgentStatus
from ai_agent_engineering.resilience import RetryExhaustedError
from ai_agent_engineering.tools import (
    ToolAuthorizationError,
    ToolDefinition,
    ToolRegistry,
    UnknownToolError,
    build_default_registry,
)


def _finish(message: str) -> AgentDecision:
    """Build one valid terminal decision."""
    return AgentDecision(
        kind=DecisionKind.FINISH,
        rationale="Finish after bounded decision-provider handling.",
        final_result=message,
    )


def test_runner_retries_transient_decision_failure() -> None:
    """Retryable decision failures recover inside the primary runner."""
    calls = 0
    state = AgentRunState(goal="Recover transient decision failure.")

    def flaky(_: AgentRunState) -> AgentDecision:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ConnectionError("temporary provider outage")
        return _finish("recovered")

    final_state, records = run_agent(
        state,
        build_default_registry(),
        flaky,
    )

    assert calls == 3
    assert final_state.status is AgentStatus.COMPLETED
    assert final_state.final_result == "recovered"
    assert final_state.retry_count == 2
    assert final_state.fallback_history == []
    assert len(records) == 1


def test_runner_does_not_retry_timeout_by_default() -> None:
    """Ambiguous synchronous timeouts are not automatically replayed."""
    calls = 0
    state = AgentRunState(goal="Do not duplicate ambiguous work.")

    def timed_out(_: AgentRunState) -> AgentDecision:
        nonlocal calls
        calls += 1
        raise TimeoutError("completion status unknown")

    with pytest.raises(TimeoutError, match="completion status unknown"):
        run_agent(
            state,
            build_default_registry(),
            timed_out,
        )

    assert calls == 1
    assert state.retry_count == 0
    assert state.fallback_history == []

def test_runner_does_not_retry_nonretryable_decision_failure() -> None:
    """Programming/provider-contract failures are not retried by default."""
    calls = 0
    state = AgentRunState(goal="Fail immediately.")

    def invalid(_: AgentRunState) -> AgentDecision:
        nonlocal calls
        calls += 1
        raise ValueError("not transient")

    with pytest.raises(ValueError, match="not transient"):
        run_agent(
            state,
            build_default_registry(),
            invalid,
        )

    assert calls == 1
    assert state.retry_count == 0
    assert state.fallback_history == []


def test_runner_uses_explicit_fallback_after_retry_exhaustion() -> None:
    """Fallback runs only after the preferred retry budget is exhausted."""
    primary_calls = 0
    fallback_calls = 0
    state = AgentRunState(goal="Use bounded recovery.")

    def unavailable(_: AgentRunState) -> AgentDecision:
        nonlocal primary_calls
        primary_calls += 1
        raise ConnectionError("provider unavailable")

    def local_fallback(_: AgentRunState) -> AgentDecision:
        nonlocal fallback_calls
        fallback_calls += 1
        return _finish("fallback result")

    final_state, records = run_agent(
        state,
        build_default_registry(),
        unavailable,
        fallback_decide=local_fallback,
    )

    assert primary_calls == 3
    assert fallback_calls == 1
    assert final_state.status is AgentStatus.COMPLETED
    assert final_state.final_result == "fallback result"
    assert final_state.retry_count == 2
    assert final_state.fallback_history == ["decision_provider"]
    assert len(records) == 1


def test_runner_does_not_fallback_for_nonretryable_failure() -> None:
    """Fallback cannot hide failures outside the approved recovery class."""
    fallback_calls = 0
    state = AgentRunState(goal="Reject broad fallback.")

    def invalid(_: AgentRunState) -> AgentDecision:
        raise ValueError("not recoverable")

    def fallback(_: AgentRunState) -> AgentDecision:
        nonlocal fallback_calls
        fallback_calls += 1
        return _finish("must not run")

    with pytest.raises(ValueError, match="not recoverable"):
        run_agent(
            state,
            build_default_registry(),
            invalid,
            fallback_decide=fallback,
        )

    assert fallback_calls == 0
    assert state.retry_count == 0
    assert state.fallback_history == []


def test_retry_exhaustion_remains_bounded_without_fallback() -> None:
    """Exhausted transient failures preserve the finite attempt count."""
    calls = 0
    state = AgentRunState(goal="Exhaust bounded retries.")

    def unavailable(_: AgentRunState) -> AgentDecision:
        nonlocal calls
        calls += 1
        raise ConnectionError("still unavailable")

    with pytest.raises(RetryExhaustedError) as captured:
        run_agent(
            state,
            build_default_registry(),
            unavailable,
        )

    assert calls == 3
    assert captured.value.attempts == 3
    assert isinstance(captured.value.__cause__, ConnectionError)
    assert state.retry_count == 2
    assert state.fallback_history == []


def test_fallback_decision_cannot_bypass_tool_registry() -> None:
    """Fallback output remains untrusted and cannot invent tool authority."""
    state = AgentRunState(goal="Attempt fallback authority escalation.")

    def unavailable(_: AgentRunState) -> AgentDecision:
        raise ConnectionError("provider unavailable")

    def forged_fallback(_: AgentRunState) -> AgentDecision:
        return AgentDecision(
            kind=DecisionKind.TOOL,
            rationale="Attempt an unauthorized action.",
            tool_name="shell",
            arguments={"command": "whoami"},
        )

    with pytest.raises(UnknownToolError):
        run_agent(
            state,
            build_default_registry(),
            unavailable,
            fallback_decide=forged_fallback,
        )

    assert state.retry_count == 2
    assert state.fallback_history == ["decision_provider"]
    assert state.selected_tools == []
    assert state.observations == []

def test_retry_exhaustion_reconciles_failed_state() -> None:
    """Exhausted bounded retry becomes FAILED without double counting."""
    state = AgentRunState(goal="Reconcile exhausted retries.")

    def unavailable(_: AgentRunState) -> AgentDecision:
        raise ConnectionError("still unavailable")

    with pytest.raises(RetryExhaustedError) as captured:
        run_agent(state, build_default_registry(), unavailable)

    assert captured.value.attempts == 3
    assert isinstance(captured.value.__cause__, ConnectionError)
    assert state.status is AgentStatus.FAILED
    assert state.retry_count == 2
    assert state.terminal_failure == "Runtime execution failed safely."


def test_nonretryable_decision_failure_reconciles_failed_state() -> None:
    """A non-retryable decision failure terminates as FAILED."""
    calls = 0
    state = AgentRunState(goal="Reconcile one failed decision.")

    def invalid(_: AgentRunState) -> AgentDecision:
        nonlocal calls
        calls += 1
        raise ValueError("provider-contract-detail")

    with pytest.raises(ValueError, match="provider-contract-detail"):
        run_agent(state, build_default_registry(), invalid)

    assert calls == 1
    assert state.status is AgentStatus.FAILED
    assert state.retry_count == 0
    assert state.terminal_failure == "Runtime execution failed safely."
    assert "provider-contract-detail" not in state.terminal_failure


def test_ambiguous_timeout_is_failed_not_timed_out() -> None:
    """A plain synchronous TimeoutError cannot imply cancellation."""
    state = AgentRunState(goal="Keep timeout evidence truthful.")

    def ambiguous(_: AgentRunState) -> AgentDecision:
        raise TimeoutError("completion status unknown")

    with pytest.raises(TimeoutError, match="completion status unknown"):
        run_agent(state, build_default_registry(), ambiguous)

    assert state.status is AgentStatus.FAILED
    assert state.retry_count == 0
    assert state.terminal_failure == "Runtime execution failed safely."


def test_failed_fallback_reconciles_state_and_preserves_history() -> None:
    """Fallback failure is FAILED while path-entry evidence remains canonical."""
    state = AgentRunState(goal="Reconcile fallback failure.")

    def unavailable(_: AgentRunState) -> AgentDecision:
        raise ConnectionError("primary unavailable")

    def failed_fallback(_: AgentRunState) -> AgentDecision:
        raise ValueError("fallback-detail")

    with pytest.raises(ValueError, match="fallback-detail"):
        run_agent(
            state,
            build_default_registry(),
            unavailable,
            fallback_decide=failed_fallback,
        )

    assert state.status is AgentStatus.FAILED
    assert state.retry_count == 2
    assert state.fallback_history == ["decision_provider"]
    assert state.terminal_failure == "Runtime execution failed safely."


def test_hostile_fallback_reconciles_failed_state() -> None:
    """Denied fallback authority becomes FAILED without executing a tool."""
    state = AgentRunState(goal="Reject fallback authority.")

    def unavailable(_: AgentRunState) -> AgentDecision:
        raise ConnectionError("primary unavailable")

    def forged(_: AgentRunState) -> AgentDecision:
        return AgentDecision(
            kind=DecisionKind.TOOL,
            rationale="Attempt unauthorized execution.",
            tool_name="shell",
            arguments={"command": "whoami"},
        )

    with pytest.raises(UnknownToolError):
        run_agent(
            state,
            build_default_registry(),
            unavailable,
            fallback_decide=forged,
        )

    assert state.status is AgentStatus.FAILED
    assert state.retry_count == 2
    assert state.fallback_history == ["decision_provider"]
    assert state.selected_tools == []
    assert state.observations == []


def test_typed_timeout_from_sync_provider_is_failed_not_timed_out() -> None:
    """An exception type alone cannot prove synchronous cancellation."""
    from ai_agent_engineering.resilience import OperationTimeoutError

    state = AgentRunState(goal="Keep synchronous timeout evidence truthful.")

    def synchronous_timeout(_: AgentRunState) -> AgentDecision:
        raise OperationTimeoutError("deadline expired")

    with pytest.raises(OperationTimeoutError, match="deadline expired"):
        run_agent(
            state,
            build_default_registry(),
            synchronous_timeout,
            decision_retry_on=(ConnectionError,),
        )

    assert state.status is AgentStatus.FAILED
    assert state.retry_count == 0
    assert state.terminal_failure == "Runtime execution failed safely."

def test_tool_authorization_denial_reconciles_failed_state() -> None:
    """Authorization denial becomes FAILED without handler execution."""
    called = False

    def blocked_handler(arguments: Mapping[str, Any]) -> str:
        nonlocal called
        called = True
        return str(arguments)

    blocked = ToolDefinition(
        name="blocked",
        description="Deliberately unauthorized test tool.",
        input_schema={"type": "object"},
        handler=blocked_handler,
        authorized=False,
    )
    registry = ToolRegistry((blocked,))
    state = AgentRunState(goal="Reject unauthorized execution.")

    def propose_blocked(_: AgentRunState) -> AgentDecision:
        return AgentDecision(
            kind=DecisionKind.TOOL,
            rationale="Propose an application-denied tool.",
            tool_name="blocked",
            arguments={},
        )

    with pytest.raises(ToolAuthorizationError):
        run_agent(state, registry, propose_blocked)

    assert called is False
    assert state.status is AgentStatus.FAILED
    assert state.terminal_failure == "Runtime execution failed safely."
    assert state.selected_tools == []
    assert state.observations == []


def test_tool_handler_failure_reconciles_failed_state() -> None:
    """A validated tool-handler failure terminates as FAILED."""
    state = AgentRunState(goal="Exercise deterministic handler failure.")

    def divide_by_zero(_: AgentRunState) -> AgentDecision:
        return AgentDecision(
            kind=DecisionKind.TOOL,
            rationale="Exercise the calculator failure boundary.",
            tool_name="calculator",
            arguments={
                "operation": "divide",
                "left": 10,
                "right": 0,
            },
        )

    with pytest.raises(ValueError, match="Division by zero"):
        run_agent(
            state,
            build_default_registry(),
            divide_by_zero,
        )

    assert state.status is AgentStatus.FAILED
    assert state.terminal_failure == "Runtime execution failed safely."
    assert state.selected_tools == []
    assert state.observations == []
