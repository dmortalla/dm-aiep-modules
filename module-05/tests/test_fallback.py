"""Tests for explicit fallback and recovery behavior."""

import pytest
from ai_agent_engineering.resilience import run_with_fallback


def test_primary_success_does_not_execute_fallback() -> None:
    fallback_called = False

    def fallback() -> str:
        nonlocal fallback_called
        fallback_called = True
        return "fallback"

    result = run_with_fallback(
        lambda: "primary",
        fallback,
    )

    assert result.value == "primary"
    assert result.used_fallback is False
    assert result.primary_error is None
    assert fallback_called is False


def test_recoverable_failure_executes_fallback() -> None:
    def primary() -> str:
        raise ConnectionError("provider unavailable")

    result = run_with_fallback(
        primary,
        lambda: "safe fallback",
        fallback_on=(ConnectionError,),
    )

    assert result.value == "safe fallback"
    assert result.used_fallback is True
    assert isinstance(result.primary_error, ConnectionError)


def test_nonrecoverable_failure_does_not_trigger_fallback() -> None:
    fallback_called = False

    def primary() -> str:
        raise PermissionError("authority denied")

    def fallback() -> str:
        nonlocal fallback_called
        fallback_called = True
        return "must not run"

    with pytest.raises(PermissionError, match="authority denied"):
        run_with_fallback(
            primary,
            fallback,
            fallback_on=(ConnectionError,),
        )

    assert fallback_called is False


def test_fallback_failure_is_not_hidden() -> None:
    def primary() -> str:
        raise ConnectionError("primary unavailable")

    def fallback() -> str:
        raise RuntimeError("fallback unavailable")

    with pytest.raises(RuntimeError, match="fallback unavailable"):
        run_with_fallback(
            primary,
            fallback,
            fallback_on=(ConnectionError,),
        )


def test_empty_fallback_policy_is_rejected() -> None:
    with pytest.raises(ValueError, match="fallback_on"):
        run_with_fallback(
            lambda: "primary",
            lambda: "fallback",
            fallback_on=(),
        )
