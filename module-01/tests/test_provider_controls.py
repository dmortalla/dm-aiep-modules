"""Regression tests for provider-specific reasoning controls."""

from ai_engineering_foundations.models import LLMRequest
from ai_engineering_foundations.providers.anthropic_provider import AnthropicProvider
from ai_engineering_foundations.providers.gemini_provider import GeminiProvider
from ai_engineering_foundations.providers.openai_provider import OpenAIProvider


def test_openai_uses_reasoning_effort_without_temperature() -> None:
    """OpenAI should translate reasoning effort without temperature."""
    request = LLMRequest(
        prompt="test",
        model="gpt-5.6-terra",
        reasoning_effort="low",
    )

    kwargs = OpenAIProvider._build_kwargs(request)

    assert kwargs["reasoning"] == {"effort": "low"}
    assert "temperature" not in kwargs


def test_anthropic_uses_adaptive_thinking_without_temperature() -> None:
    """Anthropic should use adaptive thinking without temperature."""
    request = LLMRequest(
        prompt="test",
        model="claude-sonnet-5-5",
        reasoning_effort="medium",
    )

    kwargs = AnthropicProvider._build_kwargs(request)

    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["output_config"] == {"effort": "medium"}
    assert "temperature" not in kwargs


def test_anthropic_omits_thinking_when_not_requested() -> None:
    """Anthropic should allow normal generation without thinking."""
    request = LLMRequest(
        prompt="test",
        model="claude-sonnet-5-5",
    )

    kwargs = AnthropicProvider._build_kwargs(request)

    assert "thinking" not in kwargs


def test_gemini_uses_thinking_level_without_temperature() -> None:
    """Gemini should translate its native thinking level."""
    request = LLMRequest(
        prompt="test",
        model="gemini-3.8-flash",
        thinking_level="medium",
    )

    config = GeminiProvider._build_config(request)

    assert config.thinking_config is not None
    assert config.thinking_config.thinking_level == "MEDIUM"
    assert config.temperature is None