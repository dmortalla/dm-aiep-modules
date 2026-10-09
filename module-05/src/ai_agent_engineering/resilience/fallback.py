"""Explicit fallback execution for recoverable Module 5 failures."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class FallbackResult[T]:
    """Result of primary/fallback execution.

    Attributes:
        value: Successful operation result.
        used_fallback: Whether recovery required the fallback operation.
        primary_error: Recoverable primary failure, when one occurred.
    """

    value: T
    used_fallback: bool
    primary_error: Exception | None = None


def run_with_fallback[T](
    primary: Callable[[], T],
    fallback: Callable[[], T],
    *,
    fallback_on: tuple[type[Exception], ...] = (Exception,),
) -> FallbackResult[T]:
    """Run a fallback only after an explicitly recoverable failure.

    Args:
        primary: Preferred operation.
        fallback: Recovery operation.
        fallback_on: Primary exception types allowed to trigger fallback.

    Returns:
        Successful primary or fallback result.

    Raises:
        ValueError: If no recoverable exception types are configured.
        Exception: For a nonrecoverable primary failure or fallback failure.
    """
    if not fallback_on:
        raise ValueError("fallback_on cannot be empty")

    try:
        return FallbackResult(
            value=primary(),
            used_fallback=False,
        )
    except fallback_on as exc:
        return FallbackResult(
            value=fallback(),
            used_fallback=True,
            primary_error=exc,
        )
