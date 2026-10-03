"""Deterministic, whole-chunk, budget-bounded context selection for generation.

Takes the ranked, deduplicated output of ``retrieval_workflow.py`` and selects
a bounded, ordered subset suitable for a later (Story 8) generation stage. This
module never truncates a chunk's content: whole-chunk selection keeps source
provenance and character offsets exact, trading a small amount of budget
precision for a materially simpler, easier-to-audit contract (see STORY_07.md's
"Context optimization" section for the documented trade-off). Budgeting is
character-based, never a fabricated token count, since no accepted tokenizer
contract exists in this repository. Excluded candidates are recorded with an
explicit, fixed reason; nothing is silently dropped.
"""

from dataclasses import dataclass, field

from .errors import ContextOptimizationError
from .retrieval_workflow import RetrievalCandidate

_EXCLUSION_REASONS = ("character_budget_exceeded", "chunk_count_exceeded")


@dataclass(frozen=True, slots=True)
class ContextOptimizationConfig:
    """Explicit, deterministic whole-chunk context-selection policy.

    Args:
        max_characters: Cumulative character budget across all included
            chunks' content, 1..1048576 (matching Story 2's own document
            content ceiling). This counts Unicode characters, not bytes or
            tokens.
        max_chunks: Hard cap on included chunk count, 1..4096 (matching
            Story 3's own chunk-count ceiling), enforced independently of the
            character budget.

    Raises:
        ContextOptimizationError: For invalid settings.
    """

    max_characters: int = 4_000
    max_chunks: int = 10

    def __post_init__(self) -> None:
        """Validate bounded settings before any candidate is considered."""
        if (
            type(self.max_characters) is not int
            or not 1 <= self.max_characters <= 1_048_576
        ):
            raise ContextOptimizationError(
                "Use an integer max_characters from 1 to 1048576."
            )
        if type(self.max_chunks) is not int or not 1 <= self.max_chunks <= 4_096:
            raise ContextOptimizationError("Use an integer max_chunks from 1 to 4096.")


@dataclass(frozen=True, slots=True)
class ContextItem:
    """One whole chunk included in the optimized context, with full evidence.

    Args:
        candidate: The retained RetrievalCandidate this item was selected
            from, hidden from repr to avoid incidental content exposure
            through logging; its content is reachable only through this
            object's own explicit ``content`` property.
        order: Zero-based, contiguous position in the final optimized context,
            preserving retrieval rank order.

    Raises:
        ContextOptimizationError: For a wrong candidate type or malformed
            order.
    """

    candidate: RetrievalCandidate = field(repr=False)
    order: int

    def __post_init__(self) -> None:
        """Validate the retained candidate and its contiguous position."""
        if type(self.candidate) is not RetrievalCandidate:
            raise ContextOptimizationError(
                "Supply a validated RetrievalCandidate."
            )
        if type(self.order) is not int or self.order < 0:
            raise ContextOptimizationError(
                "Use a zero-based nonnegative integer order."
            )

    @property
    def chunk_id(self) -> str:
        """Return the included chunk's stable identifier."""
        return self.candidate.chunk_id

    @property
    def document_id(self) -> str:
        """Return the included chunk's parent document identifier."""
        return self.candidate.document_id

    @property
    def score(self) -> float:
        """Return the candidate's retained retrieval score."""
        return self.candidate.score

    @property
    def produced_by(self) -> tuple[str, ...]:
        """Return which transformed queries surfaced this candidate, if any."""
        return self.candidate.produced_by

    @property
    def content(self) -> str:
        """Return this item's exact, unmodified, whole chunk content.

        This is the deliberate, explicit access point a later generation
        stage uses to assemble a prompt; it is never produced through this
        object's default repr.
        """
        return self.candidate.hit.record.chunk.content


@dataclass(frozen=True, slots=True)
class ExclusionRecord:
    """One candidate deliberately left out of the optimized context.

    Args:
        chunk_id: The excluded candidate's stable identifier; its content is
            never retained or rendered here.
        reason: Fixed, explicit exclusion reason: "character_budget_exceeded"
            or "chunk_count_exceeded".

    Raises:
        ContextOptimizationError: For an unknown reason or malformed
            identifier.
    """

    chunk_id: str
    reason: str

    def __post_init__(self) -> None:
        """Validate the identifier type and a fixed reason vocabulary."""
        if type(self.chunk_id) is not str or not self.chunk_id:
            raise ContextOptimizationError("Use a nonblank chunk_id string.")
        if self.reason not in _EXCLUSION_REASONS:
            raise ContextOptimizationError(
                "Use reason character_budget_exceeded or chunk_count_exceeded."
            )


