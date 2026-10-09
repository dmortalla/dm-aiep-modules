"""Tests for bounded retry behavior."""

import pytest
from ai_agent_engineering.resilience import (
    RetryExhaustedError,
    run_with_retry,
)


def test_retry_returns_first_success() -> None:
    result = run_with_retry(lambda: "ok")

    assert result.value == "ok"
    assert result.attempts == 1


def test_retry_recovers_within_budget() -> None:
    attempts = 0

    def flaky_operation() -> str:
        nonlocal attempts
        attempts += 1

        if attempts < 3:
            raise ConnectionError("temporary failure")

        return "recovered"

    result = run_with_retry(
        flaky_operation,
        max_attempts=3,
        retry_on=(ConnectionError,),
    )

    assert result.value == "recovered"
    assert result.attempts == 3


def test_retry_exhaustion_is_bounded_and_preserves_cause() -> None:
    attempts = 0

    def failing_operation() -> str:
        nonlocal attempts
        attempts += 1
        raise ConnectionError("still unavailable")

    with pytest.raises(RetryExhaustedError) as captured:
        run_with_retry(
            failing_operation,
            max_attempts=2,
            retry_on=(ConnectionError,),
        )

    assert attempts == 2
    assert captured.value.attempts == 2
    assert isinstance(captured.value.cause, ConnectionError)
    assert isinstance(captured.value.__cause__, ConnectionError)


def test_nonretryable_failure_fails_immediately() -> None:
    attempts = 0

    def invalid_operation() -> str:
        nonlocal attempts
        attempts += 1
        raise ValueError("invalid request")

    with pytest.raises(ValueError, match="invalid request"):
        run_with_retry(
            invalid_operation,
            max_attempts=5,
            retry_on=(ConnectionError,),
        )

    assert attempts == 1


@pytest.mark.parametrize(
    ("max_attempts", "delay_seconds"),
    [
        (0, 0.0),
        (1, -0.1),
    ],
)
def test_invalid_retry_configuration_is_rejected(
    max_attempts: int,
    delay_seconds: float,
) -> None:
    with pytest.raises(ValueError):
        run_with_retry(
            lambda: "never",
            max_attempts=max_attempts,
            delay_seconds=delay_seconds,
        )


def test_empty_retry_exception_policy_is_rejected() -> None:
    with pytest.raises(ValueError, match="retry_on"):
        run_with_retry(
            lambda: "never",
            retry_on=(),
        )
