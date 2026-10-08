"""Query reranking over Story 3 hybrid candidates (M4-RET-04, M4-RET-05).

This module composes Story 3's ``hybrid_retrieval.HybridResults`` with an
injected or adapter-supplied scorer to produce a re-ordered result. The
single orchestration function, ``rerank``, is scorer-agnostic: it calls
whatever ``RerankScorer`` it is given through the exact same path, whether
that scorer is the deterministic ``DeterministicOverlapScorer`` used by
normal tests or the genuine ``SentenceTransformersCrossEncoderScorer``
adapter. Neither scorer is special-cased inside ``rerank``, so no code path
exists that could silently substitute one for the other.

Reranking changes ordering only. A reranker score adjusts which chunk is
considered more relevant; it never grants retrieved content, a candidate, or
a scorer's own output any application, tool, credential, configuration, or
execution authority. Candidate text is passed to a scorer as inert data for
scoring, never executed, imported, or otherwise interpreted. Scorer output is
untrusted until validated: every returned value is checked finite and
well-shaped before it can affect ranking.
"""

import math
from dataclasses import dataclass, field
from typing import Protocol

from .corpus import CorpusChunk
from .errors import (
    CrossEncoderInferenceError,
    CrossEncoderUnavailableError,
    RerankConfigurationError,
    RerankingError,
    RerankScorerError,
)
from .hybrid_retrieval import HybridCandidate, HybridResults

MAX_TOP_K = 10_000


class RerankScorer(Protocol):
    """Provider-neutral query/candidate-text scoring boundary.

    Both the deterministic test scorer and the genuine cross-encoder adapter
    implement exactly this shape, so ``rerank`` never needs to know which one
    it was given.
    """

    def score(self, query: str, candidates: tuple[str, ...]) -> tuple[float, ...]:
        """Return one finite relevance score per candidate, in input order.

        Args:
            query: Application-supplied query text, treated as data.
            candidates: Ordered candidate chunk texts, treated as data.

        Returns:
            A tuple of exactly ``len(candidates)`` finite scores, positional
            to ``candidates``. Higher means more relevant.

        Raises:
            Exception: Implementation-specific failures translated at the
                ``rerank`` boundary.
        """
        ...


@dataclass(frozen=True, slots=True)
class DeterministicOverlapScorer:
    """Deterministic, offline, credential-free test/demo scorer.

    This is explicitly *not* a cross-encoder and does not satisfy
    Module 4's cross-encoder source requirement (M4-RET-05) on its own; it
    exists so ``rerank``'s orchestration path can be exercised in normal,
    network-free tests. It scores query/candidate overlap with a simple
    Jaccard index over Story 2's tokenizer, so results are fully
    reproducible and independent of any trained model.
    """

    def score(self, query: str, candidates: tuple[str, ...]) -> tuple[float, ...]:
        """Return a token-overlap Jaccard score per candidate.

        Args:
            query: Query text; tokenized the same way as each candidate.
            candidates: Ordered candidate chunk texts.

        Returns:
            One score in [0, 1] per candidate, in input order. A candidate
            sharing no tokens with the query, or an empty-token query, scores
            0.0.
        """
        from .bm25 import tokenize

        query_terms = set(tokenize(query))
        scores = []
        for text in candidates:
            candidate_terms = set(tokenize(text))
            union = query_terms | candidate_terms
            scores.append(
                len(query_terms & candidate_terms) / len(union) if union else 0.0
            )
        return tuple(scores)


