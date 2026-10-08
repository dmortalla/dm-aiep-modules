"""Deterministic relevance-threshold context filtering (M4-OPT-01).

This is a Module 4-native pre-stage over Story 4's ``reranking.RerankedResults``.
It implements inspectable, deterministic, exclusion-reasoned filtering
natively over Story 3/4's ``HybridCandidate``/``RerankedCandidate`` evidence
(BM25 + semantic fusion + reranking); Module 4 owns this stage and imports
no earlier academic module (Rule 44). See ``module-04/docs/STORY_05.md``.

Filtering is relevance/context control only: a retained or excluded
candidate's chunk content is never read to make the filtering decision
(only ``rerank_score`` and candidate count are consulted), so candidate text
can never alter filtering policy. Retrieved content remains untrusted,
inert data throughout.
"""

import math
from dataclasses import dataclass, field

from .corpus import CorpusChunk
from .errors import ContextFilterConfigurationError, ContextFilterError
from .reranking import RerankedCandidate, RerankedResults

MAX_CANDIDATES = 10_000
_EXCLUSION_REASONS = ("below_score_threshold", "candidate_count_exceeded")


@dataclass(frozen=True, slots=True)
class ContextFilterConfig:
    """Application-owned deterministic relevance-threshold filtering policy.

    ``min_rerank_score`` is compared directly against each candidate's
    Story 4 ``rerank_score``, whose scale depends entirely on the scorer
    that produced it (``DeterministicOverlapScorer`` returns ``[0, 1]``; a
    genuine cross-encoder returns unbounded, often-negative logits). This
    threshold is never auto-calibrated and the generic default disables it
    entirely (``-inf``), so a scorer-neutral default can never silently
    discard a candidate just because one particular scorer happens to use a
    nonnegative scale: an application that wants score-threshold filtering
    must explicitly choose a threshold appropriate to its chosen scorer's
    scale (for example ``0.0`` for ``DeterministicOverlapScorer``, or a
    negative value for a genuine cross-encoder's logits).

    Args:
        min_rerank_score: Inclusive lower bound; a candidate scoring exactly
            this value is retained. Default ``float("-inf")``, which
            disables score-threshold filtering (only ``max_candidates``
            applies) until an application supplies a scorer-appropriate
            value.
        max_candidates: Hard cap on retained candidate count, 1..10000,
            applied after the score threshold, in existing rerank order.
            Default 10.

    Raises:
        ContextFilterConfigurationError: For invalid settings.
    """

    min_rerank_score: float = float("-inf")
    max_candidates: int = 10

    def __post_init__(self) -> None:
        """Validate bounded settings before any candidate is considered."""
        if type(self.min_rerank_score) not in (int, float) or type(
            self.min_rerank_score
        ) is bool:
            raise ContextFilterConfigurationError(
                "Use a numeric min_rerank_score threshold."
            )
        if math.isnan(self.min_rerank_score) or self.min_rerank_score == float("inf"):
            raise ContextFilterConfigurationError(
                "Use a finite min_rerank_score, or -inf to disable the threshold."
            )
        if (
            type(self.max_candidates) is not int
            or type(self.max_candidates) is bool
            or not 1 <= self.max_candidates <= MAX_CANDIDATES
        ):
            raise ContextFilterConfigurationError(
                "Use an integer max_candidates from 1 to 10000."
            )


_DEFAULT_CONFIG = ContextFilterConfig()


@dataclass(frozen=True, slots=True)
class ContextFilterItem:
    """One retained candidate, with every upstream evidence field reachable.

    Args:
        order: Zero-based contiguous position among retained items,
            preserving Story 4's rerank order.
        candidate: The retained Story 4 RerankedCandidate, hidden from repr
            to avoid incidental content exposure; its chunk content is
            reachable only through ``item.chunk.content``.

    Raises:
        ContextFilterError: For a malformed order or wrong candidate type.
    """

    order: int
    candidate: RerankedCandidate = field(repr=False)

    def __post_init__(self) -> None:
        """Validate retained-item shape without rendering retrieved content."""
        if type(self.order) is not int or self.order < 0:
            raise ContextFilterError("Use a zero-based nonnegative integer order.")
        if type(self.candidate) is not RerankedCandidate:
            raise ContextFilterError("Supply a validated Story 4 RerankedCandidate.")

    @property
    def chunk(self) -> CorpusChunk:
        """Return the retained chunk; content is reachable only through this path."""
        return self.candidate.chunk

    @property
    def chunk_id(self) -> str:
        """Return the stable chunk identifier, unchanged from Story 2/3/4."""
        return self.candidate.chunk_id

    @property
    def document_id(self) -> str:
        """Return the parent document identifier, unchanged from Story 2/3/4."""
        return self.candidate.document_id

    @property
    def hybrid_rank(self) -> int:
        """Return the chunk's pre-rerank (Story 3 fused) rank, unchanged."""
        return self.candidate.hybrid_rank

    @property
    def rrf_score(self) -> float:
        """Return the chunk's Story 3 Reciprocal Rank Fusion score, unchanged."""
        return self.candidate.rrf_score

    @property
    def rerank_rank(self) -> int:
        """Return the chunk's Story 4 post-rerank rank, unchanged."""
        return self.candidate.rank

    @property
    def rerank_score(self) -> float:
        """Return the chunk's Story 4 reranker score, unchanged."""
        return self.candidate.rerank_score


