"""Tests for the asynchronous Anthropic provider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from ai_engineering_foundations.models import LLMRequest
from ai_engineering_foundations.providers.anthropic_provider import AnthropicProvider


@pytest.mark.asyncio
async def test_generate_normalizes_anthropic_response() -> None:
    """Anthropic responses should map to the shared response model."""

    response = SimpleNamespace(
        model="claude-test",
        content=[
            SimpleNamespace(
                type="text",
                text="Hello from Anthropic.",
            )
        ],
        usage=SimpleNamespace(
            input_tokens=13,
            output_tokens=9,
        ),
    )

    client = MagicMock()
    client.messages.create = AsyncMock(return_value=response)

    provider = AnthropicProvider(client=client)

    result = await provider.generate(
        LLMRequest(
            prompt="Hello",
            model="claude-test",
            reasoning_effort="medium",
            max_tokens=200,
        )
    )

    assert result.provider == "anthropic"
    assert result.model == "claude-test"
    assert result.content == "Hello from Anthropic."
    assert result.usage.input_tokens == 13
    assert result.usage.output_tokens == 9
    assert result.usage.total_tokens == 22

    client.messages.create.assert_awaited_once_with(
        model="claude-test",
        messages=[
            {
                "role": "user",
                "content": "Hello",
            }
        ],
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        max_tokens=200,
    )


@pytest.mark.asyncio
async def test_generate_combines_text_blocks() -> None:
    """Multiple Anthropic text blocks should form one normalized response."""

    response = SimpleNamespace(
        model="claude-test",
        content=[
            SimpleNamespace(type="text", text="Hello"),
            SimpleNamespace(type="tool_use", text="ignored"),
            SimpleNamespace(type="text", text=" world"),
        ],
        usage=None,
    )

    client = MagicMock()
    client.messages.create = AsyncMock(return_value=response)

    provider = AnthropicProvider(client=client)

    result = await provider.generate(
        LLMRequest(
            prompt="Hello",
            model="claude-test",
        )
    )

    assert result.content == "Hello world"
    assert result.usage.total_tokens == 0

    client.messages.create.assert_awaited_once_with(
        model="claude-test",
        messages=[
            {
                "role": "user",
                "content": "Hello",
            }
        ],
        max_tokens=1024,
    )


@pytest.mark.asyncio
async def test_stream_yields_anthropic_text_chunks() -> None:
    """Streaming should expose Anthropic text chunks."""

    chunks = ["Hello", " ", "world"]

    class FakeTextStream:
        """Provide an asynchronous text iterator."""

        def __aiter__(self):
            self._iterator = iter(chunks)
            return self

        async def __anext__(self):
            try:
                return next(self._iterator)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

    class FakeStream:
        """Provide an Anthropic-style asynchronous stream context."""

        def __init__(self) -> None:
            self.text_stream = FakeTextStream()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    client = MagicMock()
    client.messages.stream.return_value = FakeStream()

    provider = AnthropicProvider(client=client)

    request = LLMRequest(
        prompt="Hello",
        model="claude-test",
        max_tokens=50,
    )

    result = [chunk async for chunk in provider.stream(request)]

    assert result == ["Hello", " ", "world"]

    client.messages.stream.assert_called_once_with(
        model="claude-test",
        messages=[
            {
                "role": "user",
                "content": "Hello",
            }
        ],
        max_tokens=50,
    )


def test_invalid_anthropic_provider_configuration_is_rejected() -> None:
    """Invalid timeout and retry values should fail before SDK creation."""

    with pytest.raises(ValueError, match="timeout"):
        AnthropicProvider(timeout=0)

    with pytest.raises(ValueError, match="max_retries"):
        AnthropicProvider(max_retries=-1)
