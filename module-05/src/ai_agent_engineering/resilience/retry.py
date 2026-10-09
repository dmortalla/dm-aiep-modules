"""Bounded retry support for Module 5 agent operations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import sleep
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RetryResult[T]:
    """Result of a successful bounded retry operation.

    Attributes:
        value: Value returned by the successful operation.
        attempts: Total number of operation attempts performed.
    """

    value: T
    attempts: int


class RetryExhaustedError(RuntimeError):
    """Raised when a retryable operation exhausts its attempt budget."""

    def __init__(self, attempts: int, cause: Exception) -> None:
        """Initialize a retry exhaustion error.

        Args:
            attempts: Number of attempts that were performed.
            cause: Last retryable exception raised by the operation.
        """
        super().__init__(
            f"Operation failed after {attempts} attempt(s): {cause}"
        )
        self.attempts = attempts
        self.cause = cause


def run_with_retry[T](
    operation: Callable[[], T],
    *,
    max_attempts: int = 3,
    retry_on: tuple[type[Exception], ...] = (Exception,),
    delay_seconds: float = 0.0,
) -> RetryResult[T]:
    """Run an operation with a finite retry budget.

    Non-retryable exceptions fail immediately. Retry exhaustion preserves
    the final exception as both structured data and exception context.

    Args:
        operation: Zero-argument operation to execute.
        max_attempts: Maximum total operation attempts.
        retry_on: Exception types that are eligible for retry.
        delay_seconds: Fixed delay between retry attempts.

    Returns:
        The successful value and number of attempts used.

    Raises:
        ValueError: If retry configuration is invalid.
        RetryExhaustedError: If all retryable attempts fail.
        Exception: Immediately for a non-retryable failure.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if delay_seconds < 0:
        raise ValueError("delay_seconds cannot be negative")
    if not retry_on:
        raise ValueError("retry_on cannot be empty")

    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return RetryResult(
                value=operation(),
                attempts=attempt,
            )
        except retry_on as exc:
            last_error = exc

            if attempt < max_attempts and delay_seconds:
                sleep(delay_seconds)

    if last_error is None:
        raise RuntimeError("Retry loop ended without a result or error")

    raise RetryExhaustedError(
        max_attempts,
        last_error,
    ) from last_error
