"""Typed contracts for safe agent tools."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import jsonschema

ToolHandler = Callable[[Mapping[str, Any]], Any]


class ToolValidationError(ValueError):
    """Raised when proposed tool arguments violate the application schema."""


class ToolAuthorizationError(PermissionError):
    """Raised when a tool is not authorized for execution."""


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Application-owned definition of an executable agent tool.

    Args:
        name: Stable tool identifier.
        description: Human/model-facing explanation of the tool.
        input_schema: JSON Schema describing accepted arguments.
        handler: Application-owned execution callable.
        authorized: Whether execution is currently permitted.

    Raises:
        ValueError: If required metadata is missing or malformed.
        jsonschema.SchemaError: If the supplied JSON Schema is invalid.
    """

    name: str
    description: str
    input_schema: Mapping[str, Any]
    handler: ToolHandler
    authorized: bool = True

    def __post_init__(self) -> None:
        """Validate and freeze the application-owned tool contract."""
        name = self.name.strip()
        description = self.description.strip()

        if not name:
            raise ValueError("Tool name must not be empty.")
        if not description:
            raise ValueError("Tool description must not be empty.")
        if not callable(self.handler):
            raise ValueError("Tool handler must be callable.")

        schema = dict(self.input_schema)
        jsonschema.Draft202012Validator.check_schema(schema)

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "input_schema", MappingProxyType(schema))

    def validate_arguments(
        self,
        arguments: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Validate proposed arguments without executing the tool.

        Args:
            arguments: Untrusted proposed tool arguments.

        Returns:
            A copied dictionary containing validated arguments.

        Raises:
            ToolValidationError: If arguments are not mapping-shaped or fail
                the tool's JSON Schema.
        """
        if not isinstance(arguments, Mapping):
            raise ToolValidationError(
                f"Arguments for tool '{self.name}' must be an object."
            )

        copied = dict(arguments)

        try:
            jsonschema.validate(
                instance=copied,
                schema=dict(self.input_schema),
            )
        except jsonschema.ValidationError as exc:
            raise ToolValidationError(
                f"Invalid arguments for tool '{self.name}': {exc.message}"
            ) from exc

        return copied

    def execute(self, arguments: Mapping[str, Any]) -> Any:
        """Validate authorization and arguments before invoking the handler.

        Args:
            arguments: Untrusted proposed tool arguments.

        Returns:
            Tool handler result.

        Raises:
            ToolAuthorizationError: If this tool is not authorized.
            ToolValidationError: If arguments fail validation.
        """
        if not self.authorized:
            raise ToolAuthorizationError(
                f"Tool '{self.name}' is not authorized for execution."
            )

        validated = self.validate_arguments(arguments)
        return self.handler(validated)
