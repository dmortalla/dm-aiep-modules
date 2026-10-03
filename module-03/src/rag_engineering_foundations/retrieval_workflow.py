"""Deterministic workflow: query transformation -> embedding -> VectorIndex search.

This module composes accepted Story 4/5/6 contracts (``Embedder``,
``EmbeddingBatch``, ``VectorIndex``, ``SearchQuery``, ``SearchHit``,
``SearchResults``) with Story 7 query transformation. It relies only on the
structural ``VectorIndex`` protocol (``dimension``, ``size``, ``search``); it
never assumes adapter-specific extras such as FAISS's metric attribute,
Chroma's ``close()``, or Pinecone's injected-client constructor. Retrieved
chunks remain evidence, never authority: this module never executes, imports,
or otherwise acts on retrieved content.
"""

from dataclasses import dataclass, field

from .embeddings import Embedder, EmbeddingBatch
from .errors import EmbeddingError, RetrievalError, RetrievalWorkflowError
from .query_transformation import (
    QueryTransformationResult,
    QueryTransformConfig,
    transform_query,
)
from .retrieval import MAX_TOP_K, SearchHit, SearchQuery, SearchResults, VectorIndex

_DEFAULT_TRANSFORM = QueryTransformConfig()


@dataclass(frozen=True, slots=True)
class RetrievalCandidate:
    """One deduplicated candidate, merged across every transformed query searched.

    Args:
        hit: The best-scoring SearchHit for this chunk across every query
            searched against the same index, hidden from repr; its own content
            is reachable only through ``hit.record.chunk``.
        produced_by: Ordered tuple of distinct transformed-query texts whose
            search surfaced this same chunk_id, in first-seen order, hidden
            from repr; empty when no transformed-query evidence applies (see
            ``from_search_results``).

    Raises:
        RetrievalWorkflowError: For a wrong hit type or malformed provenance.
    """

    hit: SearchHit = field(repr=False)
    produced_by: tuple[str, ...] = field(repr=False)

    def __post_init__(self) -> None:
        """Validate the retained hit and query-text provenance tuple."""
        if type(self.hit) is not SearchHit:
            raise RetrievalWorkflowError("Supply a validated SearchHit.")
        if type(self.produced_by) is not tuple or any(
            type(p) is not str for p in self.produced_by
        ):
            raise RetrievalWorkflowError(
                "Supply a tuple of transformed-query text strings."
            )

    @property
    def chunk_id(self) -> str:
        """Return the retrieved chunk's stable identifier."""
        return self.hit.chunk_id

    @property
    def document_id(self) -> str:
        """Return the retrieved chunk's parent document identifier."""
        return self.hit.document_id

    @property
    def score(self) -> float:
        """Return the retained hit's finite metric value."""
        return self.hit.score


@dataclass(frozen=True, slots=True)
class RetrievalWorkflowResult:
    """Complete deterministic merged retrieval outcome across transformed queries.

    Args:
        transformation: The QueryTransformationResult whose derived queries
            were every one searched against the index, hidden from repr.
        candidates: Deduplicated tuple of 1..N RetrievalCandidate, ranked best
            first by the shared score direction, tied by ascending chunk_id
            (matching Story 5/6's own tie-break convention).
        higher_is_better: Score direction shared by every merged SearchResults.

    Raises:
        RetrievalWorkflowError: For wrong types, duplicate chunk IDs, or
            misordered candidates.
    """

    transformation: QueryTransformationResult = field(repr=False)
    candidates: tuple[RetrievalCandidate, ...]
    higher_is_better: bool = True

    def __post_init__(self) -> None:
        """Re-validate dedup and declared score-direction monotonicity."""
        if type(self.transformation) is not QueryTransformationResult:
            raise RetrievalWorkflowError(
                "Supply a validated QueryTransformationResult."
            )
        if type(self.higher_is_better) is not bool:
            raise RetrievalWorkflowError("Use bool for higher_is_better.")
        if (
            type(self.candidates) is not tuple
            or len(self.candidates) < 1
            or any(type(c) is not RetrievalCandidate for c in self.candidates)
        ):
            raise RetrievalWorkflowError(
                "Supply a nonempty tuple of validated RetrievalCandidate."
            )
        ids = [c.chunk_id for c in self.candidates]
        if len(set(ids)) != len(ids):
            raise RetrievalWorkflowError("Deduplicate candidates by chunk_id.")
        previous: float | None = None
        for candidate in self.candidates:
            if previous is not None:
                worse = (
                    candidate.score > previous
                    if self.higher_is_better
                    else candidate.score < previous
                )
                if worse:
                    raise RetrievalWorkflowError(
                        "Keep candidates sorted by the declared score direction."
                    )
            previous = candidate.score


