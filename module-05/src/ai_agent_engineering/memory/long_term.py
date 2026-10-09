"""Provider-neutral long-term memory contracts."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class LongTermMemory:
    """Store durable application-owned facts by explicit key.

    This native implementation is deliberately provider-neutral. Story 5 may
    connect an external memory provider without giving remembered content
    application authority.
    """

    _facts: dict[str, str] = field(default_factory=dict, repr=False)

    def remember(self, key: str, content: str) -> None:
        """Store or replace one durable fact.

        Args:
            key: Application-owned lookup key.
            content: Fact content treated as untrusted data.

        Raises:
            ValueError: If the key or content is empty.
        """
        normalized_key = key.strip()
        normalized_content = content.strip()

        if not normalized_key:
            raise ValueError("Long-term memory key must not be empty.")
        if not normalized_content:
            raise ValueError("Long-term memory content must not be empty.")

        self._facts[normalized_key] = normalized_content

    def recall(self, key: str) -> str | None:
        """Recall one durable fact by exact application-owned key."""
        return self._facts.get(key.strip())

    def forget(self, key: str) -> bool:
        """Forget one fact.

        Returns:
            True when a stored fact was removed.
        """
        normalized_key = key.strip()
        if normalized_key in self._facts:
            del self._facts[normalized_key]
            return True
        return False

    def snapshot(self) -> dict[str, str]:
        """Return a defensive copy of durable facts."""
        return dict(self._facts)

    def __len__(self) -> int:
        """Return the number of durable facts."""
        return len(self._facts)
