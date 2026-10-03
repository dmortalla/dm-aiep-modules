"""Genuine faiss-cpu integration tests: real index construction and search.

Every FaissVectorIndex and FaissIndexConfig here is backed by the actual
installed ``faiss`` package (IndexFlatIP / IndexFlatL2); nothing is simulated
with a Python list scan. No network access or credentials are required.
"""

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from rag_engineering_foundations.chunking import FixedConfig, chunk_fixed
from rag_engineering_foundations.embeddings import LocalHashEmbedder
from rag_engineering_foundations.errors import FaissOperationError, RetrievalError
from rag_engineering_foundations.faiss_index import FaissIndexConfig, FaissVectorIndex
from rag_engineering_foundations.ingestion import ingest_text
from rag_engineering_foundations.retrieval import (
    IndexedChunk,
    SearchQuery,
    to_indexed_chunks,
)
from rag_engineering_foundations.vectors import Vector

FRUIT_TEXTS = (
    "apple pear orchard fruit harvest",
    "banana citrus tropical fruit grove",
)
SPACE_TEXT = "rocket satellite orbit launch space"


def _records(texts: tuple[str, ...], dimension: int = 64):
    embedder = LocalHashEmbedder(dimension)
    documents = [
        ingest_text(text, source_key=f"doc-{i}") for i, text in enumerate(texts)
    ]
    chunks = tuple(
        chunk_fixed(document, FixedConfig(size=len(text))).chunks[0]
        for document, text in zip(documents, texts, strict=True)
    )
    batch = embedder.embed(texts)
    return to_indexed_chunks(chunks, batch), embedder


def _corpus_records(dimension: int = 64):
    texts = FRUIT_TEXTS + (SPACE_TEXT,)
    return _records(texts, dimension)


def test_faiss_index_construction_and_dimension() -> None:
    """Build a genuine faiss.IndexFlatIP and confirm reported shape/metric."""
    records, embedder = _corpus_records()
    index = FaissVectorIndex(records, FaissIndexConfig(embedder.dimension))
    assert index.size == 3
    assert index.dimension == embedder.dimension == 64
    assert index.metric == "cosine"
    assert "FaissVectorIndex" in repr(index)
    assert all(text not in repr(index) for text in FRUIT_TEXTS + (SPACE_TEXT,))


def test_faiss_index_rejects_empty_corpus() -> None:
    """An index requires at least one record; FAISS never sees an empty add."""
    with pytest.raises(RetrievalError):
        FaissVectorIndex((), FaissIndexConfig(32))


def test_faiss_index_rejects_dimension_mismatch() -> None:
    """A record whose vector dimension disagrees with the config is rejected."""
    records, _ = _corpus_records(dimension=32)
    mismatched = records[:-1] + (
        IndexedChunk(records[-1].chunk, Vector((1.0,) * 8)),
    )
    with pytest.raises(RetrievalError):
        FaissVectorIndex(mismatched, FaissIndexConfig(32))


def test_faiss_index_rejects_duplicate_chunk_ids() -> None:
    """Duplicate chunk identifiers are rejected explicitly, never silently merged."""
    records, embedder = _corpus_records()
    duplicated = (records[0], records[0], records[1])
    with pytest.raises(RetrievalError):
        FaissVectorIndex(duplicated, FaissIndexConfig(embedder.dimension))


def test_faiss_index_rejects_wrong_record_or_config_types() -> None:
    """Reject a non-tuple collection, a raw dict config, and non-record entries."""
    records, embedder = _corpus_records()
    with pytest.raises(RetrievalError):
        FaissVectorIndex(list(records), FaissIndexConfig(embedder.dimension))
    with pytest.raises(RetrievalError):
        FaissVectorIndex(records, {"dimension": embedder.dimension})
    with pytest.raises(RetrievalError):
        FaissVectorIndex(
            records + ("not-a-record",), FaissIndexConfig(embedder.dimension)
        )


def test_faiss_index_config_rejects_bad_metric_and_dimension() -> None:
    """Config validates metric name and dimension before any FAISS call."""
    with pytest.raises(RetrievalError):
        FaissIndexConfig(32, "manhattan")
    with pytest.raises(RetrievalError):
        FaissIndexConfig(0)
    with pytest.raises(RetrievalError):
        FaissIndexConfig(True)
    with pytest.raises(RetrievalError):
        FaissIndexConfig(16_385)


def test_faiss_index_rejects_zero_vector_under_cosine_only() -> None:
    """Cosine indexing cannot normalize a zero vector; Euclidean does not care."""
    chunk = chunk_fixed(
        ingest_text("zero vector document", source_key="zero"), FixedConfig(size=20)
    ).chunks[0]
    zero_record = IndexedChunk(chunk, Vector((0.0,) * 32))
    with pytest.raises(RetrievalError):
        FaissVectorIndex((zero_record,), FaissIndexConfig(32, "cosine"))
    euclidean_index = FaissVectorIndex(
        (zero_record,), FaissIndexConfig(32, "euclidean")
    )
    assert euclidean_index.size == 1


