"""Tests for Module 1 shared LLM models."""

import pytest
from ai_engineering_foundations.models import LLMRequest, LLMResponse, TokenUsage
from pydantic import ValidationError


def test_llm_request_accepts_valid_input() -> None:
    """A valid request should preserve its configured values."""

    request = LLMRequest(
        prompt="Explain asynchronous Python.",
        model="example-model",
        reasoning_effort="low",
        max_tokens=256,
    )

    assert request.prompt == "Explain asynchronous Python."
    assert request.model == "example-model"
    assert request.reasoning_effort == "low"
    assert request.max_tokens == 256


def test_llm_request_rejects_empty_prompt() -> None:
    """An empty prompt should fail validation."""

    with pytest.raises(ValidationError):
        LLMRequest(prompt="", model="example-model")


def test_token_usage_calculates_total() -> None:
    """Total token usage should combine input and output counts."""

    usage = TokenUsage(input_tokens=12, output_tokens=8)

    assert usage.total_tokens == 20


def test_llm_response_normalizes_provider_output() -> None:
    """Normalized responses should expose common provider fields."""

    response = LLMResponse(
        provider="openai",
        model="example-model",
        content="Hello.",
        usage=TokenUsage(input_tokens=5, output_tokens=2),
    )

    assert response.provider == "openai"
    assert response.content == "Hello."
    assert response.usage.total_tokens == 7


def test_llm_request_rejects_provider_native_fields() -> None:
    """Provider-native controls must not leak into the shared request model."""
    with pytest.raises(ValidationError):
        LLMRequest(
            prompt="Hello",
            model="example-model",
            reasoning={"effort": "low"},
        )

    with pytest.raises(ValidationError):
        LLMRequest(
            prompt="Hello",
            model="example-model",
            thinking={"type": "adaptive"},
        )

    with pytest.raises(ValidationError):
        LLMRequest(
            prompt="Hello",
            model="example-model",
            temperature=0.4,
        )