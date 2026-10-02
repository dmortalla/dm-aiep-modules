"""Tests for structured LLM response parsing."""

import pytest
from ai_engineering_foundations.models import LLMResponse
from ai_engineering_foundations.structured import (
    StructuredResponseError,
    extract_json_text,
    parse_structured_response,
)
from pydantic import BaseModel, Field


class AnalysisResult(BaseModel):
    """Example structured response schema."""

    summary: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


def make_response(content: str) -> LLMResponse:
    """Create a normalized response for parser tests."""

    return LLMResponse(
        provider="openai",
        model="test-model",
        content=content,
    )


def test_extract_json_text_accepts_plain_json() -> None:
    """Plain JSON should pass through after whitespace trimming."""

    content = '  {"summary": "Ready", "confidence": 0.9}  '

    result = extract_json_text(content)

    assert result == '{"summary": "Ready", "confidence": 0.9}'


def test_extract_json_text_accepts_json_fence() -> None:
    """Markdown JSON fences should be removed safely."""

    content = """```json
{"summary": "Ready", "confidence": 0.9}
```"""

    result = extract_json_text(content)

    assert result == '{"summary": "Ready", "confidence": 0.9}'


def test_extract_json_text_accepts_unlabelled_fence() -> None:
    """Unlabelled Markdown fences should also be supported."""

    content = """```
{"summary": "Ready", "confidence": 0.9}
```"""

    result = extract_json_text(content)

    assert result == '{"summary": "Ready", "confidence": 0.9}'


def test_empty_content_is_rejected() -> None:
    """Empty normalized output should fail clearly."""

    with pytest.raises(
        StructuredResponseError,
        match="content is empty",
    ):
        extract_json_text("   ")


def test_parse_structured_response_returns_validated_model() -> None:
    """Valid JSON should produce the requested Pydantic model."""

    response = make_response(
        '{"summary": "System healthy", "confidence": 0.95}'
    )

    result = parse_structured_response(
        response,
        AnalysisResult,
    )

    assert isinstance(result, AnalysisResult)
    assert result.summary == "System healthy"
    assert result.confidence == 0.95


def test_invalid_json_is_rejected() -> None:
    """Malformed JSON should produce a domain-specific parser error."""

    response = make_response(
        '{"summary": "Broken", "confidence":'
    )

    with pytest.raises(
        StructuredResponseError,
        match="valid JSON",
    ):
        parse_structured_response(
            response,
            AnalysisResult,
        )


def test_schema_mismatch_is_rejected() -> None:
    """JSON that violates the requested schema should fail validation."""

    response = make_response(
        '{"summary": "Invalid confidence", "confidence": 2.5}'
    )

    with pytest.raises(
        StructuredResponseError,
        match="required schema",
    ):
        parse_structured_response(
            response,
            AnalysisResult,
        )


def test_missing_required_field_is_rejected() -> None:
    """Missing required structured fields should fail validation."""

    response = make_response(
        '{"summary": "Missing confidence"}'
    )

    with pytest.raises(
        StructuredResponseError,
        match="required schema",
    ):
        parse_structured_response(
            response,
            AnalysisResult,
        )
