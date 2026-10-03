"""Credential-free Story 8 RAG architecture and knowledge-freshness demonstration.

Run: uv run python module-03/examples/rag_freshness.py
"""

from rag_engineering_foundations.chunking import FixedConfig, chunk_fixed
from rag_engineering_foundations.context_optimization import (
    ContextOptimizationConfig,
    optimize_context,
)
from rag_engineering_foundations.embeddings import LocalHashEmbedder
from rag_engineering_foundations.faiss_index import FaissIndexConfig, FaissVectorIndex
from rag_engineering_foundations.generation import (
    GenerationRequest,
    LocalExtractiveGenerator,
    generate,
)
from rag_engineering_foundations.ingestion import ingest_text
from rag_engineering_foundations.langchain_rag import run_langchain_rag
from rag_engineering_foundations.query_transformation import QueryTransformConfig
from rag_engineering_foundations.rag_pipeline import RagConfig, RagResult, run_rag
from rag_engineering_foundations.retrieval import to_indexed_chunks

QUERY = "  Atlas opening hours; Atlas schedule  "
STATE_A = "Atlas library opens at 09:00 on weekdays."
STATE_B = "Atlas library opens at 07:00 on weekdays."


def build_index(text: str, embedder: LocalHashEmbedder) -> FaissVectorIndex:
    """Ingest, chunk, embed, and build a real FAISS corpus snapshot.

    Args:
        text: Corpus revision, treated as untrusted evidence.
        embedder: Unchanged application-selected lexical embedder.

    Returns:
        Fresh FAISS index containing the revision's exact source chunk.
    """
    document = ingest_text(text, source_key="atlas-library-bulletin")
    chunks = chunk_fixed(document, FixedConfig(size=256)).chunks
    records = to_indexed_chunks(
        chunks, embedder.embed(tuple(chunk.content for chunk in chunks))
    )
    return FaissVectorIndex(records, FaissIndexConfig(dimension=embedder.dimension))


def show(label: str, result: RagResult) -> None:
    """Print deliberately accessed query, context, generation, and provenance."""
    print(f"{label}: integration={result.integration}")
    print(f"  original_query={result.original_query!r}")
    for query in result.retrieval.transformation.queries:
        print(f"  transformed={query.text!r} technique={query.technique}")
    for candidate in result.retrieval.candidates:
        chunk = candidate.hit.record.chunk
        print(f"  chunk_id={chunk.chunk_id}")
        print(f"  document_id={candidate.document_id}")
        print(f"  source_id={chunk.provenance.source_id}")
        print(f"  offsets=[{chunk.start},{chunk.end}) score={candidate.score:.6f}")
        print(f"  produced_by={candidate.produced_by!r}")
    print(
        f"  context_characters={result.context.total_characters} "
        f"budget={result.config.context.max_characters}"
    )
    print(f"  optimized_context={tuple(i.content for i in result.context.items)!r}")
    print(f"  answer={result.generation.answer!r}")
    print(
        f"  generator={result.generation.generator_id} "
        f"model={result.generation.model_id} "
        f"citations={result.generation.cited_chunk_ids!r}"
    )


def main() -> None:
    """Demonstrate unknown -> corpus A -> refreshed corpus B with one generator."""
    embedder = LocalHashEmbedder(dimension=64)
    generator = LocalExtractiveGenerator()
    config = RagConfig(
        top_k=1,
        transformation=QueryTransformConfig(separators=(";",)),
        context=ContextOptimizationConfig(max_characters=256, max_chunks=1),
    )
    unknown = generate(GenerationRequest(QUERY, optimize_context(())), generator)
    print(f"Without retrieved evidence: {unknown.answer}")
    a = run_rag(
        QUERY, embedder, build_index(STATE_A, embedder), generator, config=config
    )
    b = run_rag(
        QUERY, embedder, build_index(STATE_B, embedder), generator, config=config
    )
    lc = run_langchain_rag(
        QUERY, embedder, build_index(STATE_B, embedder), generator, config=config
    )
    show("Corpus A", a)
    show("Corpus B", b)
    show("LangChain corpus B", lc)
    assert a.generation.answer == STATE_A
    assert b.generation.answer == lc.generation.answer == STATE_B
    assert a.generation.model_id == b.generation.model_id == "verbatim-v1"
    print("Same generator instance/configuration; no retraining or model modification.")
    print(
        "Proves: refreshing the indexed corpus changes retrieved evidence and answer."
    )
    print("RAG improves freshness only when its source corpus is refreshed; not truth.")
    print("LocalHashEmbedder is a deterministic lexical-hash stand-in, not a trained")
    print(
        "semantic embedding model. LocalExtractiveGenerator copies evidence verbatim;"
    )
    print("it is a demonstration/test implementation, not a production semantic model.")


if __name__ == "__main__":
    main()
