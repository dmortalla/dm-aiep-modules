"""Shared data models for LLM interactions."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LLMRequest(BaseModel):
    """Represent a provider-independent LLM request."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1)
    model: str = Field(min_length=1)
    max_tokens: int | None = Field(default=None, gt=0)
    reasoning_effort: Literal["none", "low", "medium", "high"] | None = None
    thinking_level: Literal["low", "medium", "high"] | None = None


class TokenUsage(BaseModel):
    """Represent token usage reported by an LLM provider."""

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)

    @property
    def total_tokens(self) -> int:
        """Return total input and output tokens."""

        return self.input_tokens + self.output_tokens


class LLMResponse(BaseModel):
    """Represent a normalized response from an LLM provider."""

    provider: Literal["openai", "anthropic", "gemini"]
    model: str
    content: str
    usage: TokenUsage = Field(default_factory=TokenUsage)
    raw_response: Any | None = Field(default=None, exclude=True)