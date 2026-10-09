"""Structured episodic memory for prior agent experiences."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class Episode:
    """One immutable record of a prior agent experience."""

    goal: str
    outcome: str
    tools: tuple[str, ...] = ()
    episode_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate required episode fields."""
        goal = self.goal.strip()
        outcome = self.outcome.strip()

        if not goal:
            raise ValueError("Episode goal must not be empty.")
        if not outcome:
            raise ValueError("Episode outcome must not be empty.")

        object.__setattr__(self, "goal", goal)
        object.__setattr__(self, "outcome", outcome)


@dataclass(slots=True)
class EpisodicMemory:
    """Maintain a bounded history of prior agent experiences."""

    max_episodes: int = 50
    _episodes: list[Episode] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        """Validate the episode bound."""
        if self.max_episodes < 1:
            raise ValueError("Episodic memory max_episodes must be positive.")

    def remember(self, episode: Episode) -> None:
        """Store one episode while enforcing the configured bound."""
        if not isinstance(episode, Episode):
            raise TypeError("Episodic memory accepts Episode objects only.")

        self._episodes.append(episode)

        overflow = len(self._episodes) - self.max_episodes
        if overflow > 0:
            del self._episodes[:overflow]

    def recent(self, limit: int | None = None) -> tuple[Episode, ...]:
        """Return recent episodes in chronological order.

        Args:
            limit: Optional maximum number of newest episodes.

        Raises:
            ValueError: If limit is less than one.
        """
        if limit is None:
            return tuple(self._episodes)

        if limit < 1:
            raise ValueError("Episode recall limit must be positive.")

        return tuple(self._episodes[-limit:])

    def __len__(self) -> int:
        """Return the number of retained episodes."""
        return len(self._episodes)
