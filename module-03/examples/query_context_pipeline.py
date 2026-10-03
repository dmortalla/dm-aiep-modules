"""Offline Story 7 demonstration: query transformation, retrieval, and context
optimization; no network/credentials.

Run: uv run python module-03/examples/query_context_pipeline.py

Pipeline: original query -> query transformation (decomposition) -> embedding
(LocalHashEmbedder) -> FAISS VectorIndex search -> deterministic merge across
transformed queries -> deterministic, budget-bounded, whole-chunk context
optimization. This is a deterministic lexical-hash demonstration of retrieval
and context-selection mechanics, not a production semantic-quality showcase,
and it stops before any answer generation (Story 8).
"""

from rag_engineering_foundations.chunking import RecursiveConfig, chunk_recursive
from rag_engineering_foundations.context_optimization import (
    ContextOptimizationConfig,
    optimize_context,
)
from rag_engineering_foundations.embeddings import LocalHashEmbedder
from rag_engineering_foundations.faiss_index import FaissIndexConfig, FaissVectorIndex
from rag_engineering_foundations.ingestion import ingest_text
from rag_engineering_foundations.query_transformation import QueryTransformConfig
from rag_engineering_foundations.retrieval import to_indexed_chunks
from rag_engineering_foundations.retrieval_workflow import retrieve

SOURCE_TEXT = (
    "Apples ripen in the orchard every autumn and are picked by hand. "
    "Pears grow on trees beside the apple rows and share the same harvest. "
    "Rockets launch from the coastal pad at dawn under tight safety checks. "
    "Satellites orbit the planet for decades, relaying data back to ground stations."
)
QUERY_TEXT = "apple harvest in an orchard; rocket launch safety"


def preview(text: str, limit: int = 60) -> str:
    """Return a short, intentionally truncated preview for learner-facing output."""
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def main() -> None:
    """Run the full offline query -> transform -> retrieve -> optimize workflow."""
    print("Step 1: ingest and chunk the source document.")
    document = ingest_text(SOURCE_TEXT, source_key="story-07-query-context-demo")
    chunks = chunk_recursive(
        document, RecursiveConfig(size=90, separators=(". ",))
    ).chunks
    print(f"  chunk_count={len(chunks)}")
    for chunk in chunks:
        print(f"    [{chunk.index}] {preview(chunk.content)!r}")

    print("\nStep 2: embed every chunk and build a real FAISS index.")
    embedder = LocalHashEmbedder(dimension=64)
    batch = embedder.embed(tuple(chunk.content for chunk in chunks))
    records = to_indexed_chunks(chunks, batch)
    index = FaissVectorIndex(
        records, FaissIndexConfig(dimension=embedder.dimension, metric="cosine")
    )

    print(f"\nStep 3: transform the original query.\n  original_query={QUERY_TEXT!r}")
    transform_config = QueryTransformConfig(separators=(";",))
    result = retrieve(
        QUERY_TEXT, embedder, index, top_k=2, transform_config=transform_config
    )
    print("  derived retrieval queries (deterministic decomposition on ';'):")
    for transformed in result.transformation.queries:
        print(f"    technique={transformed.technique!r} text={transformed.text!r}")

    print(
        "\nStep 4: merged, deduplicated, ranked candidates across every "
        "transformed query (higher_is_better="
        f"{result.higher_is_better})."
    )
    for candidate in result.candidates:
        print(
            f"  score={candidate.score:.6f} chunk_id={candidate.chunk_id[:16]}... "
            f"produced_by={candidate.produced_by}"
        )
        print(f"    content: {preview(candidate.hit.record.chunk.content)!r}")

    print("\nStep 5: optimize bounded context for a later generation stage.")
    context_config = ContextOptimizationConfig(max_characters=120, max_chunks=10)
    optimized = optimize_context(result.candidates, context_config)
    print(
        f"  max_characters={context_config.max_characters} "
        f"total_characters={optimized.total_characters}"
    )
    print("  included (whole chunks, in rank order):")
    for item in optimized.items:
        print(
            f"    order={item.order} chunk_id={item.chunk_id[:16]}... "
            f"score={item.score:.6f}"
        )
        print(f"      content: {item.content!r}")
    print("  excluded (explicit reason, never silently dropped):")
    for excluded in optimized.excluded:
        print(f"    chunk_id={excluded.chunk_id[:16]}... reason={excluded.reason}")

    print(
        "\nWhat this proves: a compound query decomposes into independent "
        "retrieval-oriented subqueries deterministically; each subquery's "
        "embedding is searched against the same FAISS VectorIndex; the merged "
        "candidates stay traceable to whichever transformed query produced "
        "them; and a fixed character budget deterministically selects whole "
        "chunks, stopping (never truncating mid-chunk) at the first chunk "
        "that would not fit, with every exclusion recorded and explained.\n"
        "Limitations: LocalHashEmbedder is a deterministic lexical-hash "
        "stand-in, not a trained semantic model, so ranking here reflects "
        "shared words, not meaning; decomposition and merge semantics are "
        "demonstrated at a toy scale and do not claim retrieval quality at "
        "corpus scale. No generation/answer step follows; that is Story 8."
    )


if __name__ == "__main__":
    main()