class SentenceTransformersCrossEncoderScorer:
    """Genuine ``sentence_transformers.CrossEncoder`` adapter.

    ``sentence_transformers`` is imported lazily, inside this class's own
    model-loading method, never at module import time: importing
    ``reranking.py``, or constructing this adapter, does not require the
    optional dependency to already be importable, let alone require a model
    download. The model itself is loaded, and may be downloaded, only on the
    first call to ``score``. Model identity is always application-supplied,
    never derived from query or candidate content. No model weights are
    bundled with this repository.
    """

    __slots__ = ("_model_name", "_model")

    def __init__(
        self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    ) -> None:
        """Configure, without loading, a named Hugging Face cross-encoder model.

        Args:
            model_name: Nonblank application-supplied model identifier.

        Raises:
            RerankConfigurationError: For a blank/non-string model identifier.
        """
        if type(model_name) is not str or not model_name.strip():
            raise RerankConfigurationError(
                "Supply a nonblank cross-encoder model identifier."
            )
        self._model_name = model_name
        self._model = None

    def __repr__(self) -> str:
        """Return a safe repr; no loaded model state is ever rendered."""
        loaded = self._model is not None
        return (
            f"SentenceTransformersCrossEncoderScorer("
            f"model_name={self._model_name!r}, loaded={loaded!r})"
        )

    def _loaded_model(self):
        """Import and load the configured model exactly once, on first use.

        Raises:
            CrossEncoderUnavailableError: If ``sentence_transformers`` is not
                installed, or the configured model cannot be loaded (for
                example due to an unreachable model hub, an unknown model
                identifier, or insufficient local resources).
        """
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise CrossEncoderUnavailableError(
                "Install the optional sentence-transformers dependency to "
                "use a real cross-encoder scorer."
            ) from exc
        try:
            self._model = CrossEncoder(self._model_name)
        except Exception as exc:
            raise CrossEncoderUnavailableError(
                "Failed to load the configured cross-encoder model; check "
                "the model identifier, network access, and local resources."
            ) from exc
        return self._model

    def score(self, query: str, candidates: tuple[str, ...]) -> tuple[float, ...]:
        """Run the genuine cross-encoder model over (query, candidate) pairs.

        Args:
            query: Query text; paired with every candidate for scoring.
            candidates: Ordered candidate chunk texts.

        Returns:
            One finite relevance score per candidate, in input order.

        Raises:
            CrossEncoderUnavailableError: If the model cannot be imported or
                loaded.
            CrossEncoderInferenceError: If the loaded model fails during
                inference or returns a malformed prediction shape.
        """
        model = self._loaded_model()
        pairs = [(query, text) for text in candidates]
        try:
            raw_scores = model.predict(pairs)
        except Exception as exc:
            raise CrossEncoderInferenceError(
                "The configured cross-encoder model failed during inference."
            ) from exc
        try:
            scores = tuple(float(value) for value in raw_scores)
        except (TypeError, ValueError) as exc:
            raise CrossEncoderInferenceError(
                "The cross-encoder model returned a non-numeric prediction."
            ) from exc
        if len(scores) != len(candidates):
            raise CrossEncoderInferenceError(
                "The cross-encoder model returned a mismatched prediction count."
            )
        return scores


@dataclass(frozen=True, slots=True)
class RerankConfig:
    """Application-owned reranking policy.

    Args:
        top_k: Maximum reranked results to return, 1..10000; default 10.

    Raises:
        RerankConfigurationError: For an invalid top_k.
    """

    top_k: int = 10

    def __post_init__(self) -> None:
        """Validate reranking settings before any candidate is scored."""
        if (
            type(self.top_k) is not int
            or type(self.top_k) is bool
            or not 1 <= self.top_k <= MAX_TOP_K
        ):
            raise RerankConfigurationError("Use an integer top_k from 1 to 10000.")


_DEFAULT_CONFIG = RerankConfig()


@dataclass(frozen=True, slots=True)
class RerankedCandidate:
    """One post-rerank result; the fused Story 3 candidate is retained by reference.

    All Story 3 hybrid evidence (fused rank, RRF score, lexical/semantic
    rank and score, chunk/document provenance) is reachable unchanged
    through ``candidate``; this object adds only the two new Story 4 fields.

    Args:
        rank: Zero-based descending-relevance position after reranking.
        rerank_score: Finite scorer output for this candidate.
        candidate: The fused Story 3 HybridCandidate this was reranked from,
            hidden from repr to avoid incidental content exposure.

    Raises:
        RerankingError: For a malformed rank, nonfinite score, or wrong
            candidate type.
    """

    rank: int
    rerank_score: float
    candidate: HybridCandidate = field(repr=False)

    def __post_init__(self) -> None:
        """Validate rank/score shape without rendering retrieved content."""
        if type(self.rank) is not int or self.rank < 0:
            raise RerankingError("Use a zero-based nonnegative integer rank.")
        if type(self.rerank_score) not in (int, float) or not math.isfinite(
            self.rerank_score
        ):
            raise RerankingError("Use a finite reranker score.")
        if type(self.candidate) is not HybridCandidate:
            raise RerankingError("Supply a validated Story 3 HybridCandidate.")

    @property
    def chunk(self) -> CorpusChunk:
        """Return the fused chunk; content is reachable only through this path."""
        return self.candidate.chunk

    @property
    def chunk_id(self) -> str:
        """Return the stable chunk identifier, unchanged from Story 3."""
        return self.candidate.chunk_id

    @property
    def document_id(self) -> str:
        """Return the parent document identifier, unchanged from Story 3."""
        return self.candidate.document_id

    @property
    def hybrid_rank(self) -> int:
        """Return the chunk's pre-rerank (Story 3 fused) rank."""
        return self.candidate.rank

    @property
    def rrf_score(self) -> float:
        """Return the chunk's Story 3 Reciprocal Rank Fusion score, unchanged."""
        return self.candidate.rrf_score


