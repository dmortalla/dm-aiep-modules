"""Tests for the application-owned tool registry."""

from collections.abc import Mapping
from typing import Any

import pytest
from ai_agent_engineering.tools import (
    DuplicateToolError,
    ToolAuthorizationError,
    ToolDefinition,
    ToolRegistry,
    UnknownToolError,
    build_default_registry,
)


def _echo(arguments: Mapping[str, Any]) -> dict[str, Any]:
    return dict(arguments)


def test_registry_is_an_explicit_allowlist() -> None:
    """Only registered application-owned names can resolve."""
    registry = build_default_registry()

    assert registry.names() == (
        "calculator",
        "knowledge_lookup",
        "note_lookup",
    )

    with pytest.raises(UnknownToolError):
        registry.get("shell")

    with pytest.raises(UnknownToolError):
        registry.get("python_eval")


def test_duplicate_tool_names_are_rejected() -> None:
    """Stable names cannot be silently replaced."""
    tool = ToolDefinition(
        name="echo",
        description="Echo input.",
        input_schema={"type": "object"},
        handler=_echo,
    )

    registry = ToolRegistry((tool,))

    with pytest.raises(DuplicateToolError):
        registry.register(tool)


def test_unknown_provider_proposed_tool_is_denied() -> None:
    """A model/provider cannot invent execution authority."""
    registry = build_default_registry()

    with pytest.raises(UnknownToolError):
        registry.execute(
            "delete_everything",
            {"confirmed": True},
        )


def test_registry_denies_unauthorized_tool_before_handler() -> None:
    """Registry authorization is enforced before execution."""
    called = False

    def handler(arguments: Mapping[str, Any]) -> str:
        nonlocal called
        called = True
        return "unexpected"

    blocked = ToolDefinition(
        name="blocked",
        description="Blocked test tool.",
        input_schema={"type": "object"},
        handler=handler,
        authorized=False,
    )
    registry = ToolRegistry((blocked,))

    with pytest.raises(ToolAuthorizationError):
        registry.execute("blocked", {})

    assert called is False


@pytest.mark.parametrize(
    ("goal", "expected"),
    [
        ("Calculate 12 plus 4", "calculator"),
        ("What is ReAct? Use knowledge lookup.", "knowledge_lookup"),
        ("Remember the safety note context", "note_lookup"),
    ],
)
def test_dynamic_selection_chooses_allowlisted_candidate(
    goal: str,
    expected: str,
) -> None:
    """Deterministic dynamic selection returns only registered tools."""
    registry = build_default_registry()

    selected = registry.select_for_goal(goal)

    assert selected.name == expected
    assert selected.name in registry.names()


def test_dynamic_selection_fails_closed_without_candidate() -> None:
    """Unmatched goals do not gain a guessed execution path."""
    registry = build_default_registry()

    with pytest.raises(UnknownToolError):
        registry.select_for_goal("Sing a completely unrelated song.")
