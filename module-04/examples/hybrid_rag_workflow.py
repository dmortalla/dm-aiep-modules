"""Offline Story 10 end-to-end hybrid RAG workflow; no network/credentials.

Run: uv run python module-04/examples/hybrid_rag_workflow.py

Pipeline: dynamic retrieval -> BM25 + ChromaDB semantic legs fused by RRF
(through the in-memory retrieval cache) -> deterministic reranking -> context
filtering -> Module 4 extractive generation with citations -> HybridRagResult.

The extractive generator quotes retained passages; it is not a language
model. The pricing below is labeled fixture data, not a vendor price claim.
"""

from decimal import Decimal

from advanced_rag_evaluation.advanced_rag_pipeline import (
    HybridRagConfig,
    run_hybrid_rag,
)
from advanced_rag_evaluation.bm25 import BM25Index
from advanced_rag_evaluation.context_filtering import ContextFilterConfig
from advanced_rag_evaluation.corpus import build_corpus
from advanced_rag_evaluation.reranking import DeterministicOverlapScorer
from advanced_rag_evaluation.retrieval_cache import InMemoryRetrievalCache
from advanced_rag_evaluation.semantic_retrieval import ChromaSemanticIndex, HashEmbedder
from advanced_rag_evaluation.telemetry.cost import PricingConfig

PASSAGES = (
    "Apples ripen in the orchard every autumn. They are picked by hand at dawn.",
    "Pears grow on trees beside the apple rows and share the same harvest.",
    "Rockets launch from the coastal pad at dawn under tight safety checks.",
    "Satellites orbit the planet for decades, relaying data to ground stations.",
)
QUERY = "when are apples picked by hand"
FIXTURE_PRICING = PricingConfig(
    provider="demo-provider",
    model="demo-model",
    pricing_version="demo-2026-10-fixture",
    input_rate_usd_per_million_tokens=Decimal("3.00"),
    output_rate_usd_per_million_tokens=Decimal("15.00"),
)


def main() -> None:
    """Run the workflow twice and print the answer, citations, and evidence."""
    chunks = build_corpus("story-10-workflow-demo", PASSAGES)
    config = HybridRagConfig(
        context_filter=ContextFilterConfig(min_rerank_score=0.05, max_candidates=2)
    )
    cache = InMemoryRetrievalCache()
    with ChromaSemanticIndex(chunks, HashEmbedder(dimension=32)) as semantic:
        for run in (1, 2):
            result = run_hybrid_rag(
                QUERY,
                lexical=BM25Index(chunks),
                semantic=semantic,
                scorer=DeterministicOverlapScorer(),
                config=config,
                cache=cache,
                pricing=FIXTURE_PRICING,
            )
            print(f"=== Run {run}: {QUERY!r} ===")
            print(f"decision: top_k={result.decision.top_k} "
                  f"branch={result.decision.branch}")
            print(f"retrieval from_cache={result.retrieval.from_cache}")
            print(f"retained={len(result.context.items)} "
                  f"excluded={len(result.context.excluded)}")
            print(f"answer ({result.answer.evidence_kind}): {result.answer.text}")
            for citation in result.answer.citations:
                item = citation.item
                print(
                    f"  [{citation.marker}] document={citation.document_id} "
                    f"filter_order={item.order} rerank_rank={item.rerank_rank} "
                    f"hybrid_rank={item.hybrid_rank} rrf={item.rrf_score:.5f}"
                )
            print(f"stages={[t.stage for t in result.latency.stages]}")
            print(f"cost ({result.cost.usage.classification}): "
                  f"${result.cost.cost_usd}")
    print(
        "Why this matters: every citation resolves to a retained passage and its "
        "full retrieval evidence, the repeated query reused cached retrieval, and "
        "the cost is labeled as an estimate because no provider reported usage."
    )


if __name__ == "__main__":
    main()
