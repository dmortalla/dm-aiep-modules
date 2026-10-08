"""Deterministic Reciprocal Rank Fusion over a lexical and a semantic leg.

This module composes Story 2's BM25 lexical leg (``bm25.LexicalResults``)
with Module 4's own semantic retrieval leg
(``semantic_retrieval.SemanticResults``, produced by ChromaDB or the Pinecone
boundary) into one fused, ranked result. It reads both legs' public,
already-validated outputs and merges them by chunk identity. Module 4 is
standalone: no earlier academic module is imported (Rule 44; see
``module-04/docs/ARCHITECTURE.md``).

Reciprocal Rank Fusion (RRF) was chosen, as the frozen architecture requires,
because BM25 scores and vector-index scores are not comparable numbers: BM25
is an unbounded, corpus-dependent lexical statistic, while a semantic score
is a bounded cosine similarity (``SemanticResults.higher_is_better``). Adding
or otherwise combining those raw numbers would silently conflate two different
measurement systems. RRF sidesteps this entirely by fusing *rank positions*,
which are directly comparable across any ranking method, instead of raw scores:

    RRF(chunk) = sum over legs L that rank chunk of 1 / (rrf_k + rank_L(chunk))

``rank_L`` is the chunk's 1-based position within leg L's own ranking (this
module adds 1 to each leg's zero-based ``rank`` field). ``rrf_k`` is a small
positive constant that discounts the influence of very low ranks; this
module's default, ``60.0``, is the constant used in the original RRF
proposal (Cormack, Clarke & Buettcher, 2009) and widely reused since (for
example as Elasticsearch's default ``rank_constant``). It remains an
explicit, overridable ``HybridConfig`` field, not a hidden tuning knob.

Both legs' original rank and raw score are retained on every fused
``HybridCandidate`` as inspectable evidence; this module's own fused score is
never substituted for, or confused with, either leg's native score.

Retrieved chunk content, from either leg, remains untrusted, inert data:
nothing here executes, imports, or otherwise acts on it, and no retrieved
text can alter fusion configuration or ranking logic. ``HybridConfig`` is
always application-supplied, never derived from retrieved content.
"""

import math
from dataclasses import dataclass, field

from .bm25 import LexicalHit, LexicalQuery, LexicalResults
from .corpus import CorpusChunk
from .errors import HybridConfigurationError, HybridRetrievalError
from .semantic_retrieval import SemanticHit, SemanticQuery, SemanticResults

MAX_TOP_K = 10_000


@dataclass(frozen=True, slots=True)
class HybridConfig:
    """Application-owned deterministic Reciprocal Rank Fusion policy.

    Args:
        rrf_k: Rank-discounting constant, 0.0 <= rrf_k <= 1000.0; default
            60.0, the constant from the original RRF proposal.
        top_k: Maximum fused results to return, 1..10000; default 10.

    Raises:
        HybridConfigurationError: For invalid settings.
    """

    rrf_k: float = 60.0
    top_k: int = 10

    def __post_init__(self) -> None:
        """Validate fusion settings before any leg result is considered."""
        if (
            type(self.rrf_k) not in (int, float)
            or type(self.rrf_k) is bool
            or not 0.0 <= self.rrf_k <= 1000.0
        ):
            raise HybridConfigurationError("Use a numeric rrf_k from 0 to 1000.")
        if (
            type(self.top_k) is not int
            or type(self.top_k) is bool
            or not 1 <= self.top_k <= MAX_TOP_K
        ):
            raise HybridConfigurationError("Use an integer top_k from 1 to 10000.")


_DEFAULT_CONFIG = HybridConfig()


