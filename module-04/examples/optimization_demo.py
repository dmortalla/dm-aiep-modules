"""Offline Story 5 optimization demonstration; no network/credentials.

Run: uv run python module-04/examples/optimization_demo.py

Pipeline: Module 4 corpus -> Story 5 dynamic-retrieval decision ->
Story 2 BM25 + Module 4 ChromaDB semantic legs (breadth set by that decision) ->
Story 3 RRF fusion, wrapped in a Story 5 in-memory retrieval cache -> Story 4
deterministic reranking -> Story 5 context filtering.

This uses Story 4's DeterministicOverlapScorer, not the real cross-encoder,
so this lab stays credential-free and network-free (see
module-04/examples/cross_encoder_verification.py for the real-model path).
"""

from advanced_rag_evaluation.bm25 import BM25Index, LexicalQuery
from advanced_rag_evaluation.context_filtering import (
    ContextFilterConfig,
    filter_context,
)
from advanced_rag_evaluation.corpus import build_corpus
from advanced_rag_evaluation.dynamic_retrieval import decide_retrieval
from advanced_rag_evaluation.hybrid_retrieval import HybridConfig, fuse_results
from advanced_rag_evaluation.reranking import (
    DeterministicOverlapScorer,
    RerankConfig,
    rerank,
)
from advanced_rag_evaluation.retrieval_cache import (
    InMemoryRetrievalCache,
    RetrievalCacheKey,
    fingerprint_configs,
    get_or_retrieve,
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
DIMENSION = 32


def preview(text: str, limit: int = 56) -> str:
    """Return a short, intentionally truncated preview for learner-facing output."""
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def main() -> None:
    """Run dynamic retrieval -> cached fusion -> rerank -> filter, three times."""
    print("Step 1: build a Module 4 corpus, one chunk per paragraph.")
    passages = tuple(SOURCE_TEXT.split("\n\n"))
    chunks = build_corpus("story-05-optimization-demo", passages)

    bm25 = BM25Index(chunks)
    with ChromaSemanticIndex(chunks, HashEmbedder(dimension=DIMENSION)) as index:
        _run_queries(bm25, index)


def _run_queries(bm25: BM25Index, semantic_index: ChromaSemanticIndex) -> None:
    """Run the three demonstration queries against one open semantic index."""

    cache = InMemoryRetrievalCache()
    retrieve_calls = {"n": 0}

    def run_query(query_text: str) -> None:
        print(f"\n=== Query: {query_text!r} ===")

        decision = decide_retrieval(query_text)
        print(
            f"Step 2: dynamic retrieval decision -> top_k={decision.top_k} "
            f"branch={decision.branch}"
        )
        print(f"  rationale: {decision.rationale}")

        hybrid_config = HybridConfig(top_k=decision.top_k)
        cache_key = RetrievalCacheKey(
            query_text, fingerprint_configs(hybrid_config, decision)
        )

        def retrieve():
            retrieve_calls["n"] += 1
            lexical = bm25.search(LexicalQuery(query_text, top_k=decision.top_k))
            semantic = semantic_index.search(
                SemanticQuery(query_text, top_k=decision.top_k)
            )
            return fuse_results(lexical, semantic, hybrid_config)

        cached = get_or_retrieve(cache, cache_key, retrieve)
        print(
            f"Step 3: retrieval-cache lookup -> from_cache={cached.from_cache} "
            f"(retrieve() invoked {retrieve_calls['n']} time(s) total so far)"
        )

        reranked = rerank(
            query_text,
            cached.hybrid,
            DeterministicOverlapScorer(),
            RerankConfig(top_k=len(cached.hybrid.candidates)),
        )
        print("Step 4: Story 4 deterministic reranking complete.")

        filtered = filter_context(
            reranked, ContextFilterConfig(min_rerank_score=0.0, max_candidates=3)
        )
        print(
            f"Step 5: context filtering -> retained={len(filtered.items)} "
            f"excluded={len(filtered.excluded)}"
        )
        for item in filtered.items:
            print(
                f"  retained order={item.order} rerank_score={item.rerank_score:.4f} "
                f"hybrid_rank={item.hybrid_rank} rrf_score={item.rrf_score:.5f} "
                f"content={preview(item.chunk.content)!r}"
            )
        for exclusion in filtered.excluded:
            print(
                f"  excluded chunk_id={exclusion.chunk_id[:16]}... "
                f"reason={exclusion.reason}"
            )

    run_query("picked by hand every autumn")
    run_query("picked by hand every autumn")
    run_query("ground stations relaying decades")

    print(
        f"\nWhy this matters: retrieve() was invoked {retrieve_calls['n']} time(s) "
        "across 3 calls (2 identical + 1 distinct query) -- the repeated query was "
        "genuinely served from the Story 5 cache, not recomputed, while the "
        "dynamic-retrieval decision, reranking, and filtering stages each "
        "remained independently inspectable: every retained chunk still carries "
        "its original hybrid rank, RRF score, rerank rank, and rerank score "
        "alongside the Story 5 decisions applied on top of it."
    )


if __name__ == "__main__":
    main()
