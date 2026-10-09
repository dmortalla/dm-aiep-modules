"""Small deterministic tools used to demonstrate safe orchestration."""

from __future__ import annotations

import operator
from collections.abc import Mapping
from typing import Any

from .registry import ToolRegistry
from .schemas import ToolDefinition

_KNOWLEDGE_BASE = {
    "react": (
        "ReAct combines reasoning-oriented decision steps with actions and "
        "observations in an iterative agent loop."
    ),
    "tool schema": (
        "A tool schema defines the structured arguments an application accepts "
        "before allowing a tool call to execute."
    ),
    "agent lifecycle": (
        "An agent lifecycle describes the bounded states and transitions of an "
        "agent run from receipt through completion or terminal failure."
    ),
}

_NOTES = {
    "demo_goal": "Use only application-allowlisted tools.",
    "safety_rule": "Model output is data and does not grant execution authority.",
}

_OPERATIONS = {
    "add": operator.add,
    "subtract": operator.sub,
    "multiply": operator.mul,
    "divide": operator.truediv,
}


def _calculate(arguments: Mapping[str, Any]) -> dict[str, float | str]:
    """Execute one allowlisted arithmetic operation."""
    operation_name = str(arguments["operation"])
    left = float(arguments["left"])
    right = float(arguments["right"])

    if operation_name == "divide" and right == 0:
        raise ValueError("Division by zero is not permitted.")

    operation = _OPERATIONS[operation_name]
    result = operation(left, right)

    return {
        "operation": operation_name,
        "result": float(result),
    }


def _knowledge_lookup(arguments: Mapping[str, Any]) -> dict[str, str]:
    """Retrieve one bounded entry from local teaching knowledge."""
    topic = str(arguments["topic"]).strip().casefold()

    if topic not in _KNOWLEDGE_BASE:
        return {
            "topic": topic,
            "content": "No bounded local knowledge entry was found.",
        }

    return {
        "topic": topic,
        "content": _KNOWLEDGE_BASE[topic],
    }


def _note_lookup(arguments: Mapping[str, Any]) -> dict[str, str]:
    """Retrieve one bounded structured demonstration note."""
    key = str(arguments["key"]).strip()

    return {
        "key": key,
        "value": _NOTES.get(key, "No structured note was found."),
    }


def build_default_registry() -> ToolRegistry:
    """Build the standalone allowlist used by deterministic demonstrations.

    Returns:
        Registry containing the three approved Module 5 teaching tools.
    """
    calculator = ToolDefinition(
        name="calculator",
        description="Perform one bounded arithmetic operation.",
        input_schema={
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": [
                        "add",
                        "subtract",
                        "multiply",
                        "divide",
                    ],
                },
                "left": {"type": "number"},
                "right": {"type": "number"},
            },
            "required": ["operation", "left", "right"],
            "additionalProperties": False,
        },
        handler=_calculate,
    )

    knowledge_lookup = ToolDefinition(
        name="knowledge_lookup",
        description="Look up one topic in bounded local teaching knowledge.",
        input_schema={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "minLength": 1,
                },
            },
            "required": ["topic"],
            "additionalProperties": False,
        },
        handler=_knowledge_lookup,
    )

    note_lookup = ToolDefinition(
        name="note_lookup",
        description="Retrieve one structured demonstration note.",
        input_schema={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "minLength": 1,
                },
            },
            "required": ["key"],
            "additionalProperties": False,
        },
        handler=_note_lookup,
    )

    return ToolRegistry(
        (
            calculator,
            knowledge_lookup,
            note_lookup,
        )
    )