@dataclass(frozen=True, slots=True)
class HybridCandidate:
    """One fused chunk with both contributing legs' evidence retained.

    Exactly one of a candidate's two legs may be absent (``None`` rank/score
    pair) when a chunk was returned by only one leg; both are present when
    both legs returned the same chunk. At least one leg is always present.

    Args:
        rank: Zero-based descending-fused-relevance position.
        rrf_score: Finite, positive Reciprocal Rank Fusion score. This is a
            rank-fusion score, not a BM25 score or a semantic similarity/
            distance; it must never be compared to either leg's own score.
        chunk: Fused Module 4 CorpusChunk; content is reachable only through
            ``candidate.chunk.content``, never through this object's repr.
        lexical_rank: The chunk's zero-based rank within the lexical leg, or
            None if the lexical leg did not return this chunk.
        lexical_score: The lexical leg's own raw BM25 score, or None.
        semantic_rank: The chunk's zero-based rank within the semantic leg,
            or None if the semantic leg did not return this chunk.
        semantic_score: The semantic leg's own raw score (similarity or
            distance, depending on that leg's configured metric), or None.

    Raises:
        HybridRetrievalError: For malformed rank/score pairing, a wrong
            chunk type, or a candidate with neither leg present.
    """

    rank: int
    rrf_score: float
    chunk: CorpusChunk = field(repr=False)
    lexical_rank: int | None
    lexical_score: float | None
    semantic_rank: int | None
    semantic_score: float | None

    def __post_init__(self) -> None:
        """Validate fused-candidate shape without rendering retrieved content."""
        if type(self.rank) is not int or self.rank < 0:
            raise HybridRetrievalError("Use a zero-based nonnegative integer rank.")
        if (
            type(self.rrf_score) not in (int, float)
            or not math.isfinite(self.rrf_score)
            or self.rrf_score <= 0
        ):
            raise HybridRetrievalError("Use a finite positive RRF score.")
        if type(self.chunk) is not CorpusChunk:
            raise HybridRetrievalError("Supply a validated Module 4 CorpusChunk.")
        lexical_present = (
            self.lexical_rank is not None or self.lexical_score is not None
        )
        if lexical_present and (
            type(self.lexical_rank) is not int
            or self.lexical_rank < 0
            or type(self.lexical_score) not in (int, float)
        ):
            raise HybridRetrievalError("Supply a paired lexical rank and score.")
        semantic_present = (
            self.semantic_rank is not None or self.semantic_score is not None
        )
        if semantic_present and (
            type(self.semantic_rank) is not int
            or self.semantic_rank < 0
            or type(self.semantic_score) not in (int, float)
        ):
            raise HybridRetrievalError("Supply a paired semantic rank and score.")
        if not lexical_present and not semantic_present:
            raise HybridRetrievalError(
                "A fused candidate must be contributed by at least one leg."
            )

    @property
    def chunk_id(self) -> str:
        """Return the fused chunk's stable identifier."""
        return self.chunk.chunk_id

    @property
    def document_id(self) -> str:
        """Return the fused chunk's parent document identifier."""
        return self.chunk.provenance.document_id

    @property
    def in_lexical_leg(self) -> bool:
        """Return whether the lexical leg returned this chunk."""
        return self.lexical_rank is not None

    @property
    def in_semantic_leg(self) -> bool:
        """Return whether the semantic leg returned this chunk."""
        return self.semantic_rank is not None


@dataclass(frozen=True, slots=True)
class HybridResults:
    """Validated complete fused outcome for one lexical and one semantic query.

    Args:
        candidates: Tuple of 1..config.top_k HybridCandidate objects,
            contiguous rank order, nonincreasing rrf_score, unique chunk_id.
        config: The HybridConfig that produced this fusion, hidden from repr.
        lexical_query: Retained Story 2 LexicalQuery evidence, hidden from repr.
        semantic_query: Retained Module 4 SemanticQuery evidence,
            hidden from repr.
        semantic_higher_is_better: The semantic leg's own score direction,
            retained so ``semantic_score`` on each candidate can be
            interpreted without assuming a direction.

    Raises:
        HybridRetrievalError: For wrong types, rank gaps, score-order
            violations, or a duplicate chunk_id.
    """

    candidates: tuple[HybridCandidate, ...]
    config: HybridConfig = field(repr=False)
    lexical_query: LexicalQuery = field(repr=False)
    semantic_query: SemanticQuery = field(repr=False)
    semantic_higher_is_better: bool

    def __post_init__(self) -> None:
        """Re-validate rank contiguity, score order, and chunk_id uniqueness."""
        if type(self.config) is not HybridConfig:
            raise HybridRetrievalError("Supply a validated HybridConfig.")
        if type(self.lexical_query) is not LexicalQuery:
            raise HybridRetrievalError("Supply a validated Story 2 LexicalQuery.")
        if type(self.semantic_query) is not SemanticQuery:
            raise HybridRetrievalError("Supply a validated Module 4 SemanticQuery.")
        if type(self.semantic_higher_is_better) is not bool:
            raise HybridRetrievalError("Use bool for semantic_higher_is_better.")
        if (
            type(self.candidates) is not tuple
            or not 1 <= len(self.candidates) <= self.config.top_k
            or any(type(c) is not HybridCandidate for c in self.candidates)
        ):
            raise HybridRetrievalError(
                "Supply 1..top_k validated HybridCandidate rows."
            )
        previous: float | None = None
        for index, candidate in enumerate(self.candidates):
            if candidate.rank != index:
                raise HybridRetrievalError("Keep candidate ranks contiguous from zero.")
            if previous is not None and candidate.rrf_score > previous:
                raise HybridRetrievalError(
                    "Keep candidates sorted by nonincreasing score."
                )
            previous = candidate.rrf_score
        ids = [candidate.chunk_id for candidate in self.candidates]
        if len(set(ids)) != len(ids):
            raise HybridRetrievalError("Deduplicate fused chunk_id values.")