def from_search_results(results: SearchResults) -> tuple[RetrievalCandidate, ...]:
    """Wrap one plain SearchResults as unmerged RetrievalCandidate objects.

    Useful when the application already searched a single, non-transformed (or
    externally transformed) query and wants bounded context optimization
    without this module's multi-query merge; ``produced_by`` is empty since no
    transformed-query evidence applies.

    Args:
        results: A validated SearchResults from any accepted VectorIndex.

    Returns:
        One RetrievalCandidate per hit, in the same rank order.

    Raises:
        RetrievalWorkflowError: If results is not a validated SearchResults.
    """
    if type(results) is not SearchResults:
        raise RetrievalWorkflowError("Supply a validated SearchResults.")
    return tuple(RetrievalCandidate(hit, ()) for hit in results.hits)


def retrieve(
    query_text: str,
    embedder: Embedder,
    index: VectorIndex,
    *,
    top_k: int = 10,
    transform_config: QueryTransformConfig = _DEFAULT_TRANSFORM,
) -> RetrievalWorkflowResult:
    """Run query transformation, embedding, and VectorIndex search, then merge.

    Workflow: ``original query -> query transformation -> embedding ->
    VectorIndex search -> candidate retrieval``. Every transformed query is
    searched against the same index, so their scores share one metric and
    direction and can be merged safely; this function never merges results
    from different indexes or providers. When the same chunk is retrieved by
    more than one transformed query, the better-scoring hit is kept and every
    contributing query's text is recorded in ``produced_by``.

    Args:
        query_text: Original, application-authored query text.
        embedder: Accepted Story 4 Embedder, selected by the application.
        index: Accepted Story 5/6 VectorIndex, used only through its
            structural ``dimension``/``size``/``search`` surface.
        top_k: Requested maximum ranked results per transformed query,
            1..10000; the merged result may exceed top_k after deduplication
            across multiple transformed queries.
        transform_config: Validated deterministic transformation policy.

    Returns:
        A RetrievalWorkflowResult with the transformation evidence and the
        deduplicated, ranked, provenance-bearing candidates.

    Raises:
        RetrievalWorkflowError: For a dimension mismatch, invalid top_k,
            malformed embedder/index output, or inconsistent score direction
            across the same index's own searches.
        QueryTransformationError: For invalid query text or configuration.
        QuerySignalError: If a configured query expander fails.
    """
    if type(top_k) is not int or not 1 <= top_k <= MAX_TOP_K:
        raise RetrievalWorkflowError("Use an integer top_k from 1 to 10000.")
    if embedder.dimension != index.dimension:
        raise RetrievalWorkflowError(
            "Embedder and index dimensions must match before searching."
        )

    transformation = transform_query(query_text, transform_config)
    try:
        batch = embedder.embed(tuple(q.text for q in transformation.queries))
    except EmbeddingError as exc:
        raise RetrievalWorkflowError(
            "Embedding the transformed queries failed; verify embedder input."
        ) from exc
    if (
        type(batch) is not EmbeddingBatch
        or len(batch.vectors) != len(transformation.queries)
    ):
        raise RetrievalWorkflowError(
            "Embedder returned a vector count that does not match the queries."
        )

    best: dict[str, SearchHit] = {}
    contributors: dict[str, list[str]] = {}
    higher_is_better: bool | None = None
    for transformed_query, vector in zip(
        transformation.queries, batch.vectors, strict=True
    ):
        try:
            search_query = SearchQuery(vector, top_k)
        except RetrievalError as exc:
            raise RetrievalWorkflowError(
                "Could not build a valid search query for this index."
            ) from exc
        results = index.search(search_query)
        if type(results) is not SearchResults:
            raise RetrievalWorkflowError("Index returned a malformed SearchResults.")
        if higher_is_better is None:
            higher_is_better = results.higher_is_better
        elif results.higher_is_better != higher_is_better:
            raise RetrievalWorkflowError(
                "Index returned inconsistent score direction across searches;"
                " incomparable provider metrics cannot be merged."
            )
        for hit in results.hits:
            chunk_id = hit.chunk_id
            bucket = contributors.setdefault(chunk_id, [])
            if transformed_query.text not in bucket:
                bucket.append(transformed_query.text)
            current = best.get(chunk_id)
            if current is None or (
                hit.score > current.score
                if higher_is_better
                else hit.score < current.score
            ):
                best[chunk_id] = hit

    candidates = [
        RetrievalCandidate(best[chunk_id], tuple(contributors[chunk_id]))
        for chunk_id in best
    ]
    candidates.sort(
        key=lambda c: (-c.score if higher_is_better else c.score, c.chunk_id)
    )
    return RetrievalWorkflowResult(
        transformation, tuple(candidates), bool(higher_is_better)
    )
