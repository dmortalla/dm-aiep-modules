"""Offline Story 4 reranking demonstration; no network/credentials.

Run: uv run python module-04/examples/reranking_demo.py

Pipeline: Module 4 corpus -> BM25 lexical leg (Story 2) -> Module 4
semantic leg (HashEmbedder + ephemeral ChromaDB) -> Reciprocal Rank Fusion
(Story 3) -> Story 4 reranking with DeterministicOverlapScorer.

DeterministicOverlapScorer is explicitly test/demo infrastructure, a simple
query/candidate token-overlap score -- it is NOT a trained cross-encoder and
does not by itself satisfy Module 4's cross-encoder source requirement
(M4-RET-05). For genuine sentence-transformers CrossEncoder execution, see
the separate, explicit opt-in script:
``module-04/examples/cross_encoder_verification.py``.
"""

from advanced_rag_evaluation.bm25 import BM25Index, LexicalQuery
from advanced_rag_evaluation.corpus import build_corpus
from advanced_rag_evaluation.hybrid_retrieval import HybridConfig, fuse_results
from advanced_rag_evaluation.reranking import (
    DeterministicOverlapScorer,
    RerankConfig,
    rerank,
)
from advanced_rag_evaluation.semantic_retrieval import (
    ChromaSemanticIndex,
    HashEmbedder,
    SemanticQuery,
)

SOURCE_TEXT = (
    "Apples ripen in the orchard every autumn and are picked by hand.\n\n"
    "Pears grow on trees beside the apple rows and share the same harvest.\n\n"
    "Rockets launch from the coastal pad at dawn under tight safety checks.\n\n"
    "Satellites orbit the planet for decades, relaying data back to ground "
    "stations."
)
QUERY_TEXT = "picked by hand every autumn"
DIMENSION = 32


def preview(text: str, limit: int = 56) -> str:
    """Return a short, intentionally truncated preview for learner-facing output."""
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def main() -> None:
    """Run fusion then reranking, and explain what reranking changed."""
    print("Step 1: build a Module 4 corpus, one chunk per paragraph.")
    chunks = build_corpus("story-04-rerank-demo", tuple(SOURCE_TEXT.split("\n\n")))

    print(f"\nStep 2: build Story 2 BM25 + Module 4 semantic legs for {QUERY_TEXT!r}.")
    bm25 = BM25Index(chunks)
    lexical = bm25.search(LexicalQuery(QUERY_TEXT, top_k=len(chunks)))
    with ChromaSemanticIndex(chunks, HashEmbedder(dimension=DIMENSION)) as index:
        semantic = index.search(SemanticQuery(QUERY_TEXT, top_k=len(chunks)))

    print("\nStep 3: fuse both legs with Story 3 Reciprocal Rank Fusion.")
    hybrid = fuse_results(lexical, semantic, HybridConfig(top_k=len(chunks)))
    for candidate in hybrid.candidates:
        print(
            f"  fused_rank={candidate.rank} rrf_score={candidate.rrf_score:.5f} "
            f"content={preview(candidate.chunk.content)!r}"
        )

    print(
        "\nStep 4: rerank the fused candidates with Story 4's "
        "DeterministicOverlapScorer (demonstration/test scorer, not a "
        "trained cross-encoder)."
    )
    reranked = rerank(
        QUERY_TEXT,
        hybrid,
        DeterministicOverlapScorer(),
        RerankConfig(top_k=len(hybrid.candidates)),
    )
    for candidate in reranked.candidates:
        print(
            f"  post_rerank_rank={candidate.rank} "
            f"rerank_score={candidate.rerank_score:.4f} "
            f"hybrid_rank={candidate.hybrid_rank} rrf_score={candidate.rrf_score:.5f} "
            f"content={preview(candidate.chunk.content)!r}"
        )

    print(
        "\nWhy this matters: fusion already combined lexical and semantic "
        "evidence into one ranking, but that ranking still only reflects "
        "term overlap and lexical-hash similarity. A reranker scores each "
        "fused candidate directly against the query with a model dedicated "
        "to relevance judgment, which can promote a candidate fusion ranked "
        "lower and demote one it ranked higher -- every candidate still "
        "carries its pre-rerank hybrid_rank and rrf_score as evidence, so "
        "the change is fully inspectable, not a black box."
    )


if __name__ == "__main__":
    main()
