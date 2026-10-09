"""Typed domain models for agent execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4


class AgentStatus(StrEnum):
    """Finite lifecycle states for an autonomous agent run."""

    RECEIVED = "received"
    INITIALIZED = "initialized"
    CONTEXT_READY = "context_ready"
    REASONING = "reasoning"
    TOOL_SELECTED = "tool_selected"
    VALIDATED = "validated"
    EXECUTING = "executing"
    OBSERVED = "observed"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    BUDGET_EXHAUSTED = "budget_exhausted"


@dataclass(slots=True)
class AgentRunState:
    """Application-owned state for one bounded agent execution.

    Args:
        goal: User goal driving the autonomous run.
        max_steps: Maximum number of execution-loop steps permitted.
        run_id: Unique identifier for this run.
        status: Current lifecycle status.
        current_step: Number of execution steps consumed.
        observations: Validated observations collected during execution.
        selected_tools: Names of tools selected during execution.
        short_term_context: Run-scoped working context.
        retrieved_long_term_memories: Retrieved cross-run memory context.
        episodic_events: Structured events describing the run.
        retry_count: Number of retry attempts consumed.
        fallback_history: Fallback paths used during the run.
        final_result: Final successful result, when available.
        terminal_failure: Terminal failure description, when available.

    Raises:
        ValueError: If the goal is empty or max_steps is less than one.
    """

    goal: str
    max_steps: int = 8
    run_id: str = field(default_factory=lambda: str(uuid4()))
    status: AgentStatus = AgentStatus.RECEIVED
    current_step: int = 0
    observations: list[Any] = field(default_factory=list)
    selected_tools: list[str] = field(default_factory=list)
    short_term_context: dict[str, Any] = field(default_factory=dict)
    retrieved_long_term_memories: list[Any] = field(default_factory=list)
    episodic_events: list[dict[str, Any]] = field(default_factory=list)
    retry_count: int = 0
    fallback_history: list[str] = field(default_factory=list)
    final_result: Any | None = None
    terminal_failure: str | None = None

    def __post_init__(self) -> None:
        """Validate construction invariants."""
        normalized_goal = self.goal.strip()
        if not normalized_goal:
            raise ValueError("Agent goal must not be empty.")
        if self.max_steps < 1:
            raise ValueError("max_steps must be at least 1.")

        self.goal = normalized_goal

    @property
    def is_terminal(self) -> bool:
        """Return whether the run is in a terminal lifecycle state."""
        return self.status in {
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
            AgentStatus.TIMED_OUT,
            AgentStatus.BUDGET_EXHAUSTED,
        }

    @property
    def steps_remaining(self) -> int:
        """Return the remaining bounded execution-step budget."""
        return max(self.max_steps - self.current_step, 0)

    def consume_step(self) -> None:
        """Consume one execution step without exceeding the configured budget.

        Raises:
            RuntimeError: If no execution-step budget remains.
        """
        if self.steps_remaining == 0:
            raise RuntimeError("Agent execution-step budget is exhausted.")

        self.current_step += 1
