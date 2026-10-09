"""Allowlisted registry and orchestration boundary for agent tools."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .schemas import ToolDefinition


class UnknownToolError(LookupError):
    """Raised when untrusted input requests a tool outside the allowlist."""


class DuplicateToolError(ValueError):
    """Raised when a registry receives duplicate stable tool names."""


class ToolRegistry:
    """Application-owned allowlist of tools available to an agent."""

    def __init__(self, tools: Iterable[ToolDefinition] = ()) -> None:
        """Create a registry from explicit application-owned definitions.

        Args:
            tools: Tool definitions permitted to exist in the registry.

        Raises:
            DuplicateToolError: If two definitions use the same name.
        """
        self._tools: dict[str, ToolDefinition] = {}

        for tool in tools:
            self.register(tool)

    def register(self, tool: ToolDefinition) -> None:
        """Register one explicitly approved tool definition.

        Args:
            tool: Application-owned tool definition.

        Raises:
            DuplicateToolError: If its stable name is already registered.
        """
        if tool.name in self._tools:
            raise DuplicateToolError(
                f"Tool '{tool.name}' is already registered."
            )

        self._tools[tool.name] = tool

    def names(self) -> tuple[str, ...]:
        """Return registered allowlisted tool names in stable sorted order."""
        return tuple(sorted(self._tools))

    def definitions(self) -> tuple[ToolDefinition, ...]:
        """Return registered definitions in stable name order."""
        return tuple(self._tools[name] for name in self.names())

    def get(self, name: str) -> ToolDefinition:
        """Resolve a tool only if its exact name is allowlisted.

        Args:
            name: Untrusted proposed tool name.

        Returns:
            Registered application-owned tool definition.

        Raises:
            UnknownToolError: If the name is malformed or not registered.
        """
        if not isinstance(name, str) or name not in self._tools:
            raise UnknownToolError(
                f"Tool is not present in the application allowlist: {name!r}"
            )

        return self._tools[name]

    def validate_call(
        self,
        name: str,
        arguments: Mapping[str, Any],
    ) -> tuple[ToolDefinition, dict[str, Any]]:
        """Resolve and validate a proposed tool call without executing it.

        Args:
            name: Untrusted proposed tool name.
            arguments: Untrusted proposed arguments.

        Returns:
            Resolved tool definition and validated copied arguments.
        """
        tool = self.get(name)

        if not tool.authorized:
            from .schemas import ToolAuthorizationError

            raise ToolAuthorizationError(
                f"Tool '{tool.name}' is not authorized for execution."
            )

        return tool, tool.validate_arguments(arguments)

    def execute(
        self,
        name: str,
        arguments: Mapping[str, Any],
    ) -> Any:
        """Resolve, authorize, validate, and execute one tool call.

        Args:
            name: Untrusted proposed tool name.
            arguments: Untrusted proposed arguments.

        Returns:
            Validated tool execution result.
        """
        tool, validated = self.validate_call(name, arguments)
        return tool.handler(validated)

    def select_for_goal(self, goal: str) -> ToolDefinition:
        """Select a deterministic tool candidate from a goal.

        This is a safe local selection primitive for Story 2. Later agent and
        provider stories may propose selections dynamically, but all proposed
        names must still resolve through this registry.

        Args:
            goal: Goal text used to select an allowlisted candidate.

        Returns:
            Selected application-owned tool definition.

        Raises:
            UnknownToolError: If no deterministic candidate can be selected.
        """
        normalized = goal.casefold()

        calculator_terms = (
            "calculate",
            "calculator",
            "math",
            "sum",
            "add",
            "subtract",
            "multiply",
            "divide",
        )
        knowledge_terms = (
            "knowledge",
            "lookup",
            "research",
            "explain",
            "what is",
        )
        note_terms = (
            "note",
            "remember",
            "context",
        )

        if any(term in normalized for term in calculator_terms):
            return self.get("calculator")

        if any(term in normalized for term in note_terms):
            return self.get("note_lookup")

        if any(term in normalized for term in knowledge_terms):
            return self.get("knowledge_lookup")

        raise UnknownToolError(
            "No allowlisted tool candidate matched the supplied goal."
        )