def fuse_results(
    lexical: LexicalResults,
    semantic: SemanticResults,
    config: HybridConfig = _DEFAULT_CONFIG,
) -> HybridResults:
    """Fuse one lexical and one semantic ranking with Reciprocal Rank Fusion.

    Both inputs are expected over the same underlying chunk corpus; a chunk
    returned by both legs is represented exactly once in the result, with
    both legs' rank/score retained as evidence. A chunk returned by only one
    leg is still represented, with the other leg's rank/score left ``None``.
    Fusion never adds raw lexical and semantic scores together: only each
    leg's rank position feeds the RRF formula (see this module's docstring).

    Args:
        lexical: Validated Story 2 BM25 LexicalResults.
        semantic: Validated Module 4 SemanticResults.
        config: Validated Reciprocal Rank Fusion policy.

    Returns:
        HybridResults ranked best-first by fused RRF score, 1..config.top_k
        candidates, deterministic for a fixed input/config pair.

    Raises:
        HybridConfigurationError: For a wrong-typed lexical/semantic/config
            argument.
        HybridRetrievalError: For a chunk_id shared by both legs whose
            underlying chunk content disagrees between them.
    """
    if type(lexical) is not LexicalResults:
        raise HybridConfigurationError("Supply validated Story 2 LexicalResults.")
    if type(semantic) is not SemanticResults:
        raise HybridConfigurationError("Supply validated Module 4 SemanticResults.")
    if type(config) is not HybridConfig:
        raise HybridConfigurationError("Supply a validated HybridConfig.")

    lexical_by_id: dict[str, LexicalHit] = {hit.chunk_id: hit for hit in lexical.hits}
    semantic_by_id: dict[str, SemanticHit] = {
        hit.chunk_id: hit for hit in semantic.hits
    }

    scored: list[tuple[float, str, CorpusChunk, LexicalHit | None, SemanticHit | None]]
    scored = []
    for chunk_id in lexical_by_id.keys() | semantic_by_id.keys():
        lexical_hit = lexical_by_id.get(chunk_id)
        semantic_hit = semantic_by_id.get(chunk_id)
        semantic_chunk = semantic_hit.chunk if semantic_hit else None
        if lexical_hit is not None and semantic_chunk is not None:
            if lexical_hit.chunk != semantic_chunk:
                raise HybridRetrievalError(
                    "Lexical and semantic legs disagree on the chunk for a "
                    "shared chunk_id; fuse results built from the same corpus."
                )
        chunk = lexical_hit.chunk if lexical_hit is not None else semantic_chunk
        rrf_score = 0.0
        if lexical_hit is not None:
            rrf_score += 1.0 / (config.rrf_k + lexical_hit.rank + 1)
        if semantic_hit is not None:
            rrf_score += 1.0 / (config.rrf_k + semantic_hit.rank + 1)
        scored.append((rrf_score, chunk_id, chunk, lexical_hit, semantic_hit))

    # Ties broken by ascending chunk_id, matching the semantic leg's documented
    # deterministic tie-break convention for equal scores.
    scored.sort(key=lambda item: (-item[0], item[1]))
    top = scored[: config.top_k]

    candidates = tuple(
        HybridCandidate(
            rank=rank,
            rrf_score=rrf_score,
            chunk=chunk,
            lexical_rank=(lexical_hit.rank if lexical_hit is not None else None),
            lexical_score=(lexical_hit.score if lexical_hit is not None else None),
            semantic_rank=(semantic_hit.rank if semantic_hit is not None else None),
            semantic_score=(semantic_hit.score if semantic_hit is not None else None),
        )
        for rank, (rrf_score, _chunk_id, chunk, lexical_hit, semantic_hit) in enumerate(
            top
        )
    )
    return HybridResults(
        candidates, config, lexical.query, semantic.query, semantic.higher_is_better
    )
