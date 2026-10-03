"""Deterministic, provider-neutral query transformation ahead of retrieval.

This module only ever reads the application's own original query text. It never
reads retrieved chunk content or metadata, so retrieved/external content cannot
influence, decompose, or expand a query: that boundary is structural, not a
runtime check. Every technique here is deterministic and requires no live model;
``QueryExpander`` is an explicit, provider-neutral extensibility seam an
application may fill with a future model-backed transformer through dependency
injection, never a requirement for normal offline testing.
"""

from dataclasses import dataclass, field
from typing import Protocol

from .embeddings import validate_texts
from .errors import EmbeddingError, QuerySignalError, QueryTransformationError

MAX_QUERIES = 32
MAX_SEPARATORS = 8


def _validate_query_text(text: str, error: type[QueryTransformationError]) -> None:
    """Reuse Story 4's bounded nonblank-text rules for one query string."""
    try:
        validate_texts((text,))
    except EmbeddingError as exc:
        raise error(
            "Supply a nonblank query string, at most Story 4's per-text byte bound."
        ) from exc


class QueryExpander(Protocol):
    """Application-selected deterministic alternate-formulation generator.

    Implementations must be deterministic for reproducible retrieval. They
    receive the application's own query text, never retrieved document content,
    and must treat that text as data, not instructions. No default or
    model-backed implementation is supplied by this module; a later story may
    inject an LLM-backed expander without changing this protocol.
    """

    def __call__(self, text: str) -> tuple[str, ...]:
        """Return zero or more additional retrieval-oriented formulations.

        Args:
            text: Exact base query text (already normalized, or one decomposed
                part), in input order.

        Returns:
            Zero or more nonblank alternate formulations, in preferred order.

        Raises:
            Exception: Implementation-specific failures translated at the
                boundary into QuerySignalError.
        """
        ...


@dataclass(frozen=True, slots=True)
class QueryTransformConfig:
    """Explicit, deterministic, fully offline-by-default transformation policy.

    Args:
        separators: 0..8 unique nonempty literal strings, each <=32 characters,
            used to decompose a normalized query into retrieval-oriented
            subqueries; an empty tuple (the default) disables decomposition.
        expander: Optional deterministic QueryExpander; None (the default)
            performs no expansion, so normal use requires no live model.
        max_queries: Hard bound on total derived queries after decomposition
            and expansion, 1..32; default 8.

    Raises:
        QueryTransformationError: For invalid settings.
    """

    separators: tuple[str, ...] = field(default=(), repr=False)
    expander: QueryExpander | None = None
    max_queries: int = 8

    def __post_init__(self) -> None:
        """Validate bounded configuration before any text is transformed."""
        if (
            type(self.separators) is not tuple
            or len(self.separators) > MAX_SEPARATORS
            or any(
                type(s) is not str or not 1 <= len(s) <= 32 for s in self.separators
            )
            or len(set(self.separators)) != len(self.separators)
        ):
            raise QueryTransformationError(
                "Supply 0..8 unique nonempty literal separators, each <=32 chars."
            )
        if self.expander is not None and not callable(self.expander):
            raise QueryTransformationError(
                "Supply a callable QueryExpander or leave expansion disabled."
            )
        if (
            type(self.max_queries) is not int
            or not 1 <= self.max_queries <= MAX_QUERIES
        ):
            raise QueryTransformationError("Use an integer max_queries from 1 to 32.")


@dataclass(frozen=True, slots=True)
class TransformedQuery:
    """One deterministic retrieval-oriented query derived from the original.

    Args:
        text: Nonblank derived retrieval query text, hidden from repr to avoid
            incidental exposure through logging; reachable only through this
            field's explicit access.
        technique: Deterministic technique that produced this text: "normalize",
            "decompose", or "expand".

    Raises:
        QueryTransformationError: For blank/oversized text or an unknown
            technique.
    """

    text: str = field(repr=False)
    technique: str

    def __post_init__(self) -> None:
        """Validate text bounds and a fixed technique vocabulary."""
        _validate_query_text(self.text, QueryTransformationError)
        if self.technique not in ("normalize", "decompose", "expand"):
            raise QueryTransformationError(
                "Use technique normalize, decompose, or expand."
            )