@dataclass(frozen=True, slots=True)
class RerankedResults:
    """Validated complete reranked outcome for one query over one hybrid result.

    Args:
        candidates: Tuple of 1..config.top_k RerankedCandidate objects,
            contiguous rank order, nonincreasing rerank_score, unique
            chunk_id.
        hybrid: The Story 3 HybridResults this was reranked from, hidden
            from repr; every candidate's ``.candidate`` must be a member of
            ``hybrid.candidates``.
        query: The nonblank query text used for scoring.
        config: The RerankConfig that produced this result, hidden from repr.

    Raises:
        RerankingError: For wrong types, rank gaps, score-order violations,
            a duplicate chunk_id, or a candidate not drawn from ``hybrid``.
    """

    candidates: tuple[RerankedCandidate, ...]
    hybrid: HybridResults = field(repr=False)
    query: str
    config: RerankConfig = field(repr=False)

    def __post_init__(self) -> None:
        """Re-validate rank/score order, chunk_id uniqueness, and hybrid origin."""
        if type(self.hybrid) is not HybridResults:
            raise RerankingError("Supply a validated Story 3 HybridResults.")
        if type(self.query) is not str or not self.query.strip():
            raise RerankingError("Supply a nonblank query string.")
        if type(self.config) is not RerankConfig:
            raise RerankingError("Supply a validated RerankConfig.")
        if (
            type(self.candidates) is not tuple
            or not 1 <= len(self.candidates) <= self.config.top_k
            or any(type(c) is not RerankedCandidate for c in self.candidates)
        ):
            raise RerankingError(
                "Supply 1..top_k validated RerankedCandidate rows."
            )
        hybrid_candidates = set(self.hybrid.candidates)
        previous: float | None = None
        for index, candidate in enumerate(self.candidates):
            if candidate.rank != index:
                raise RerankingError("Keep candidate ranks contiguous from zero.")
            if previous is not None and candidate.rerank_score > previous:
                raise RerankingError(
                    "Keep candidates sorted by nonincreasing rerank_score."
                )
            previous = candidate.rerank_score
            if candidate.candidate not in hybrid_candidates:
                raise RerankingError(
                    "Every reranked candidate must originate from the supplied "
                    "Story 3 HybridResults."
                )
        ids = [candidate.chunk_id for candidate in self.candidates]
        if len(set(ids)) != len(ids):
            raise RerankingError("Deduplicate reranked chunk_id values.")


def rerank(
    query: str,
    hybrid: HybridResults,
    scorer: RerankScorer,
    config: RerankConfig = _DEFAULT_CONFIG,
) -> RerankedResults:
    """Rerank Story 3 hybrid candidates using an injected or adapter scorer.

    Every Story 3 candidate's chunk content is passed to ``scorer.score`` as
    plain text, in the candidates' existing fused order; the scorer's
    returned scores alone determine the new order. Ties are broken by
    ascending ``chunk_id``, matching Story 3's and the semantic leg's documented
    deterministic tie-break convention. No candidate is discarded due to a
    tie; only ``config.top_k`` ever truncates the result.

    Args:
        query: Nonblank query text, treated as data; paired with every
            candidate's text for scoring.
        hybrid: Validated Story 3 HybridResults to rerank.
        scorer: Application-selected RerankScorer, deterministic or a
            genuine cross-encoder adapter; called through the same path
            either way.
        config: Validated reranking policy.

    Returns:
        RerankedResults ranked best-first by reranker score, 1..config.top_k
        candidates.

    Raises:
        RerankConfigurationError: For a blank query, wrong hybrid type, or
            wrong config type.
        RerankScorerError: If the scorer raises an unexpected exception, or
            returns a wrong-cardinality, nonnumeric, or nonfinite score.
    """
    if type(query) is not str or not query.strip():
        raise RerankConfigurationError("Supply a nonblank query string.")
    if type(hybrid) is not HybridResults:
        raise RerankConfigurationError("Supply a validated Story 3 HybridResults.")
    if type(config) is not RerankConfig:
        raise RerankConfigurationError("Supply a validated RerankConfig.")

    texts = tuple(candidate.chunk.content for candidate in hybrid.candidates)
    try:
        raw_scores = scorer.score(query, texts)
    except RerankingError:
        raise
    except Exception as exc:
        raise RerankScorerError(
            "The injected scorer failed; repair the scorer or its configuration."
        ) from exc

    if type(raw_scores) is not tuple or len(raw_scores) != len(texts):
        raise RerankScorerError(
            "The scorer must return exactly one score per candidate, in order."
        )
    scores: list[float] = []
    for value in raw_scores:
        if type(value) not in (int, float) or type(value) is bool:
            raise RerankScorerError("Reject a nonnumeric scorer output value.")
        if not math.isfinite(value):
            raise RerankScorerError("Reject a nonfinite scorer output value.")
        scores.append(float(value))

    ordered = sorted(
        zip(hybrid.candidates, scores, strict=True),
        key=lambda item: (-item[1], item[0].chunk_id),
    )
    truncated = ordered[: config.top_k]
    reranked = tuple(
        RerankedCandidate(rank=rank, rerank_score=score, candidate=candidate)
        for rank, (candidate, score) in enumerate(truncated)
    )
    return RerankedResults(reranked, hybrid, query, config)
