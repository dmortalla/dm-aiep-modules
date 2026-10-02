"""OpenAI asynchronous LLM provider."""

from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from ..base import AsyncLLMProvider
from ..models import LLMRequest, LLMResponse, TokenUsage


class OpenAIProvider(AsyncLLMProvider):
    """Provide asynchronous generation and streaming through OpenAI."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 2,
        client: Any | None = None,
    ) -> None:
        """Initialize the OpenAI provider."""
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        self._client = client or AsyncOpenAI(
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )

    @staticmethod
    def _build_kwargs(request: LLMRequest) -> dict[str, Any]:
        """Translate a shared request into OpenAI Responses parameters."""
        kwargs: dict[str, Any] = {
            "model": request.model,
            "input": request.prompt,
        }

        if request.max_tokens is not None:
            kwargs["max_output_tokens"] = request.max_tokens

        if request.reasoning_effort is not None:
            kwargs["reasoning"] = {"effort": request.reasoning_effort}

        return kwargs

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate and normalize one complete OpenAI response."""
        response = await self._client.responses.create(
            **self._build_kwargs(request)
        )

        usage = getattr(response, "usage", None)

        return LLMResponse(
            provider="openai",
            model=getattr(response, "model", request.model),
            content=getattr(response, "output_text", ""),
            usage=TokenUsage(
                input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
                output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
            ),
            raw_response=response,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream text deltas from OpenAI."""
        async with self._client.responses.stream(
            **self._build_kwargs(request)
        ) as stream:
            async for event in stream:
                if getattr(event, "type", "") == "response.output_text.delta":
                    delta = getattr(event, "delta", "")

                    if delta:
                        yield delta