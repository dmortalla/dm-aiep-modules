
"""Tests for queue-based asynchronous LLM execution."""

import asyncio

import pytest
from ai_engineering_foundations.models import LLMRequest, LLMResponse
from ai_engineering_foundations.service import LLMService, LLMServiceError
from test_service import FakeProvider


@pytest.mark.asyncio
async def test_generate_queued_preserves_request_order() -> None:
    """Queue workers should preserve the caller-visible request order."""
    service = LLMService(
        {
            "openai": FakeProvider("openai", delay=0.02),
            "anthropic": FakeProvider("anthropic"),
        }
    )

    results = await service.generate_queued(
        [
            ("openai", LLMRequest(prompt="first", model="model-a")),
            ("anthropic", LLMRequest(prompt="second", model="model-b")),
        ],
        workers=2,
    )

    assert [result.content for result in results] == [
        "openai:first",
        "anthropic:second",
    ]


@pytest.mark.asyncio
async def test_generate_queued_rejects_invalid_worker_count() -> None:
    """A queue requires at least one worker."""
    service = LLMService()

    with pytest.raises(ValueError, match="workers"):
        await service.generate_queued([], workers=0)


@pytest.mark.asyncio
async def test_generate_queued_handles_empty_workload() -> None:
    """An empty queue should complete without creating workers."""
    service = LLMService()

    assert await service.generate_queued([]) == []

@pytest.mark.asyncio
async def test_queued_execution_propagates_worker_failure_without_hanging() -> None:
    """A provider failure should terminate queued execution instead of hanging."""

    class FailingProvider(FakeProvider):
        async def generate(self, request: LLMRequest) -> LLMResponse:
            if request.prompt == "fail":
                raise RuntimeError("provider failure")

            return await super().generate(request)

    service = LLMService({"fake": FailingProvider("fake")})

    requests = [
        ("fake", LLMRequest(prompt="fail", model="test-model")),
        ("fake", LLMRequest(prompt="queued", model="test-model")),
    ]

    with pytest.raises(LLMServiceError):
        await asyncio.wait_for(
            service.generate_queued(requests, workers=1),
            timeout=1.0,
        )