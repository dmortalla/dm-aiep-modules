"""Bounded short-term memory for the active agent run."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass(slots=True)
class ShortTermMemory:
    """Maintain bounded context for the current run or session.

    Args:
        max_items: Maximum number of context items retained.

    Raises:
        ValueError: If the configured bound is invalid.
    """

    max_items: int = 20
    _items: deque[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize bounded storage."""
        if self.max_items < 1:
            raise ValueError("Short-term memory max_items must be positive.")

        self._items = deque(maxlen=self.max_items)

    def remember(self, content: str) -> None:
        """Store one non-empty context item.

        Args:
            content: Context text to retain.

        Raises:
            ValueError: If content is empty.
        """
        normalized = content.strip()
        if not normalized:
            raise ValueError("Short-term memory content must not be empty.")

        self._items.append(normalized)

    def recall(self) -> tuple[str, ...]:
        """Return current context in insertion order."""
        return tuple(self._items)

    def clear(self) -> None:
        """Clear current-run context."""
        self._items.clear()

    def __len__(self) -> int:
        """Return the number of retained context items."""
        return len(self._items)
