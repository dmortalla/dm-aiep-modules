"""Offline, FAISS-independent tests for provider-neutral retrieval contracts."""

from dataclasses import FrozenInstanceError

import pytest
from rag_engineering_foundations.chunking import FixedConfig, chunk_fixed
from rag_engineering_foundations.embeddings import LocalHashEmbedder
from rag_engineering_foundations.errors import RetrievalError
from rag_engineering_foundations.ingestion import ingest_text
from rag_engineering_foundations.retrieval import (
    MAX_TOP_K,
    IndexedChunk,
    SearchHit,
    SearchQuery,
    SearchResults,
    to_indexed_chunks,
)
from rag_engineering_foundations.vectors import Vector


def _chunk(text: str = "hello world content", source_key: str = "s"):
    document = ingest_text(text, source_key=source_key)
    return chunk_fixed(document, FixedConfig(size=len(text))).chunks[0], document


def test_indexed_chunk_identity_repr_and_immutability() -> None:
    """Expose stable identifiers without rendering chunk or vector content."""
    chunk, document = _chunk()
    vector = Vector((1.0, 0.0, 0.0))
    record = IndexedChunk(chunk, vector)
    assert record.chunk_id == chunk.chunk_id
    assert record.document_id == document.provenance.document_id
    assert "hello" not in repr(record)
    assert "1.0" not in repr(record)
    with pytest.raises(FrozenInstanceError):
        record.vector = Vector((0.0, 0.0, 0.0))


@pytest.mark.parametrize(
    ("chunk_value", "vector_value"),
    [
        ("raw", Vector((1.0,))),
        (None, Vector((1.0,))),
    ],
)
def test_indexed_chunk_rejects_wrong_chunk_type(chunk_value, vector_value) -> None:
    """Reject anything other than an accepted Story 3 DocumentChunk."""
    with pytest.raises(RetrievalError):
        IndexedChunk(chunk_value, vector_value)


def test_indexed_chunk_rejects_wrong_vector_type() -> None:
    """Reject raw coordinate containers; only a validated Vector is accepted."""
    chunk, _ = _chunk()
    with pytest.raises(RetrievalError):
        IndexedChunk(chunk, (1.0, 0.0))
    with pytest.raises(RetrievalError):
        IndexedChunk(chunk, [1.0, 0.0])


@pytest.mark.parametrize("top_k", [0, -1, True, 1.0, "5", None, MAX_TOP_K + 1])
def test_search_query_rejects_invalid_top_k(top_k) -> None:
    """Reject non-integer, boolean, and out-of-range top_k values."""
    with pytest.raises(RetrievalError):
        SearchQuery(Vector((1.0, 0.0)), top_k)


def test_search_query_rejects_non_vector() -> None:
    """A query vector must already be an accepted, validated Vector."""
    with pytest.raises(RetrievalError):
        SearchQuery((1.0, 0.0), 5)


def test_search_query_default_top_k() -> None:
    """Default top_k is a small, explicit, sane value."""
    query = SearchQuery(Vector((1.0,)))
    assert query.top_k == 10


@pytest.mark.parametrize(
    ("rank", "score"),
    [(-1, 0.5), (True, 0.5), (1.0, 0.5), ("0", 0.5)],
)
def test_search_hit_rejects_invalid_rank(rank, score) -> None:
    """Reject negative, boolean, float, and non-integer ranks."""
    chunk, _ = _chunk()
    record = IndexedChunk(chunk, Vector((1.0,)))
    with pytest.raises(RetrievalError):
        SearchHit(rank=rank, score=score, record=record)


@pytest.mark.parametrize(
    "score", [float("nan"), float("inf"), -float("inf"), "0.5", True, None]
)
def test_search_hit_rejects_invalid_score(score) -> None:
    """Reject nonfinite, bool, string, and None relevance scores."""
    chunk, _ = _chunk()
    record = IndexedChunk(chunk, Vector((1.0,)))
    with pytest.raises(RetrievalError):
        SearchHit(rank=0, score=score, record=record)


def test_search_hit_rejects_wrong_record_type() -> None:
    """A hit must retain an actual validated IndexedChunk, not raw data."""
    with pytest.raises(RetrievalError):
        SearchHit(rank=0, score=0.5, record="not-a-record")


def test_search_hit_exposes_identity_and_hides_content() -> None:
    """Delegate identifiers to the retained record; never render its content."""
    chunk, document = _chunk()
    record = IndexedChunk(chunk, Vector((1.0,)))
    hit = SearchHit(rank=0, score=0.9, record=record)
    assert hit.chunk_id == chunk.chunk_id
    assert hit.document_id == document.provenance.document_id
    assert "hello" not in repr(hit)
    with pytest.raises(FrozenInstanceError):
        hit.score = 0.1


def _hit(rank: int, score: float, record: IndexedChunk) -> SearchHit:
    return SearchHit(rank=rank, score=score, record=record)