def test_known_ranking_relates_lexically_similar_content() -> None:
    """A fruit-themed query ranks fruit chunks above the unrelated space chunk."""
    records, embedder = _corpus_records()
    index = FaissVectorIndex(records, FaissIndexConfig(embedder.dimension))
    query_vector = embedder.embed(("apple fruit orchard harvest",)).vectors[0]
    results = index.search(SearchQuery(query_vector, top_k=3))
    assert len(results.hits) == 3
    assert [hit.rank for hit in results.hits] == [0, 1, 2]
    fruit_ids = {records[0].chunk_id, records[1].chunk_id}
    assert results.hits[0].chunk_id in fruit_ids
    assert results.hits[-1].chunk_id == records[2].chunk_id
    scores = [hit.score for hit in results.hits]
    assert scores == sorted(scores, reverse=True)
    assert results.higher_is_better is True


def test_euclidean_metric_orders_ascending_by_genuine_distance() -> None:
    """Euclidean mode reports true (non-squared) distance, ascending, lower closer."""
    records, embedder = _corpus_records()
    index = FaissVectorIndex(records, FaissIndexConfig(embedder.dimension, "euclidean"))
    query_vector = embedder.embed(("apple fruit orchard harvest",)).vectors[0]
    results = index.search(SearchQuery(query_vector, top_k=3))
    assert results.higher_is_better is False
    scores = [hit.score for hit in results.hits]
    assert scores == sorted(scores)
    manual = float(
        np.linalg.norm(
            np.array(query_vector.values, dtype=np.float32)
            - np.array(results.hits[0].record.vector.values, dtype=np.float32)
        )
    )
    assert abs(results.hits[0].score - manual) < 1e-4


def test_top_k_greater_than_corpus_size_is_not_an_error() -> None:
    """Requesting more results than exist returns exactly the corpus size."""
    records, embedder = _corpus_records()
    index = FaissVectorIndex(records, FaissIndexConfig(embedder.dimension))
    query_vector = embedder.embed(("apple fruit orchard harvest",)).vectors[0]
    results = index.search(SearchQuery(query_vector, top_k=1_000))
    assert len(results.hits) == index.size == 3


def test_search_rejects_query_dimension_mismatch() -> None:
    """A query vector of the wrong dimension is rejected before reaching FAISS."""
    records, embedder = _corpus_records()
    index = FaissVectorIndex(records, FaissIndexConfig(embedder.dimension))
    with pytest.raises(RetrievalError):
        index.search(SearchQuery(Vector((1.0,) * 5), top_k=1))


def test_search_rejects_wrong_query_type() -> None:
    """Only a validated SearchQuery may be searched; raw vectors are rejected."""
    records, embedder = _corpus_records()
    index = FaissVectorIndex(records, FaissIndexConfig(embedder.dimension))
    with pytest.raises(RetrievalError):
        index.search(Vector((1.0,) * 32))


def test_search_is_stable_and_repeatable() -> None:
    """Repeated identical queries against the same index produce identical output."""
    records, embedder = _corpus_records()
    index = FaissVectorIndex(records, FaissIndexConfig(embedder.dimension))
    query = SearchQuery(embedder.embed(("apple fruit",)).vectors[0], top_k=3)
    first = index.search(query)
    second = index.search(query)
    assert [h.chunk_id for h in first.hits] == [h.chunk_id for h in second.hits]
    assert [h.score for h in first.hits] == [h.score for h in second.hits]


def test_deterministic_tie_break_by_ascending_chunk_id() -> None:
    """Identical vectors under the same metric are ordered by ascending chunk_id,
    independent of insertion order, so ties never depend on FAISS internals.
    """
    chunk_a = chunk_fixed(
        ingest_text("tie content a", source_key="tie-a"), FixedConfig(size=20)
    ).chunks[0]
    chunk_b = chunk_fixed(
        ingest_text("tie content b", source_key="tie-b"), FixedConfig(size=20)
    ).chunks[0]
    vector = Vector((1.0, 0.0) + (0.0,) * 30)
    record_a = IndexedChunk(chunk_a, vector)
    record_b = IndexedChunk(chunk_b, vector)
    expected = sorted([record_a.chunk_id, record_b.chunk_id])

    forward = FaissVectorIndex((record_a, record_b), FaissIndexConfig(32))
    reverse = FaissVectorIndex((record_b, record_a), FaissIndexConfig(32))
    query = SearchQuery(vector, top_k=2)
    assert [h.chunk_id for h in forward.search(query).hits] == expected
    assert [h.chunk_id for h in reverse.search(query).hits] == expected


def test_deterministic_record_position_mapping() -> None:
    """Every returned hit's record is exactly the record that was indexed."""
    records, embedder = _corpus_records()
    index = FaissVectorIndex(records, FaissIndexConfig(embedder.dimension))
    query = SearchQuery(embedder.embed(("apple fruit",)).vectors[0], top_k=3)
    results = index.search(query)
    by_id = {record.chunk_id: record for record in records}
    for hit in results.hits:
        assert hit.record is by_id[hit.chunk_id]


