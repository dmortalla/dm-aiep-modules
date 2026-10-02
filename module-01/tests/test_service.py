"""Tests for the provider-independent asynchronous LLM service."""

import asyncio

import pytest
from ai_engineering_foundations.base import AsyncLLMProvider
from ai_engineering_foundations.models import LLMRequest, LLMResponse
from ai_engineering_foundations.service import (
    LLMService,
    LLMServiceError,
    UnknownProviderError,
)


class FakeProvider(AsyncLLMProvider):
    """Provide deterministic responses for service tests."""

    def __init__(
        self,
        provider_name: str,
        *,
        delay: float = 0.0,
    ) -> None:
        """Initialize the fake provider."""

        self.provider_name = provider_name
        self.delay = delay

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Return a deterministic normalized response."""

        if self.delay:
            await asyncio.sleep(self.delay)

        return LLMResponse(
            provider=self.provider_name,
            model=request.model,
            content=f"{self.provider_name}:{request.prompt}",
        )

    async def stream(self, request: LLMRequest):
        """Yield deterministic text chunks."""

        yield self.provider_name
        yield ":"
        yield request.prompt


@pytest.mark.asyncio
async def test_generate_routes_to_selected_provider() -> None:
    """Generation should use the requested registered provider."""

    service = LLMService(
        {
            "openai": FakeProvider("openai"),
        }
    )

    result = await service.generate(
        "openai",
        LLMRequest(
            prompt="hello",
            model="test-model",
        ),
    )

    assert result.provider == "openai"
    assert result.content == "openai:hello"


@pytest.mark.asyncio
async def test_stream_routes_to_selected_provider() -> None:
    """Streaming should expose chunks from the selected provider."""

    service = LLMService(
        {
            "anthropic": FakeProvider("anthropic"),
        }
    )

    request = LLMRequest(
        prompt="hello",
        model="test-model",
    )

    chunks = [
        chunk
        async for chunk in service.stream(
            "anthropic",
            request,
        )
    ]

    assert chunks == ["anthropic", ":", "hello"]


def test_register_provider_normalizes_name() -> None:
    """Provider registration should normalize surrounding whitespace and case."""

    service = LLMService()

    service.register_provider(
        "  Gemini  ",
        FakeProvider("gemini"),
    )

    assert service.provider_names == ("gemini",)
    assert service.get_provider("GEMINI").provider_name == "gemini"


def test_empty_provider_name_is_rejected() -> None:
    """Empty provider names should fail before registration."""

    service = LLMService()

    with pytest.raises(ValueError, match="cannot be empty"):
        service.register_provider(
            "   ",
            FakeProvider("openai"),
        )


def test_unknown_provider_has_clear_error() -> None:
    """Unknown providers should report available provider names."""

    service = LLMService(
        {
            "openai": FakeProvider("openai"),
            "gemini": FakeProvider("gemini"),
        }
    )

    with pytest.raises(
        UnknownProviderError,
        match="Available providers: gemini, openai",
    ):
        service.get_provider("anthropic")


@pytest.mark.asyncio
async def test_generate_many_preserves_request_order() -> None:
    """Concurrent generation should preserve input ordering."""

    service = LLMService(
        {
            "openai": FakeProvider("openai", delay=0.02),
            "anthropic": FakeProvider("anthropic", delay=0.0),
        }
    )

    results = await service.generate_many(
        [
            (
                "openai",
                LLMRequest(
                    prompt="first",
                    model="model-a",
                ),
            ),
            (
                "anthropic",
                LLMRequest(
                    prompt="second",
                    model="model-b",
                ),
            ),
        ]
    )

    assert [result.content for result in results] == [
        "openai:first",
        "anthropic:second",
    ]


class FailingProvider(AsyncLLMProvider):
    """Provide deterministic provider failures."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Fail deterministic generation."""

        raise RuntimeError("provider-secret-detail")

    async def stream(self, request: LLMRequest):
        """Fail deterministic streaming."""

        raise RuntimeError("provider-secret-detail")

        if False:
            yield ""


@pytest.mark.asyncio
async def test_generate_wraps_provider_failure() -> None:
    """Provider generation failures should cross a stable service boundary."""

    service = LLMService(
        {
            "openai": FailingProvider(),
        }
    )

    request = LLMRequest(
        prompt="sensitive prompt text",
        model="test-model",
    )

    with pytest.raises(
        LLMServiceError,
        match="LLM generation failed for provider 'openai'",
    ) as exc_info:
        await service.generate("openai", request)

    assert "provider-secret-detail" not in str(exc_info.value)
    assert "sensitive prompt text" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_stream_wraps_provider_failure() -> None:
    """Provider streaming failures should cross a stable service boundary."""

    service = LLMService(
        {
            "anthropic": FailingProvider(),
        }
    )

    request = LLMRequest(
        prompt="sensitive prompt text",
        model="test-model",
    )

    with pytest.raises(
        LLMServiceError,
        match="LLM streaming failed for provider 'anthropic'",
    ) as exc_info:
        async for _ in service.stream("anthropic", request):
            pass

    assert "provider-secret-detail" not in str(exc_info.value)
    assert "sensitive prompt text" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_generation_logs_metadata_without_prompt(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Operational logs should contain metadata but not prompt content."""

    service = LLMService(
        {
            "openai": FakeProvider("openai"),
        }
    )

    request = LLMRequest(
        prompt="do-not-log-this-prompt",
        model="test-model",
    )

    with caplog.at_level("INFO"):
        await service.generate("openai", request)

    log_output = caplog.text

    assert "provider=openai" in log_output
    assert "model=test-model" in log_output
    assert "do-not-log-this-prompt" not in log_output

