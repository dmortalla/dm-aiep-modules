"""Structured parsing and validation for normalized LLM responses."""

import json
import re

from pydantic import BaseModel, ValidationError

from .models import LLMResponse

_JSON_FENCE_PATTERN = re.compile(
    r"^\s*```(?:json)?\s*(.*?)\s*```\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)


class StructuredResponseError(ValueError):
    """Represent invalid or schema-incompatible structured LLM output."""


def extract_json_text(content: str) -> str:
    """Extract JSON text from plain or fenced LLM output.

    Args:
        content: Raw normalized LLM text.

    Returns:
        JSON text ready for decoding.

    Raises:
        StructuredResponseError: If the response is empty.
    """
    stripped = content.strip()

    if not stripped:
        raise StructuredResponseError("LLM response content is empty.")

    match = _JSON_FENCE_PATTERN.fullmatch(stripped)

    if match:
        return match.group(1).strip()

    return stripped


def parse_structured_response[StructuredModel: BaseModel](
    response: LLMResponse,
    schema: type[StructuredModel],
) -> StructuredModel:
    """Parse normalized LLM text and validate it against a Pydantic model.

    Args:
        response: Provider-independent normalized LLM response.
        schema: Pydantic model class defining the required structure.

    Returns:
        Validated instance of the requested Pydantic model.

    Raises:
        StructuredResponseError: If JSON decoding or schema validation fails.
    """
    json_text = extract_json_text(response.content)

    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise StructuredResponseError(
            "LLM response did not contain valid JSON."
        ) from exc

    try:
        return schema.model_validate(payload)
    except ValidationError as exc:
        raise StructuredResponseError(
            "LLM response JSON did not match the required schema."
        ) from exc