@dataclass(frozen=True, slots=True)
class OptimizedContext:
    """Deterministic bounded whole-chunk context selection for generation.

    Args:
        items: Ordered tuple of 0..max_chunks included ContextItem objects,
            contiguous zero-based ``order``, preserving retrieval rank order.
            Zero items is a valid, meaningful outcome (for example, when even
            the best candidate exceeds the configured budget); this module
            never silently includes content that would violate the declared
            budget just to avoid an empty result.
        excluded: Ordered tuple of ExclusionRecord for every candidate left
            out, hidden from repr.
        config: The ContextOptimizationConfig that produced this selection,
            hidden from repr.
        total_characters: Sum of every included item's content length; never
            exceeds ``config.max_characters``.

    Raises:
        ContextOptimizationError: For wrong types, order gaps, or a budget
            violation.
    """

    items: tuple[ContextItem, ...]
    excluded: tuple[ExclusionRecord, ...] = field(repr=False)
    config: ContextOptimizationConfig = field(repr=False)
    total_characters: int

    def __post_init__(self) -> None:
        """Re-validate contiguous order, dedup, and the declared budget."""
        if type(self.config) is not ContextOptimizationConfig:
            raise ContextOptimizationError(
                "Supply a validated ContextOptimizationConfig."
            )
        if (
            type(self.items) is not tuple
            or len(self.items) > self.config.max_chunks
            or any(type(item) is not ContextItem for item in self.items)
        ):
            raise ContextOptimizationError(
                "Supply at most max_chunks validated ContextItem objects."
            )
        for index, item in enumerate(self.items):
            if item.order != index:
                raise ContextOptimizationError("Keep item order contiguous from zero.")
        ids = [item.chunk_id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ContextOptimizationError("Deduplicate included chunk_id values.")
        if (
            type(self.excluded) is not tuple
            or any(type(e) is not ExclusionRecord for e in self.excluded)
        ):
            raise ContextOptimizationError(
                "Supply a tuple of validated ExclusionRecord objects."
            )
        if type(self.total_characters) is not int or self.total_characters < 0:
            raise ContextOptimizationError(
                "Use a nonnegative integer total_characters."
            )
        if self.total_characters > self.config.max_characters:
            raise ContextOptimizationError(
                "total_characters must not exceed the configured budget."
            )
        if self.total_characters != sum(len(item.content) for item in self.items):
            raise ContextOptimizationError(
                "total_characters must equal the sum of included content lengths."
            )


_DEFAULT_CONFIG = ContextOptimizationConfig()


def optimize_context(
    candidates: tuple[RetrievalCandidate, ...],
    config: ContextOptimizationConfig = _DEFAULT_CONFIG,
) -> OptimizedContext:
    """Greedily select whole chunks in existing rank order within budget.

    Candidates are considered in the order supplied (the caller's own
    retrieval rank order; this function never re-ranks them). Selection stops
    at the first candidate that would exceed either limit: the character
    budget or the chunk count. That candidate and every candidate after it are
    recorded as excluded, with the reason that triggered the stop, so a lower-
    ranked but smaller chunk is never substituted ahead of a higher-ranked one
    that did not fit; this preserves retrieval rank fidelity over bin-packing
    efficiency.

    Args:
        candidates: Ranked, deduplicated candidates, typically
            ``RetrievalWorkflowResult.candidates`` or
            ``from_search_results(...)``.
        config: Validated deterministic budget/count policy.

    Returns:
        An OptimizedContext with the included items, the excluded candidates
        and their reasons, the config used, and the total character count.

    Raises:
        ContextOptimizationError: For invalid candidates or configuration.
    """
    if type(candidates) is not tuple or any(
        type(c) is not RetrievalCandidate for c in candidates
    ):
        raise ContextOptimizationError(
            "Supply a tuple of validated RetrievalCandidate objects."
        )
    if type(config) is not ContextOptimizationConfig:
        raise ContextOptimizationError("Supply a validated ContextOptimizationConfig.")

    included: list[ContextItem] = []
    excluded: list[ExclusionRecord] = []
    total = 0
    stop_reason: str | None = None
    for candidate in candidates:
        if stop_reason is None:
            length = len(candidate.hit.record.chunk.content)
            if len(included) >= config.max_chunks:
                stop_reason = "chunk_count_exceeded"
            elif total + length > config.max_characters:
                stop_reason = "character_budget_exceeded"
            else:
                included.append(ContextItem(candidate, len(included)))
                total += length
                continue
        excluded.append(ExclusionRecord(candidate.chunk_id, stop_reason))

    return OptimizedContext(tuple(included), tuple(excluded), config, total)
