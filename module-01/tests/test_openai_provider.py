"""Tests for the asynchronous OpenAI provider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from ai_engineering_foundations.models import LLMRequest
from ai_engineering_foundations.providers.openai_provider import OpenAIProvider


@pytest.mark.asyncio
async def test_generate_normalizes_openai_response() -> None:
    """OpenAI responses should map to the shared response model."""

    response = SimpleNamespace(
        model="gpt-test",
        output_text="Hello from OpenAI.",
        usage=SimpleNamespace(
            input_tokens=11,
            output_tokens=7,
        ),
    )

    client = MagicMock()
    client.responses.create = AsyncMock(return_value=response)

    provider = OpenAIProvider(client=client)

    result = await provider.generate(
        LLMRequest(
            prompt="Hello",
            model="gpt-test",
            reasoning_effort="low",
            max_tokens=100,
        )
    )

    assert result.provider == "openai"
    assert result.model == "gpt-test"
    assert result.content == "Hello from OpenAI."
    assert result.usage.input_tokens == 11
    assert result.usage.output_tokens == 7
    assert result.usage.total_tokens == 18

    client.responses.create.assert_awaited_once_with(
        model="gpt-test",
        input="Hello",
        reasoning={"effort": "low"},
        max_output_tokens=100,
    )


@pytest.mark.asyncio
async def test_generate_omits_optional_max_tokens() -> None:
    """Optional output-token limits should be omitted when unspecified."""

    response = SimpleNamespace(
        model="gpt-test",
        output_text="Done.",
        usage=None,
    )

    client = MagicMock()
    client.responses.create = AsyncMock(return_value=response)

    provider = OpenAIProvider(client=client)

    result = await provider.generate(
        LLMRequest(
            prompt="Hello",
            model="gpt-test",
        )
    )

    assert result.usage.total_tokens == 0

    client.responses.create.assert_awaited_once_with(
        model="gpt-test",
        input="Hello",
    )


@pytest.mark.asyncio
async def test_stream_yields_only_text_deltas() -> None:
    """Streaming should expose only non-empty text deltas."""

    events = [
        SimpleNamespace(
            type="response.output_text.delta",
            delta="Hello",
        ),
        SimpleNamespace(
            type="response.output_text.delta",
            delta=" ",
        ),
        SimpleNamespace(
            type="response.output_text.delta",
            delta="world",
        ),
        SimpleNamespace(
            type="response.completed",
            delta="",
        ),
    ]

    class FakeStream:
        """Provide an asynchronous context manager and event iterator."""

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        def __aiter__(self):
            self._iterator = iter(events)
            return self

        async def __anext__(self):
            try:
                return next(self._iterator)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

    client = MagicMock()
    client.responses.stream.return_value = FakeStream()

    provider = OpenAIProvider(client=client)

    request = LLMRequest(
        prompt="Hello",
        model="gpt-test",
        max_tokens=50,
    )

    chunks = [chunk async for chunk in provider.stream(request)]

    assert chunks == ["Hello", " ", "world"]

    client.responses.stream.assert_called_once_with(
        model="gpt-test",
        input="Hello",
        max_output_tokens=50,
    )


def test_invalid_openai_provider_configuration_is_rejected() -> None:
    """Invalid timeout and retry values should fail before SDK creation."""

    with pytest.raises(ValueError, match="timeout"):
        OpenAIProvider(timeout=0)

    with pytest.raises(ValueError, match="max_retries"):
        OpenAIProvider(max_retries=-1)
