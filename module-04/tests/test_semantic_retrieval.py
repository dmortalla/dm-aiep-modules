"""Module-4-owned corpus and semantic retrieval: ChromaDB and Pinecone boundaries.

ChromaDB tests run a genuine in-process ephemeral Chroma collection. Pinecone
tests exercise the real installed Pinecone SDK value types through an
injected offline index double; they verify the integration boundary only, not
a live Pinecone service. No test needs credentials or network access.
"""

import math
import socket
from dataclasses import FrozenInstanceError

import chromadb
import pytest
from advanced_rag_evaluation.bm25 import BM25Index, LexicalQuery
from advanced_rag_evaluation.corpus import ChunkProvenance, CorpusChunk, build_corpus
from advanced_rag_evaluation.errors import (
    CorpusError,
    SemanticConfigurationError,
    SemanticProviderError,
    SemanticQueryError,
    SemanticRetrievalError,
)
from advanced_rag_evaluation.hybrid_retrieval import fuse_results
from advanced_rag_evaluation.observability.failure_analysis import (
    Category,
    Stage,
    analyze_failure,
)
from advanced_rag_evaluation.semantic_retrieval import (
    ChromaSemanticIndex,
    EmbeddingBatch,
    HashEmbedder,
    PineconeSemanticIndex,
    SemanticHit,
    SemanticQuery,
    SemanticResults,
    connect_pinecone_index,
)
from chromadb.config import Settings
from pinecone import QueryResponse, ScoredVector, Vector

