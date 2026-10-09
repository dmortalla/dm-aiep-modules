"""Tests for typed tool contracts and schema validation."""

from collections.abc import Mapping
from typing import Any

import pytest
from ai_agent_engineering.tools import (
    ToolAuthorizationError,
    ToolDefinition,
    ToolValidationError,
)


def _echo(arguments: Mapping[str, Any]) -> dict[str, Any]:
    return dict(arguments)


def test_tool_definition_validates_arguments() -> None:
    """Valid structured arguments are copied and accepted."""
    tool = ToolDefinition(
        name="echo",
        description="Echo one value.",
        input_schema={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        handler=_echo,
    )

    source = {"value": "safe"}
    validated = tool.validate_arguments(source)

    assert validated == source
    assert validated is not source


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"value": 42},
        {"value": "safe", "unexpected": True},
    ],
)
def test_invalid_arguments_are_rejected(
    arguments: dict[str, Any],
) -> None:
    """Schema violations cannot reach tool execution."""
    tool = ToolDefinition(
        name="echo",
        description="Echo one value.",
        input_schema={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        handler=_echo,
    )

    with pytest.raises(ToolValidationError):
        tool.execute(arguments)


def test_non_mapping_arguments_are_rejected() -> None:
    """Provider-like malformed argument payloads fail safely."""
    tool = ToolDefinition(
        name="echo",
        description="Echo one value.",
        input_schema={"type": "object"},
        handler=_echo,
    )

    with pytest.raises(ToolValidationError):
        tool.execute("forged")  # type: ignore[arg-type]


def test_unauthorized_tool_cannot_execute() -> None:
    """Possessing a tool definition does not imply execution authority."""
    called = False

    def handler(arguments: Mapping[str, Any]) -> dict[str, Any]:
        nonlocal called
        called = True
        return dict(arguments)

    tool = ToolDefinition(
        name="blocked",
        description="A deliberately unauthorized tool.",
        input_schema={"type": "object"},
        handler=handler,
        authorized=False,
    )

    with pytest.raises(ToolAuthorizationError):
        tool.execute({})

    assert called is False


@pytest.mark.parametrize(
    ("name", "description"),
    [
        ("", "Valid description"),
        ("   ", "Valid description"),
        ("valid", ""),
        ("valid", "   "),
    ],
)
def test_empty_tool_metadata_is_rejected(
    name: str,
    description: str,
) -> None:
    """Tool contracts require stable names and useful descriptions."""
    with pytest.raises(ValueError):
        ToolDefinition(
            name=name,
            description=description,
            input_schema={"type": "object"},
            handler=_echo,
        )
