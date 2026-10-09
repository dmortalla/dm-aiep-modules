"""Deadline enforcement for asynchronous Module 5 operations."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

T = TypeVar("T")


class OperationTimeoutError(TimeoutError):
    """Raised when an asynchronous operation exceeds its deadline."""


async def run_with_timeout[T](
    operation: Awaitable[T],
    *,
    timeout_seconds: float,
) -> T:
    """Run an asynchronous operation with a real deadline.

    ``asyncio.wait_for`` cancels the awaited task when the deadline expires.
    This avoids representing an uninterruptible worker thread as safely
    terminated when it may still be executing.

    Args:
        operation: Awaitable operation to execute.
        timeout_seconds: Positive execution deadline in seconds.

    Returns:
        The operation result.

    Raises:
        ValueError: If the timeout is not positive.
        OperationTimeoutError: If the deadline expires.
    """
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")

    try:
        return await asyncio.wait_for(
            operation,
            timeout=timeout_seconds,
        )
    except TimeoutError as exc:
        raise OperationTimeoutError(
            f"Operation exceeded {timeout_seconds:g}-second deadline"
        ) from exc