PASSAGES = (
    "Apples ripen in the orchard every autumn and are picked by hand.",
    "Pears grow on trees beside the apple rows and share the same harvest.",
    "Rockets launch from the coastal pad at dawn under tight safety checks.",
    "Satellites orbit the planet for decades, relaying data to ground stations.",
)
SECRET = "pcsk_SECRET-key-must-not-leak"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail on any attempted outbound connection."""

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Semantic retrieval tests must not use the network.")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture
def chunks():
    return build_corpus("semantic-test", PASSAGES)


class TestCorpus:
    def test_build_corpus_is_deterministic_with_shared_provenance(self) -> None:
        first, second = build_corpus("s", PASSAGES), build_corpus("s", PASSAGES)
        assert first == second
        assert [c.index for c in first] == [0, 1, 2, 3]
        assert len({c.chunk_id for c in first}) == 4
        assert {c.provenance for c in first} == {first[0].provenance}
        assert first[0].provenance.source_id == "s"

    def test_distinct_sources_get_distinct_document_ids(self) -> None:
        a = build_corpus("a", ("same text",))[0]
        b = build_corpus("b", ("same text",))[0]
        assert a.provenance.document_id != b.provenance.document_id
        assert a.chunk_id != b.chunk_id

    def test_passages_are_never_split_or_rewritten(self) -> None:
        text = "  One passage.\n\nStill the same passage.  "
        assert build_corpus("s", (text,))[0].content == text

    def test_content_is_hidden_from_repr_and_chunks_are_frozen(self, chunks) -> None:
        assert PASSAGES[0] not in repr(chunks[0])
        with pytest.raises(FrozenInstanceError):
            chunks[0].content = "changed"  # type: ignore[misc]

    @pytest.mark.parametrize(
        "source,passages",
        [("", ("x",)), ("s", ()), ("s", ["x"]), ("s", ("ok", " ")), ("s", (1,))],
    )
    def test_build_corpus_rejects_invalid_input(self, source, passages) -> None:
        with pytest.raises(CorpusError):
            build_corpus(source, passages)

    def test_chunk_rejects_invalid_fields(self) -> None:
        provenance = ChunkProvenance("s", "d")
        with pytest.raises(CorpusError):
            CorpusChunk("id", -1, "text", provenance)
        with pytest.raises(CorpusError):
            CorpusChunk("id", 0, "text", "not-provenance")  # type: ignore[arg-type]
        with pytest.raises(CorpusError):
            CorpusChunk("id", 0, "x" * 1_048_577, provenance)
        with pytest.raises(CorpusError):
            ChunkProvenance("s", "d" * 257)


class TestHashEmbedder:
    def test_identical_text_yields_identical_unit_vectors(self) -> None:
        embedder = HashEmbedder()
        batch = embedder.embed(("apple orchard", "apple orchard", "rocket"))
        assert batch.dimension == 64 and len(batch.vectors) == 3
        assert batch.vectors[0] == batch.vectors[1] != batch.vectors[2]
        for vector in batch.vectors:
            assert math.isclose(math.hypot(*vector), 1.0, rel_tol=1e-12)

    def test_text_without_alphanumeric_terms_is_still_nonzero(self) -> None:
        vector = HashEmbedder().embed(("!!! ---",)).vectors[0]
        assert math.hypot(*vector) > 0

    def test_embedding_id_names_the_actual_local_model(self) -> None:
        assert HashEmbedder(dimension=32).embedding_id == "module-4-local-hash:32"

    @pytest.mark.parametrize("dimension", [7, 4097, 64.0, "64", True])
    def test_rejects_invalid_dimension(self, dimension) -> None:
        with pytest.raises(SemanticConfigurationError):
            HashEmbedder(dimension=dimension)  # type: ignore[arg-type]

    @pytest.mark.parametrize("texts", [(), ["x"], ("ok", ""), ("ok", 3), ("\ud800",)])
    def test_rejects_invalid_text_batches(self, texts) -> None:
        with pytest.raises(SemanticQueryError):
            HashEmbedder().embed(texts)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "vectors,dimension",
        [((), 8), (((0.0,) * 7,), 8), (((float("nan"),) * 8,), 8), (([0.0] * 8,), 8)],
    )
    def test_embedding_batch_rejects_malformed_vectors(self, vectors, dimension):
        with pytest.raises(SemanticQueryError):
            EmbeddingBatch(vectors, dimension)


class TestSemanticContracts:
    @pytest.mark.parametrize("text,top_k", [("", 1), (" ", 1), ("q", 0), ("q", True)])
    def test_query_rejects_invalid_shape(self, text, top_k) -> None:
        with pytest.raises(SemanticQueryError):
            SemanticQuery(text, top_k)

    def test_query_text_is_hidden_from_repr(self) -> None:
        assert "private question" not in repr(SemanticQuery("private question"))

    def test_hit_and_results_validate_order_and_identity(self, chunks) -> None:
        query = SemanticQuery("apple", top_k=3)
        with pytest.raises(SemanticQueryError):
            SemanticHit(0, 1.5, chunks[0])
        with pytest.raises(SemanticQueryError):
            SemanticHit(0, 0.5, "not-a-chunk")  # type: ignore[arg-type]
        low, high = SemanticHit(0, 0.1, chunks[0]), SemanticHit(1, 0.9, chunks[1])
        with pytest.raises(SemanticQueryError):
            SemanticResults((low, high), query, "chromadb")
        dup = (SemanticHit(0, 0.9, chunks[0]), SemanticHit(1, 0.5, chunks[0]))
        with pytest.raises(SemanticQueryError):
            SemanticResults(dup, query, "chromadb")
        with pytest.raises(SemanticQueryError):
            SemanticResults((SemanticHit(0, 0.9, chunks[0]),), query, "faiss")


class TestChromaSemanticIndex:
    def test_genuine_chroma_ranks_identical_text_first(self, chunks) -> None:
        with ChromaSemanticIndex(chunks, HashEmbedder()) as index:
            results = index.search(SemanticQuery(PASSAGES[2], top_k=4))
        assert results.backend == "chromadb" and results.higher_is_better is True
        assert results.hits[0].chunk is chunks[2]
        assert math.isclose(results.hits[0].score, 1.0, abs_tol=1e-5)
        assert [h.rank for h in results.hits] == [0, 1, 2, 3]
        scores = [h.score for h in results.hits]
        assert scores == sorted(scores, reverse=True)

    def test_returned_chunks_are_the_applications_own_objects(self, chunks) -> None:
        with ChromaSemanticIndex(chunks, HashEmbedder()) as index:
            results = index.search(SemanticQuery("apple orchard", top_k=4))
        for hit in results.hits:
            assert hit.chunk in chunks
            assert hit.chunk.provenance is chunks[0].provenance
            assert hit.document_id == chunks[0].provenance.document_id

    def test_search_is_deterministic_and_top_k_is_bounded(self, chunks) -> None:
        with ChromaSemanticIndex(chunks, HashEmbedder(dimension=32)) as index:
            first = index.search(SemanticQuery("harvest rows", top_k=10_000))
            second = index.search(SemanticQuery("harvest rows", top_k=10_000))
            assert len(index.search(SemanticQuery("harvest", top_k=2)).hits) == 2
        assert [(h.chunk_id, h.score) for h in first.hits] == [
            (h.chunk_id, h.score) for h in second.hits
        ]
        assert len(first.hits) == len(chunks)

    def test_close_deletes_only_the_owned_collection(self, chunks) -> None:
        client = chromadb.EphemeralClient(settings=Settings(anonymized_telemetry=False))
        index = ChromaSemanticIndex(chunks, HashEmbedder(), client=client)
        name = index.collection_name
        assert name in [c.name for c in client.list_collections()]
        index.close()
        index.close()
        assert name not in [c.name for c in client.list_collections()]
        with pytest.raises(SemanticConfigurationError):
            index.search(SemanticQuery("apple"))

    def test_feeds_hybrid_fusion(self, chunks) -> None:
        lexical = BM25Index(chunks).search(LexicalQuery("apple orchard"))
        with ChromaSemanticIndex(chunks, HashEmbedder()) as index:
            semantic = index.search(SemanticQuery("apple orchard"))
        fused = fuse_results(lexical, semantic)
        assert fused.semantic_query is semantic.query
        assert all(c.chunk in chunks for c in fused.candidates)

    @pytest.mark.parametrize("bad", [(), "chunks", (1,)])
    def test_rejects_invalid_corpus(self, bad) -> None:
        with pytest.raises(SemanticConfigurationError):
            ChromaSemanticIndex(bad, HashEmbedder())  # type: ignore[arg-type]

    def test_rejects_duplicate_chunk_ids_and_bad_embedder(self, chunks) -> None:
        with pytest.raises(SemanticConfigurationError):
            ChromaSemanticIndex((chunks[0], chunks[0]), HashEmbedder())
        with pytest.raises(SemanticConfigurationError):
            ChromaSemanticIndex(chunks, object())  # type: ignore[arg-type]

    def test_rejects_malformed_embedder_output(self, chunks) -> None:
        class ShortEmbedder:
            dimension = 64

            def embed(self, texts):
                return HashEmbedder().embed(texts[:1])

        with pytest.raises(SemanticQueryError):
            ChromaSemanticIndex(chunks, ShortEmbedder())

    def test_provider_failures_are_sanitized(self, chunks) -> None:
        class FailingClient:
            def create_collection(self, *_args, **_kwargs):
                raise RuntimeError(f"connection refused api_key={SECRET}")

        with pytest.raises(SemanticProviderError) as caught:
            ChromaSemanticIndex(chunks, HashEmbedder(), client=FailingClient())
        assert SECRET not in str(caught.value)
        assert caught.value.__cause__ is None and caught.value.__suppress_context__

    @pytest.mark.parametrize(
        "response",
        [
            {"ids": [["unknown-id"]], "distances": [[0.1]]},
            {"ids": [["ID", "ID"]], "distances": [[0.1, 0.2]]},
            {"ids": [["ID"]], "distances": [[float("nan")]]},
            {"ids": [["ID"]], "distances": [[5.0]]},
            {"ids": [["ID"]], "distances": [[0.1, 0.2]]},
            {"ids": [[]], "distances": [[]]},
            {"ids": "ID", "distances": [[0.1]]},
        ],
    )
    def test_malformed_chroma_responses_are_rejected(self, chunks, response) -> None:
        chunk_id = chunks[0].chunk_id

        class FakeCollection:
            def add(self, **_kwargs):
                return None

            def query(self, **_kwargs):
                return {
                    key: (
                        [[chunk_id if v == "ID" else v for v in value[0]]]
                        if isinstance(value, list)
                        else value
                    )
                    for key, value in response.items()
                }

        class FakeClient:
            def create_collection(self, *_args, **_kwargs):
                return FakeCollection()

            def delete_collection(self, _name):
                return None

        index = ChromaSemanticIndex(chunks, HashEmbedder(), client=FakeClient())
        with pytest.raises(SemanticProviderError):
            index.search(SemanticQuery("apple"))


class OfflinePineconeIndex:
    """Offline double of ``pinecone.Index`` speaking the real SDK value types.

    It ranks stored vectors by cosine similarity, as a cosine-metric Pinecone
    index would. This verifies the Module 4 boundary, not the live service.
    """

    def __init__(self, *, response=None, fail_on=None) -> None:
        self.stored: dict[str, list[float]] = {}
        self.upserts: list[dict] = []
        self.queries: list[dict] = []
        self.response = response
        self.fail_on = fail_on

    def upsert(self, *, vectors, namespace, show_progress):
        if self.fail_on == "upsert":
            raise RuntimeError(f"401 Unauthorized api_key={SECRET}")
        self.upserts.append(
            {"vectors": vectors, "namespace": namespace, "progress": show_progress}
        )
        self.stored.update({vector.id: vector.values for vector in vectors})

    def query(self, *, top_k, vector, namespace, include_values, include_metadata):
        if self.fail_on == "query":
            raise RuntimeError(f"503 upstream payload {SECRET}")
        self.queries.append(
            {
                "top_k": top_k,
                "namespace": namespace,
                "values": include_values,
                "metadata": include_metadata,
            }
        )
        if self.response is not None:
            return self.response(self)
        scored = sorted(
            (
                (sum(a * b for a, b in zip(vector, values, strict=True)), chunk_id)
                for chunk_id, values in self.stored.items()
            ),
            reverse=True,
        )[:top_k]
        return QueryResponse(
            matches=[ScoredVector(id=i, score=s) for s, i in scored],
            namespace=namespace,
        )


class TestPineconeBoundary:
    def test_upserts_sdk_vectors_without_content(self, chunks) -> None:
        client = OfflinePineconeIndex()
        index = PineconeSemanticIndex(chunks, HashEmbedder(), client, namespace="ns")
        assert index.size == 4 and index.namespace == "ns"
        (call,) = client.upserts
        assert call["namespace"] == "ns" and call["progress"] is False
        assert all(type(v) is Vector for v in call["vectors"])
        assert [v.id for v in call["vectors"]] == [c.chunk_id for c in chunks]
        assert all(not v.metadata for v in call["vectors"])
        assert PASSAGES[0] not in repr(call["vectors"])

    def test_search_returns_validated_local_chunks(self, chunks) -> None:
        client = OfflinePineconeIndex()
        index = PineconeSemanticIndex(chunks, HashEmbedder(), client)
        results = index.search(SemanticQuery(PASSAGES[1], top_k=3))
        assert results.backend == "pinecone"
        assert results.hits[0].chunk is chunks[1]
        assert len(results.hits) == 3
        assert client.queries[-1] == {
            "top_k": 3,
            "namespace": "module-4-semantic",
            "values": False,
            "metadata": False,
        }

    def test_ordering_is_recomputed_with_chunk_id_tie_break(self, chunks) -> None:
        ids = [c.chunk_id for c in chunks]

        def tied(_client):
            return QueryResponse(
                matches=[ScoredVector(id=i, score=0.5) for i in reversed(ids)]
            )

        index = PineconeSemanticIndex(
            chunks, HashEmbedder(), OfflinePineconeIndex(response=tied)
        )
        results = index.search(SemanticQuery("apple", top_k=4))
        assert [h.chunk_id for h in results.hits] == sorted(ids)

    def test_matches_chroma_ranking_for_the_same_corpus(self, chunks) -> None:
        query = SemanticQuery("satellites relay data", top_k=4)
        pinecone_hits = (
            PineconeSemanticIndex(chunks, HashEmbedder(), OfflinePineconeIndex())
            .search(query)
            .hits
        )
        with ChromaSemanticIndex(chunks, HashEmbedder()) as index:
            chroma_hits = index.search(query).hits
        assert [h.chunk_id for h in pinecone_hits] == [h.chunk_id for h in chroma_hits]

    @pytest.mark.parametrize(
        "response",
        [
            lambda c: {"matches": []},
            lambda c: QueryResponse(matches=[{"id": "x", "score": 0.1}]),
            lambda c: QueryResponse(matches=[ScoredVector(id="unknown", score=0.1)]),
            lambda c: QueryResponse(matches=[]),
            lambda c: QueryResponse(
                matches=[ScoredVector(id=next(iter(c.stored)), score=float("inf"))]
            ),
            lambda c: QueryResponse(
                matches=[ScoredVector(id=next(iter(c.stored)), score=0.4)] * 2
            ),
        ],
    )
    def test_invalid_provider_responses_are_rejected(self, chunks, response) -> None:
        index = PineconeSemanticIndex(
            chunks, HashEmbedder(), OfflinePineconeIndex(response=response)
        )
        with pytest.raises(SemanticProviderError):
            index.search(SemanticQuery("apple"))

    @pytest.mark.parametrize("stage", ["upsert", "query"])
    def test_provider_failures_are_sanitized(self, chunks, stage) -> None:
        client = OfflinePineconeIndex(fail_on=stage)
        with pytest.raises(SemanticProviderError) as caught:
            PineconeSemanticIndex(chunks, HashEmbedder(), client).search(
                SemanticQuery("apple")
            )
        assert SECRET not in str(caught.value)
        assert caught.value.__cause__ is None and caught.value.__suppress_context__
        analysis = analyze_failure(Stage.RETRIEVAL, caught.value)
        assert analysis.category is Category.RETRIEVAL

    def test_rejects_invalid_client_and_namespace(self, chunks) -> None:
        with pytest.raises(SemanticConfigurationError):
            PineconeSemanticIndex(chunks, HashEmbedder(), object())  # type: ignore
        with pytest.raises(SemanticConfigurationError):
            PineconeSemanticIndex(
                chunks, HashEmbedder(), OfflinePineconeIndex(), namespace=" "
            )

    def test_connect_builds_a_real_sdk_handle_without_network(self) -> None:
        index = connect_pinecone_index(
            api_key=SECRET, host="https://m4-test.svc.pinecone.io"
        )
        assert type(index).__module__.startswith("pinecone")
        assert callable(index.upsert) and callable(index.query)

    @pytest.mark.parametrize(
        "api_key,host",
        [("", "https://h"), (SECRET, "http://insecure"), (SECRET, ""), (None, "h")],
    )
    def test_connect_rejects_invalid_configuration(self, api_key, host) -> None:
        with pytest.raises(SemanticConfigurationError) as caught:
            connect_pinecone_index(api_key=api_key, host=host)
        assert SECRET not in str(caught.value)


def test_semantic_errors_are_application_owned_retrieval_failures() -> None:
    for error in (
        SemanticConfigurationError("x"),
        SemanticQueryError("x"),
        SemanticProviderError("x"),
        CorpusError("x"),
    ):
        assert analyze_failure(Stage.RETRIEVAL, error).category is Category.RETRIEVAL
    assert issubclass(SemanticProviderError, SemanticRetrievalError)
