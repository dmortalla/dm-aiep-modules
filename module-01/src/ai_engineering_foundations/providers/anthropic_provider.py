"""Anthropic asynchronous LLM provider."""

from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic

from ..base import AsyncLLMProvider
from ..models import LLMRequest, LLMResponse, TokenUsage


class AnthropicProvider(AsyncLLMProvider):
    """Provide asynchronous generation and streaming through Anthropic."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 2,
        client: Any | None = None,
    ) -> None:
        """Initialize the Anthropic provider."""
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        self._client = client or AsyncAnthropic(
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )

    @staticmethod
    def _build_kwargs(request: LLMRequest) -> dict[str, Any]:
        """Translate a shared request into Anthropic Messages parameters."""
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": [
                {
                    "role": "user",
                    "content": request.prompt,
                }
            ],
            "max_tokens": request.max_tokens or 1024,
        }

        if request.reasoning_effort is not None:
            kwargs["thinking"] = {"type": "adaptive"}
            kwargs["output_config"] = {
                "effort": request.reasoning_effort,
            }

        return kwargs

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate and normalize one complete Anthropic response."""
        response = await self._client.messages.create(
            **self._build_kwargs(request)
        )

        text_parts = [
            getattr(block, "text", "")
            for block in getattr(response, "content", [])
            if getattr(block, "type", "") == "text"
        ]

        usage = getattr(response, "usage", None)

        return LLMResponse(
            provider="anthropic",
            model=getattr(response, "model", request.model),
            content="".join(text_parts),
            usage=TokenUsage(
                input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
                output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
            ),
            raw_response=response,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream text deltas from Anthropic."""
        async with self._client.messages.stream(
            **self._build_kwargs(request)
        ) as stream:
            async for text in stream.text_stream:
                if text:
                    yield text