def test_search_rejects_out_of_range_faiss_position_without_dereferencing() -> None:
    """A FAISS adapter must not index into application records with a bad position.

    This directly injects a faulty underlying index to exercise the safety net;
    real faiss.IndexFlat never returns an out-of-range position when the
    requested k does not exceed ntotal, which this adapter always ensures.
    """

    class _FaultyIndex:
        def search(self, _row, _k):
            return (
                np.array([[0.9]], dtype=np.float32),
                np.array([[-1]], dtype=np.int64),
            )

    records, embedder = _corpus_records()
    index = FaissVectorIndex(records, FaissIndexConfig(embedder.dimension))
    index._index = _FaultyIndex()
    query = SearchQuery(embedder.embed(("apple fruit",)).vectors[0], top_k=1)
    with pytest.raises(FaissOperationError):
        index.search(query)


def test_search_rejects_positive_out_of_range_faiss_position() -> None:
    """A positive but out-of-bounds position is also rejected, not just -1."""

    class _FaultyIndex:
        def search(self, _row, _k):
            return (
                np.array([[0.9]], dtype=np.float32),
                np.array([[999]], dtype=np.int64),
            )

    records, embedder = _corpus_records()
    index = FaissVectorIndex(records, FaissIndexConfig(embedder.dimension))
    index._index = _FaultyIndex()
    query = SearchQuery(embedder.embed(("apple fruit",)).vectors[0], top_k=1)
    with pytest.raises(FaissOperationError):
        index.search(query)


def test_search_rejects_nonfinite_faiss_score() -> None:
    """A nonfinite score from the underlying index is never exposed as a hit."""

    class _FaultyIndex:
        def search(self, _row, _k):
            return (
                np.array([[float("nan")]], dtype=np.float32),
                np.array([[0]], dtype=np.int64),
            )

    records, embedder = _corpus_records()
    index = FaissVectorIndex(records, FaissIndexConfig(embedder.dimension))
    index._index = _FaultyIndex()
    query = SearchQuery(embedder.embed(("apple fruit",)).vectors[0], top_k=1)
    with pytest.raises(FaissOperationError):
        index.search(query)


def test_end_to_end_ingest_chunk_embed_index_search() -> None:
    """Full offline workflow: text -> chunks -> embeddings -> FAISS -> ranked hits."""
    document = ingest_text(
        "Apples ripen in the orchard every autumn. "
        "Pears grow well beside the apple trees. "
        "Rockets launch from the coastal pad at dawn. "
        "Satellites orbit the planet for decades.",
        source_key="e2e-source",
    )
    chunks = chunk_fixed(document, FixedConfig(size=48)).chunks
    embedder = LocalHashEmbedder(dimension=64)
    batch = embedder.embed(tuple(chunk.content for chunk in chunks))
    records = to_indexed_chunks(chunks, batch)
    index = FaissVectorIndex(records, FaissIndexConfig(embedder.dimension))

    query_vector = embedder.embed(("apple harvest in an orchard",)).vectors[0]
    results = index.search(SearchQuery(query_vector, top_k=2))

    assert len(results.hits) == 2
    top_hit = results.hits[0]
    assert "apple" in top_hit.record.chunk.content.lower()
    assert top_hit.document_id == document.provenance.document_id
    assert results.hits[0].score >= results.hits[1].score


def test_isolation_no_story6_provider_sdks_required(tmp_path: Path) -> None:
    """A fresh interpreter using only the Story 5 FAISS path loads no later-
    story provider/UI SDK.

    This runs in its own subprocess rather than checking ``sys.modules`` in
    the current test process: in a full repository ``pytest`` run, module-01
    and module-02 tests (for example ``test_langchain_templates.py`` and
    ``test_streamlit.py``) already import ``langchain``/``streamlit`` earlier
    in the same shared process, before module-03's tests even run. Checking
    the current process's ``sys.modules`` would therefore fail regardless of
    whether Story 5 itself ever imports those SDKs, which is not what this
    test is meant to prove. A fresh subprocess isolates the question to
    exactly what Story 5's own import/use path causes to load.
    """
    script = (
        "import sys; "
        "from rag_engineering_foundations.chunking import FixedConfig, chunk_fixed; "
        "from rag_engineering_foundations.embeddings import LocalHashEmbedder; "
        "from rag_engineering_foundations.faiss_index import ("
        "FaissIndexConfig, FaissVectorIndex); "
        "from rag_engineering_foundations.ingestion import ingest_text; "
        "from rag_engineering_foundations.retrieval import ("
        "SearchQuery, to_indexed_chunks); "
        "document = ingest_text('apple pear orchard fruit', source_key='s'); "
        "chunk = chunk_fixed(document, FixedConfig(size=24)).chunks[0]; "
        "embedder = LocalHashEmbedder(dimension=8); "
        "batch = embedder.embed((chunk.content,)); "
        "records = to_indexed_chunks((chunk,), batch); "
        "index = FaissVectorIndex(records, FaissIndexConfig(embedder.dimension)); "
        "index.search(SearchQuery(embedder.embed(('apple',)).vectors[0], top_k=1)); "
        "print(sorted(set(sys.modules) & "
        "{'chromadb', 'pinecone', 'langchain', 'streamlit'}))"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert result.stdout.strip() == "[]"
