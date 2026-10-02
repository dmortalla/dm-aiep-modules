"""Trusted local-tool permissions and budgets, independent of detector findings.

Application code owns policy creation and session lifetimes. Never deserialize
policy from user, context, or model content. Typed shape validation establishes
neither trust provenance nor permission to change application configuration.
"""

from typing import Literal, Self

from pydantic import ConfigDict, Field, model_validator

from ..contracts import StrictContract

type ToolIdentifier = Literal["add", "text_statistics"]


class SafetyPolicy(StrictContract):
    """Immutable application-owned permissions for sequential local execution.

    Defaults deny tools. Hard bounds keep this instructional session small.
    Detection findings do not participate in authorization decisions.

    Attributes:
        allowed_tools: Up to two unique registered identifiers; defaults empty.
        max_executions: Permitted handler invocations, 0..16; default three.
        max_text_characters: Text-statistics argument ceiling, 0..4,096;
            default 1,024 Python characters, not bytes/tokens.

    Raises:
        ValidationError: For invalid strict fields, bounds, or duplicate tools.
            Direct Pydantic diagnostics must not be exposed to external callers.
    """

    model_config = ConfigDict(frozen=True)
    allowed_tools: tuple[ToolIdentifier, ...] = Field(default=(), max_length=2)
    max_executions: int = Field(default=3, ge=0, le=16)
    max_text_characters: int = Field(default=1_024, ge=0, le=4_096)

    @model_validator(mode="after")
    def unique_tools(self) -> Self:
        """Reject ambiguous repeated permissions.

        Returns:
            This validated policy.

        Raises:
            ValueError: If allowed identifiers repeat.
        """
        if len(set(self.allowed_tools)) != len(self.allowed_tools):
            raise ValueError("Allowed tool identifiers must be unique.")
        return self