@dataclass(frozen=True, slots=True)
class QueryTransformationResult:
    """Complete deterministic transformation outcome for one original query.

    Args:
        original_query: The exact, unmodified caller-supplied query text,
            preserved verbatim and hidden from repr.
        queries: Ordered, deduplicated tuple of 1..32 TransformedQuery objects,
            in deterministic production order (normalize, then decompose, then
            expand), suitable for embedding in that same order.

    Raises:
        QueryTransformationError: For wrong types, empty output, or duplicate
            derived text.
    """

    original_query: str = field(repr=False)
    queries: tuple[TransformedQuery, ...]

    def __post_init__(self) -> None:
        """Validate the original query and the bounded, deduplicated output."""
        _validate_query_text(self.original_query, QueryTransformationError)
        if (
            type(self.queries) is not tuple
            or not 1 <= len(self.queries) <= MAX_QUERIES
            or any(type(q) is not TransformedQuery for q in self.queries)
        ):
            raise QueryTransformationError(
                "Supply a tuple of 1..32 validated TransformedQuery objects."
            )
        texts = [q.text for q in self.queries]
        if len(set(texts)) != len(texts):
            raise QueryTransformationError(
                "Deduplicate derived query text before building the result."
            )


def _normalize(text: str) -> str:
    """Collapse runs of whitespace and strip the ends, without case-folding.

    Embedders may casefold internally (see LocalHashEmbedder); this layer only
    removes incidental whitespace noise so identical queries compare equal.
    """
    return " ".join(text.split())


def _decompose(text: str, separators: tuple[str, ...]) -> list[str]:
    """Split on literal separators only, left to right; never uses regex.

    Each configured separator is applied in turn to every part produced by the
    previous separator, so declaration order does not establish priority: any
    configured separator breaks the text into a new part wherever it occurs.
    """
    parts = [text]
    for separator in separators:
        next_parts: list[str] = []
        for part in parts:
            next_parts.extend(part.split(separator))
        parts = next_parts
    return [part.strip() for part in parts if part.strip()]


_DEFAULT_CONFIG = QueryTransformConfig()


def transform_query(
    text: str, config: QueryTransformConfig = _DEFAULT_CONFIG
) -> QueryTransformationResult:
    """Normalize, optionally decompose, and optionally expand one user query.

    The original query is always preserved verbatim in the result. Decomposed
    or expanded text is never re-fed into itself (no recursive decomposition or
    expansion), keeping the technique bounded and easy to explain. Query text
    is always the application's own query; this function never reads retrieved
    document content, so it cannot reinterpret retrieved content as
    instructions.

    Args:
        text: Original, untrusted-as-content (but application-authored) query
            text; treated as data throughout.
        config: Validated deterministic transformation policy.

    Returns:
        A QueryTransformationResult preserving the original query plus an
        ordered, deduplicated, bounded tuple of derived retrieval queries.

    Raises:
        QueryTransformationError: For invalid input/configuration, an
            oversized derived-query count, or malformed expander output.
        QuerySignalError: If the configured expander raises or returns a
            malformed formulation.
    """
    _validate_query_text(text, QueryTransformationError)
    if type(config) is not QueryTransformConfig:
        raise QueryTransformationError("Supply a validated QueryTransformConfig.")

    normalized = _normalize(text)
    parts = _decompose(normalized, config.separators) if config.separators else []
    if len(parts) <= 1:
        bases = [(normalized, "normalize")]
    else:
        bases = [(part, "decompose") for part in parts]

    derived: list[TransformedQuery] = []
    seen: set[str] = set()
    for base_text, technique in bases:
        if base_text not in seen:
            seen.add(base_text)
            derived.append(TransformedQuery(base_text, technique))
        if config.expander is not None:
            try:
                formulations = config.expander(base_text)
            except Exception:
                raise QuerySignalError(
                    "Query expander failed; repair its implementation or adapter."
                ) from None
            if type(formulations) is not tuple or any(
                type(f) is not str for f in formulations
            ):
                raise QuerySignalError(
                    "Query expander must return a tuple of strings."
                )
            for formulation in formulations:
                if formulation not in seen:
                    seen.add(formulation)
                    derived.append(TransformedQuery(formulation, "expand"))

    if len(derived) > config.max_queries:
        raise QueryTransformationError(
            "Reduce decomposition/expansion so total derived queries fit"
            " max_queries; increase max_queries or narrow the policy instead."
        )
    return QueryTransformationResult(text, tuple(derived))