def test_search_results_accepts_well_formed_hits() -> None:
    """A correctly ordered, contiguous hit tuple constructs without error."""
    chunk, _ = _chunk()
    record = IndexedChunk(chunk, Vector((1.0,)))
    query = SearchQuery(Vector((1.0,)), top_k=2)
    hits = (_hit(0, 0.9, record), _hit(1, 0.5, record))
    results = SearchResults(hits=hits, query=query, higher_is_better=True)
    assert results.hits == hits
    assert results.higher_is_better is True


def test_search_results_rejects_rank_gap() -> None:
    """Ranks must be exactly contiguous from zero; a gap is rejected."""
    chunk, _ = _chunk()
    record = IndexedChunk(chunk, Vector((1.0,)))
    query = SearchQuery(Vector((1.0,)), top_k=2)
    with pytest.raises(RetrievalError):
        SearchResults(
            hits=(_hit(0, 0.9, record), _hit(2, 0.1, record)),
            query=query,
            higher_is_better=True,
        )


def test_search_results_rejects_hits_exceeding_top_k() -> None:
    """More hits than the query's own top_k is an internal inconsistency."""
    chunk, _ = _chunk()
    record = IndexedChunk(chunk, Vector((1.0,)))
    query = SearchQuery(Vector((1.0,)), top_k=1)
    with pytest.raises(RetrievalError):
        SearchResults(
            hits=(_hit(0, 0.9, record), _hit(1, 0.5, record)),
            query=query,
            higher_is_better=True,
        )


@pytest.mark.parametrize("higher_is_better", [True, False])
def test_search_results_rejects_wrong_score_direction(higher_is_better) -> None:
    """Hits sorted the wrong way for the declared metric direction are rejected."""
    chunk, _ = _chunk()
    record = IndexedChunk(chunk, Vector((1.0,)))
    query = SearchQuery(Vector((1.0,)), top_k=2)
    # 0.1 then 0.9 is wrong for higher_is_better=True (should descend) and also
    # wrong for higher_is_better=False (should ascend, so 0.9 then 0.1 is wrong
    # instead); construct the specific violation for each declared direction.
    hits = (
        (_hit(0, 0.1, record), _hit(1, 0.9, record))
        if higher_is_better
        else (_hit(0, 0.9, record), _hit(1, 0.1, record))
    )
    with pytest.raises(RetrievalError):
        SearchResults(hits=hits, query=query, higher_is_better=higher_is_better)


def test_search_results_allows_equal_consecutive_scores() -> None:
    """Ties (equal consecutive scores) do not themselves violate monotonicity."""
    chunk, _ = _chunk()
    record = IndexedChunk(chunk, Vector((1.0,)))
    query = SearchQuery(Vector((1.0,)), top_k=2)
    results = SearchResults(
        hits=(_hit(0, 0.5, record), _hit(1, 0.5, record)),
        query=query,
        higher_is_better=True,
    )
    assert results.hits[0].score == results.hits[1].score


def test_search_results_rejects_wrong_types() -> None:
    """Reject non-tuple hits, a wrong query type, and a non-bool direction flag."""
    chunk, _ = _chunk()
    record = IndexedChunk(chunk, Vector((1.0,)))
    query = SearchQuery(Vector((1.0,)), top_k=1)
    hit = _hit(0, 0.5, record)
    with pytest.raises(RetrievalError):
        SearchResults(hits=[hit], query=query, higher_is_better=True)
    with pytest.raises(RetrievalError):
        SearchResults(hits=(), query=query, higher_is_better=True)
    with pytest.raises(RetrievalError):
        SearchResults(hits=(hit,), query="not-a-query", higher_is_better=True)
    with pytest.raises(RetrievalError):
        SearchResults(hits=(hit,), query=query, higher_is_better=1)


def test_to_indexed_chunks_preserves_order_and_pairs_correctly() -> None:
    """Pair ordered chunks with their matching batch vectors, in input order."""
    embedder = LocalHashEmbedder(dimension=16)
    texts = ("apple pear", "rocket orbit")
    chunks = tuple(_chunk(text, source_key=f"s-{i}")[0] for i, text in enumerate(texts))
    batch = embedder.embed(texts)
    records = to_indexed_chunks(chunks, batch)
    assert len(records) == 2
    assert [r.vector for r in records] == list(batch.vectors)
    assert [r.chunk for r in records] == list(chunks)


def test_to_indexed_chunks_rejects_mismatched_counts() -> None:
    """A chunk/vector count mismatch is a caller bug, not silently truncated."""
    embedder = LocalHashEmbedder(dimension=8)
    chunks = (_chunk("a", source_key="s0")[0],)
    batch = embedder.embed(("a", "b"))
    with pytest.raises(RetrievalError):
        to_indexed_chunks(chunks, batch)


def test_to_indexed_chunks_rejects_wrong_types() -> None:
    """Reject a non-tuple chunk container or a non-EmbeddingBatch object."""
    embedder = LocalHashEmbedder(dimension=8)
    chunk, _ = _chunk()
    batch = embedder.embed(("a",))
    with pytest.raises(RetrievalError):
        to_indexed_chunks([chunk], batch)
    with pytest.raises(RetrievalError):
        to_indexed_chunks((chunk,), "not-a-batch")
