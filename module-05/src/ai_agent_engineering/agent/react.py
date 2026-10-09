"""Application-visible decision records for bounded ReAct execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class DecisionKind(StrEnum):
    """Kinds of application-visible agent decisions."""

    TOOL = "tool"
    FINISH = "finish"


@dataclass(frozen=True, slots=True)
class AgentDecision:
    """One explicit application-visible decision.

    This record represents an agent action decision, not private chain-of-thought.

    Args:
        kind: Whether to invoke a tool or finish the run.
        rationale: Concise application-visible reason for the decision.
        tool_name: Proposed allowlisted tool name for tool decisions.
        arguments: Proposed structured tool arguments.
        final_result: Final response for finish decisions.

    Raises:
        ValueError: If the decision shape is inconsistent with its kind.
    """

    kind: DecisionKind
    rationale: str
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None
    final_result: str | None = None

    def __post_init__(self) -> None:
        """Validate the decision contract."""
        rationale = self.rationale.strip()

        if not rationale:
            raise ValueError("Decision rationale must not be empty.")

        object.__setattr__(self, "rationale", rationale)

        if self.kind is DecisionKind.TOOL:
            if not self.tool_name:
                raise ValueError("Tool decisions require a tool name.")
            if self.arguments is None:
                raise ValueError("Tool decisions require structured arguments.")
            if self.final_result is not None:
                raise ValueError("Tool decisions cannot contain a final result.")
            return

        if self.kind is DecisionKind.FINISH:
            if self.tool_name is not None or self.arguments is not None:
                raise ValueError("Finish decisions cannot contain a tool call.")
            if not self.final_result or not self.final_result.strip():
                raise ValueError("Finish decisions require a final result.")
            object.__setattr__(self, "final_result", self.final_result.strip())
            return

        raise ValueError(f"Unsupported decision kind: {self.kind!r}")


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    """Auditable application-visible record of one decision step."""

    step: int
    kind: DecisionKind
    rationale: str
    tool_name: str | None = None
