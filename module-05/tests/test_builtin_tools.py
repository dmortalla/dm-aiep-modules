"""Tests for deterministic Module 5 teaching tools."""

import pytest
from ai_agent_engineering.tools import ToolValidationError, build_default_registry


@pytest.mark.parametrize(
    ("operation", "left", "right", "expected"),
    [
        ("add", 7, 5, 12.0),
        ("subtract", 7, 5, 2.0),
        ("multiply", 7, 5, 35.0),
        ("divide", 10, 4, 2.5),
    ],
)
def test_calculator_executes_allowlisted_operations(
    operation: str,
    left: float,
    right: float,
    expected: float,
) -> None:
    """Calculator executes only schema-approved operations."""
    registry = build_default_registry()

    result = registry.execute(
        "calculator",
        {
            "operation": operation,
            "left": left,
            "right": right,
        },
    )

    assert result["operation"] == operation
    assert result["result"] == expected


def test_calculator_rejects_unknown_operation() -> None:
    """Arbitrary operation names cannot reach the calculator handler."""
    registry = build_default_registry()

    with pytest.raises(ToolValidationError):
        registry.execute(
            "calculator",
            {
                "operation": "exec",
                "left": 1,
                "right": 2,
            },
        )


def test_calculator_rejects_extra_arguments() -> None:
    """Unexpected provider-supplied arguments fail closed."""
    registry = build_default_registry()

    with pytest.raises(ToolValidationError):
        registry.execute(
            "calculator",
            {
                "operation": "add",
                "left": 1,
                "right": 2,
                "command": "whoami",
            },
        )


def test_calculator_rejects_division_by_zero() -> None:
    """Domain-invalid arithmetic produces an explicit failure."""
    registry = build_default_registry()

    with pytest.raises(ValueError, match="Division by zero"):
        registry.execute(
            "calculator",
            {
                "operation": "divide",
                "left": 10,
                "right": 0,
            },
        )


def test_bounded_knowledge_lookup_returns_known_entry() -> None:
    """Knowledge lookup remains inside its local bounded corpus."""
    registry = build_default_registry()

    result = registry.execute(
        "knowledge_lookup",
        {"topic": "react"},
    )

    assert result["topic"] == "react"
    assert "actions" in result["content"]


def test_unknown_knowledge_does_not_escape_local_boundary() -> None:
    """Unknown topics do not trigger external or arbitrary retrieval."""
    registry = build_default_registry()

    result = registry.execute(
        "knowledge_lookup",
        {"topic": "secret filesystem data"},
    )

    assert result == {
        "topic": "secret filesystem data",
        "content": "No bounded local knowledge entry was found.",
    }


def test_structured_note_lookup_is_bounded() -> None:
    """Structured note retrieval exposes only predefined demonstration notes."""
    registry = build_default_registry()

    result = registry.execute(
        "note_lookup",
        {"key": "safety_rule"},
    )

    assert result["key"] == "safety_rule"
    assert "does not grant execution authority" in result["value"]
