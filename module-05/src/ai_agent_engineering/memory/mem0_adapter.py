"""Narrow Mem0 integration boundary for Module 5."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Protocol, runtime_checkable


class Mem0IntegrationError(RuntimeError):
    """Raised when the Mem0 integration boundary cannot operate safely."""


@runtime_checkable
class Mem0Backend(Protocol):
    """Minimum external behavior required by the application adapter."""

    def add(
        self,
        messages: list[dict[str, str]],
        *,
        user_id: str,
    ) -> Any:
        """Store memory for one explicit application-owned user identifier."""
        ...

    def search(
        self,
        query: str,
        *,
        filters: dict[str, Any],
    ) -> Any:
        """Search memory using explicit application-owned filters."""
        ...


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """Application-owned normalized representation of recalled memory."""

    content: str
    memory_id: str | None = None
    score: float | None = None


class Mem0MemoryAdapter:
    """Adapt Mem0 memory behavior to an application-owned contract.

    External memory content is always returned as data. It does not grant
    tool, lifecycle, credential, authorization, or execution authority.

    Args:
        backend: Object implementing the minimal Mem0 backend behavior.
    """

    def __init__(self, backend: Mem0Backend) -> None:
        """Initialize the adapter with an explicit backend."""
        if backend is None:
            raise ValueError("Mem0 backend must not be None.")

        self._backend = backend

    @classmethod
    def from_default_mem0(cls) -> Mem0MemoryAdapter:
        """Create an adapter using the installed Mem0 package.

        Import is intentionally lazy so importing Module 5 does not require
        Mem0 and cannot itself trigger provider initialization or paid calls.

        Returns:
            Adapter backed by ``mem0.Memory``.

        Raises:
            Mem0IntegrationError: If Mem0 is unavailable or cannot initialize.
        """
        try:
            module = import_module("mem0")
            memory_class = module.Memory
            backend = memory_class()
        except (ImportError, AttributeError, TypeError, ValueError) as exc:
            raise Mem0IntegrationError(
                "Mem0 is unavailable or could not be initialized."
            ) from exc

        return cls(backend)

    def remember(
        self,
        *,
        user_id: str,
        content: str,
    ) -> Any:
        """Store one memory through Mem0.

        Args:
            user_id: Explicit application-owned memory namespace.
            content: Memory text treated as untrusted data.

        Returns:
            Raw provider acknowledgement for observability.

        Raises:
            ValueError: If user_id or content is empty.
            Mem0IntegrationError: If the backend operation fails.
        """
        normalized_user = self._require_text(user_id, "user_id")
        normalized_content = self._require_text(content, "content")

        messages = [
            {
                "role": "user",
                "content": normalized_content,
            }
        ]

        try:
            return self._backend.add(
                messages,
                user_id=normalized_user,
            )
        except Exception as exc:
            raise Mem0IntegrationError(
                "Mem0 remember operation failed."
            ) from exc

    def recall(
        self,
        *,
        user_id: str,
        query: str,
    ) -> tuple[MemoryRecord, ...]:
        """Search Mem0 and normalize results into application-owned records.

        Mem0's current search API scopes identities through ``filters`` rather
        than a dedicated ``user_id`` keyword argument. The application-facing
        contract deliberately remains ``user_id`` so provider API details do
        not leak into the rest of Module 5.

        Args:
            user_id: Explicit application-owned memory namespace.
            query: Search query.

        Returns:
            Immutable normalized memory records.

        Raises:
            ValueError: If user_id or query is empty.
            Mem0IntegrationError: If search fails or returns an unsafe shape.
        """
        normalized_user = self._require_text(user_id, "user_id")
        normalized_query = self._require_text(query, "query")

        try:
            raw = self._backend.search(
                normalized_query,
                filters={"user_id": normalized_user},
            )
        except Exception as exc:
            raise Mem0IntegrationError(
                "Mem0 recall operation failed."
            ) from exc

        return self._normalize_search_results(raw)

    @staticmethod
    def _require_text(value: str, field_name: str) -> str:
        """Validate one required text value."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must not be empty.")
        return value.strip()

    @classmethod
    def _normalize_search_results(
        cls,
        raw: Any,
    ) -> tuple[MemoryRecord, ...]:
        """Normalize supported Mem0 result envelopes."""
        if isinstance(raw, Mapping):
            if "results" not in raw:
                raise Mem0IntegrationError(
                    "Mem0 search response is missing results."
                )
            raw_results = raw["results"]
        else:
            raw_results = raw

        if not isinstance(raw_results, list):
            raise Mem0IntegrationError(
                "Mem0 search results must be a list."
            )

        normalized: list[MemoryRecord] = []

        for item in raw_results:
            if not isinstance(item, Mapping):
                raise Mem0IntegrationError(
                    "Mem0 search result must be an object."
                )

            content = item.get("memory")

            if not isinstance(content, str) or not content.strip():
                raise Mem0IntegrationError(
                    "Mem0 search result is missing memory text."
                )

            memory_id = item.get("id")
            if memory_id is not None and not isinstance(memory_id, str):
                memory_id = str(memory_id)

            score = item.get("score")
            if score is not None:
                if isinstance(score, bool) or not isinstance(
                    score,
                    (int, float),
                ):
                    raise Mem0IntegrationError(
                        "Mem0 search result score must be numeric."
                    )
                score = float(score)

            normalized.append(
                MemoryRecord(
                    content=content.strip(),
                    memory_id=memory_id,
                    score=score,
                )
            )

        return tuple(normalized)
