"""Offline Story 3 hybrid-retrieval demonstration; no network/credentials.

Run: uv run python module-04/examples/hybrid_search.py

Pipeline: build a Module 4 corpus -> build a Story 2 BM25 lexical index ->
build Module 4's semantic index (HashEmbedder + a real ephemeral ChromaDB
collection) -> search each leg independently -> fuse both rankings with
Story 3's Reciprocal Rank Fusion. This is a retrieval
demonstration only: no generation, reranking, caching, evaluation, or
observability is exercised here.
"""

from advanced_rag_evaluation.bm25 import BM25Index, LexicalQuery
from advanced_rag_evaluation.corpus import build_corpus
from advanced_rag_evaluation.hybrid_retrieval import HybridConfig, fuse_results
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
# Shares only "harvest"/"rows" with the corpus, so the two legs can weigh the
# same partial overlap differently (BM25 term statistics versus hashed-feature
# cosine similarity) -- illustrating why the legs disagree and fusion helps.
# The hash embedder measures token overlap, not learned meaning.
QUERY_TEXT = "harvest season on the rows"
DIMENSION = 32


def preview(text: str, limit: int = 56) -> str:
    """Return a short, intentionally truncated preview for learner-facing output."""
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def main() -> None:
    """Run lexical-only, semantic-only, and fused retrieval, and explain each."""
    print("Step 1: build a Module 4 corpus, one chunk per paragraph.")
    chunks = build_corpus("story-03-hybrid-demo", tuple(SOURCE_TEXT.split("\n\n")))
    for chunk in chunks:
        print(f"  [{chunk.index}] {preview(chunk.content)!r}")

    print(f"\nStep 2: build a Story 2 BM25 lexical index. Query: {QUERY_TEXT!r}")
    bm25 = BM25Index(chunks)
    lexical = bm25.search(LexicalQuery(QUERY_TEXT, top_k=len(chunks)))
    for hit in lexical.hits:
        print(f"  lexical_rank={hit.rank} score={hit.score:.4f} "
              f"content={preview(hit.chunk.content)!r}")

    print("\nStep 3: build Module 4's semantic index (HashEmbedder + ChromaDB).")
    with ChromaSemanticIndex(chunks, HashEmbedder(dimension=DIMENSION)) as index:
        semantic = index.search(SemanticQuery(QUERY_TEXT, top_k=len(chunks)))
    for hit in semantic.hits:
        print(f"  semantic_rank={hit.rank} score={hit.score:.4f} "
              f"content={preview(hit.chunk.content)!r}")

    print("\nStep 4: fuse both legs with Story 3 Reciprocal Rank Fusion.")
    fused = fuse_results(lexical, semantic, HybridConfig(top_k=len(chunks)))
    for candidate in fused.candidates:
        print(
            f"  fused_rank={candidate.rank} rrf_score={candidate.rrf_score:.5f} "
            f"lexical_rank={candidate.lexical_rank} "
            f"semantic_rank={candidate.semantic_rank} "
            f"content={preview(candidate.chunk.content)!r}"
        )

    print(
        "\nWhy this matters: the lexical and semantic legs disagree about which "
        "chunk is most relevant (different vocabularies, different scoring "
        "scales); Reciprocal Rank Fusion combines their rank *positions* -- "
        "never their raw, incomparable scores -- into one ranking that is "
        "more robust than trusting either leg alone. A chunk both legs agree "
        "on accumulates evidence from both and tends to rank higher than a "
        "chunk only one leg found."
    )


if __name__ == "__main__":
    main()