@dataclass(frozen=True, slots=True)
class FilterExclusion:
    """One candidate deliberately excluded, with an explicit, fixed reason.

    Args:
        chunk_id: The excluded candidate's stable identifier; content is
            never retained or rendered here.
        reason: Fixed reason: "below_score_threshold" or
            "candidate_count_exceeded".

    Raises:
        ContextFilterError: For an unknown reason or malformed identifier.
    """

    chunk_id: str
    reason: str

    def __post_init__(self) -> None:
        """Validate the identifier type and a fixed reason vocabulary."""
        if type(self.chunk_id) is not str or not self.chunk_id:
            raise ContextFilterError("Use a nonblank chunk_id string.")
        if self.reason not in _EXCLUSION_REASONS:
            raise ContextFilterError(
                "Use reason below_score_threshold or candidate_count_exceeded."
            )


@dataclass(frozen=True, slots=True)
class FilteredContext:
    """Deterministic, bounded, reason-evidenced context-filtering outcome.

    Args:
        items: Ordered tuple of 0..max_candidates retained ContextFilterItem
            objects, contiguous zero-based order. Zero items is a valid,
            meaningful outcome (every candidate failed the threshold), never
            silently padded to avoid an empty result.
        excluded: Ordered tuple of FilterExclusion for every excluded
            candidate, hidden from repr.
        config: The ContextFilterConfig that produced this filtering,
            hidden from repr.
        reranked: The Story 4 RerankedResults this was filtered from, hidden
            from repr; every item's candidate must be a member of
            ``reranked.candidates``.

    Raises:
        ContextFilterError: For wrong types, order gaps, a duplicate
            chunk_id, a budget violation, or an item not drawn from
            ``reranked``.
    """

    items: tuple[ContextFilterItem, ...]
    excluded: tuple[FilterExclusion, ...] = field(repr=False)
    config: ContextFilterConfig = field(repr=False)
    reranked: RerankedResults = field(repr=False)

    def __post_init__(self) -> None:
        """Re-validate contiguous order, dedup, origin, and the declared cap."""
        if type(self.config) is not ContextFilterConfig:
            raise ContextFilterError("Supply a validated ContextFilterConfig.")
        if type(self.reranked) is not RerankedResults:
            raise ContextFilterError("Supply a validated Story 4 RerankedResults.")
        if (
            type(self.items) is not tuple
            or len(self.items) > self.config.max_candidates
            or any(type(item) is not ContextFilterItem for item in self.items)
        ):
            raise ContextFilterError(
                "Supply at most max_candidates validated ContextFilterItem objects."
            )
        reranked_candidates = set(self.reranked.candidates)
        for index, item in enumerate(self.items):
            if item.order != index:
                raise ContextFilterError("Keep item order contiguous from zero.")
            if item.candidate not in reranked_candidates:
                raise ContextFilterError(
                    "Every retained item must originate from the supplied "
                    "Story 4 RerankedResults."
                )
        ids = [item.chunk_id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ContextFilterError("Deduplicate retained chunk_id values.")
        if (
            type(self.excluded) is not tuple
            or any(type(e) is not FilterExclusion for e in self.excluded)
        ):
            raise ContextFilterError(
                "Supply a tuple of validated FilterExclusion objects."
            )


def filter_context(
    reranked: RerankedResults, config: ContextFilterConfig = _DEFAULT_CONFIG
) -> FilteredContext:
    """Deterministically retain/exclude Story 4 candidates by score and count.

    Candidates are considered in their existing Story 4 rerank order (never
    re-ranked here). A candidate scoring below ``config.min_rerank_score``
    is excluded with reason "below_score_threshold"; once
    ``config.max_candidates`` retained items are reached, every further
    candidate (even one that passed the threshold) is excluded with reason
    "candidate_count_exceeded". Nothing is silently dropped: every candidate
    not retained appears in ``excluded`` with its reason.

    Args:
        reranked: Validated Story 4 RerankedResults to filter.
        config: Validated deterministic threshold/count policy.

    Returns:
        A FilteredContext with retained items, excluded candidates and their
        reasons, and the config used.

    Raises:
        ContextFilterError: For invalid reranked input or configuration.
    """
    if type(reranked) is not RerankedResults:
        raise ContextFilterError("Supply a validated Story 4 RerankedResults.")
    if type(config) is not ContextFilterConfig:
        raise ContextFilterError("Supply a validated ContextFilterConfig.")

    items: list[ContextFilterItem] = []
    excluded: list[FilterExclusion] = []
    for candidate in reranked.candidates:
        if candidate.rerank_score < config.min_rerank_score:
            excluded.append(
                FilterExclusion(candidate.chunk_id, "below_score_threshold")
            )
            continue
        if len(items) >= config.max_candidates:
            excluded.append(
                FilterExclusion(candidate.chunk_id, "candidate_count_exceeded")
            )
            continue
        items.append(ContextFilterItem(len(items), candidate))

    return FilteredContext(tuple(items), tuple(excluded), config, reranked)
