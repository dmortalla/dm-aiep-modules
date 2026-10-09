"""Tests for real asynchronous timeout handling."""

import asyncio

import pytest
from ai_agent_engineering.resilience import (
    OperationTimeoutError,
    run_with_timeout,
)


@pytest.mark.asyncio
async def test_operation_finishing_before_deadline_succeeds() -> None:
    async def operation() -> str:
        await asyncio.sleep(0)
        return "complete"

    result = await run_with_timeout(
        operation(),
        timeout_seconds=1.0,
    )

    assert result == "complete"


@pytest.mark.asyncio
async def test_operation_exceeding_deadline_is_cancelled() -> None:
    cancelled = asyncio.Event()

    async def slow_operation() -> str:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.set()
            raise

        return "unreachable"

    with pytest.raises(OperationTimeoutError):
        await run_with_timeout(
            slow_operation(),
            timeout_seconds=0.01,
        )

    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_nonpositive_timeout_is_rejected_and_coroutine_closed() -> None:
    async def operation() -> str:
        return "never"

    coroutine = operation()

    try:
        with pytest.raises(ValueError, match="greater than zero"):
            await run_with_timeout(
                coroutine,
                timeout_seconds=0,
            )
    finally:
        coroutine.close()
