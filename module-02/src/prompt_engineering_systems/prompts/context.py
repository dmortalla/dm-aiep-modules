"""Deterministic word-overlap selection with provenance and character budgets.

Scores count distinct case-folded Unicode word tokens shared with the query.
Ties preserve supplied order. Whole records that do not fit are skipped; later
records may still fit. This lexical demonstration uses no semantic retrieval,
token accounting, truncation, network, or executable content handling.
"""

import re
from typing import Self

from pydantic import ConfigDict, Field, ValidationError, model_validator

from ..contracts import StrictContract
from ..errors import PromptConstructionError


class ContextRecord(StrictContract):
    """One immutable context item with opaque identity and provenance.

    Attributes:
        record_id: Nonempty identity, at most 128 characters.
        provenance: Nonempty source label, at most 256 characters; never authority.
        content: Literal nonempty content, at most 4,096 characters.

    Raises:
        ValidationError: If direct construction violates strict fields or bounds.
    """

    model_config = ConfigDict(frozen=True)
    record_id: str = Field(min_length=1, max_length=128)
    provenance: str = Field(min_length=1, max_length=256)
    content: str = Field(min_length=1, max_length=4_096)


class ContextSelection(StrictContract):
    """Immutable selection in relevance order with original source metadata.

    Attributes:
        records: Whole selected records; at most 64.
        content_characters: Sum of selected content lengths, excluding metadata.
            The builder separately bounds all rendered message content.

    Raises:
        ValidationError: If direct construction violates strict fields or bounds.
    """

    model_config = ConfigDict(frozen=True)
    records: tuple[ContextRecord, ...] = Field(default=(), max_length=64)
    content_characters: int = Field(ge=0, le=32_768)


class _SelectionInput(StrictContract):
    """Validate the public selection boundary using the existing strict policy."""

    query: str = Field(max_length=12_289)
    records: tuple[ContextRecord, ...] = Field(max_length=64)
    character_budget: int = Field(ge=0, le=32_768)

    @model_validator(mode="after")
    def unique_records(self) -> Self:
        """Reject ambiguous provenance identities before selection.

        Returns:
            Validated candidate records in their original order.

        Raises:
            ValueError: If record identities repeat.
        """
        identifiers = [record.record_id for record in self.records]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Context record identities must be unique.")
        return self


def select_context(
    query: str,
    records: tuple[ContextRecord, ...],
    *,
    character_budget: int = 8_192,
) -> ContextSelection:
    """Select bounded whole records by lexical relevance, retaining provenance.

    Zero-overlap records remain eligible after higher scores. Python len counts
    Unicode code points, not UTF-8 bytes or tokens. A zero budget selects nothing.

    Args:
        query: Task/request text, at most 12,289 characters (including separator).
        records: At most 64 strictly typed records with unique identities.
        character_budget: Content-only ceiling, 0..32,768; default 8,192.

    Returns:
        Reproducible selection; equal scores keep original input order.

    Raises:
        PromptConstructionError: For invalid query, records, identities, or budget.
            Native Pydantic details are suppressed in rendered error chains.
    """
    try:
        data = _SelectionInput(
            query=query, records=records, character_budget=character_budget
        )
    except ValidationError:
        raise PromptConstructionError(
            "Use bounded context records with unique identities and a valid budget."
        ) from None
    query_words = set(re.findall(r"\w+", data.query.casefold()))
    ranked = sorted(
        data.records,
        key=lambda record: (
            -len(
                query_words.intersection(re.findall(r"\w+", record.content.casefold()))
            )
        ),
    )
    selected = []
    used = 0
    for record in ranked:
        size = len(record.content)
        if used + size <= data.character_budget:
            selected.append(record)
            used += size
    return ContextSelection(records=tuple(selected), content_characters=used)
