"""Google Gemini asynchronous LLM provider."""

from collections.abc import AsyncIterator
from typing import Any

from google import genai
from google.genai import types

from ..base import AsyncLLMProvider
from ..models import LLMRequest, LLMResponse, TokenUsage


class GeminiProvider(AsyncLLMProvider):
    """Provide asynchronous generation and streaming through Google Gemini."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        """Initialize the Gemini provider."""
        self._client = client or genai.Client(api_key=api_key)

    @staticmethod
    def _build_config(request: LLMRequest) -> types.GenerateContentConfig:
        """Translate a shared request into Gemini generation configuration."""
        thinking_config = None

        if request.thinking_level is not None:
            thinking_config = types.ThinkingConfig(
                thinking_level=request.thinking_level,
            )

        return types.GenerateContentConfig(
            max_output_tokens=request.max_tokens,
            thinking_config=thinking_config,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True,
            ),
        )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate and normalize one complete Gemini response."""
        response = await self._client.aio.models.generate_content(
            model=request.model,
            contents=request.prompt,
            config=self._build_config(request),
        )

        usage = getattr(response, "usage_metadata", None)

        return LLMResponse(
            provider="gemini",
            model=request.model,
            content=getattr(response, "text", "") or "",
            usage=TokenUsage(
                input_tokens=(
                    getattr(usage, "prompt_token_count", 0) or 0
                    if usage
                    else 0
                ),
                output_tokens=(
                    getattr(usage, "candidates_token_count", 0) or 0
                    if usage
                    else 0
                ),
            ),
            raw_response=response,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream text chunks from Gemini."""
        stream = await self._client.aio.models.generate_content_stream(
            model=request.model,
            contents=request.prompt,
            config=self._build_config(request),
        )

        async for chunk in stream:
            text = getattr(chunk, "text", "") or ""

            if text:
                yield text