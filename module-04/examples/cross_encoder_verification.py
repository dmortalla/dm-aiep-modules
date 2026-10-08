"""Explicit opt-in genuine sentence-transformers CrossEncoder verification.

Run: uv run python module-04/examples/cross_encoder_verification.py

This is NOT part of the normal credential-free, network-free quality gates.
It genuinely instantiates ``SentenceTransformersCrossEncoderScorer`` and runs
real inference through the configured Hugging Face cross-encoder model
(default: ``cross-encoder/ms-marco-MiniLM-L-6-v2``, ~80 MB). The first run
downloads and locally caches the model through ``sentence-transformers``'s
own Hugging Face Hub integration; this requires outbound network access and
local disk space, and no model weights are committed to this repository. No
credential is required for this public model.

If model acquisition fails (no network, blocked registry, insufficient
resources), this script reports the exact failure from the Module 4 adapter
boundary (``CrossEncoderUnavailableError``/``CrossEncoderInferenceError``)
rather than silently falling back to the deterministic scorer -- Story 4
explicitly forbids that fallback.

Set ADVANCED_RAG_CROSS_ENCODER_MODEL to override the model identifier.
"""

import os

from advanced_rag_evaluation.bm25 import BM25Index, LexicalQuery
from advanced_rag_evaluation.corpus import build_corpus
from advanced_rag_evaluation.errors import RerankScorerError
from advanced_rag_evaluation.hybrid_retrieval import HybridConfig, fuse_results
from advanced_rag_evaluation.reranking import (
    RerankConfig,
    SentenceTransformersCrossEncoderScorer,
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
QUERY_TEXT = "harvest season on the rows"
DIMENSION = 32


def preview(text: str, limit: int = 56) -> str:
    """Return a short, intentionally truncated preview for learner-facing output."""
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def main() -> None:
    """Build a real Story 3 hybrid result, then rerank it with a real CrossEncoder."""
    model_name = os.environ.get(
        "ADVANCED_RAG_CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
    )
    print(f"Configured cross-encoder model: {model_name!r}")
    print(
        "This may download the model on first use (network + local disk "
        "required); no credential is needed for this public model.\n"
    )

    passages = tuple(SOURCE_TEXT.split("\n\n"))
    chunks = build_corpus("story-04-cross-encoder-demo", passages)
    bm25 = BM25Index(chunks)
    lexical = bm25.search(LexicalQuery(QUERY_TEXT, top_k=len(chunks)))
    with ChromaSemanticIndex(chunks, HashEmbedder(dimension=DIMENSION)) as index:
        semantic = index.search(SemanticQuery(QUERY_TEXT, top_k=len(chunks)))
    hybrid = fuse_results(lexical, semantic, HybridConfig(top_k=len(chunks)))

    scorer = SentenceTransformersCrossEncoderScorer(model_name=model_name)
    try:
        reranked = rerank(
            QUERY_TEXT, hybrid, scorer, RerankConfig(top_k=len(hybrid.candidates))
        )
    except RerankScorerError as exc:
        print("LIVE CROSS-ENCODER VERIFICATION: NOT ESTABLISHED.")
        print(f"  {type(exc).__name__}: {exc}")
        print(
            "  This records the exact unverified boundary rather than "
            "claiming success; the deterministic Story 4 path "
            "(reranking_demo.py) is unaffected and remains credential-free."
        )
        raise SystemExit(1) from exc

    print("LIVE CROSS-ENCODER VERIFICATION: genuine model inference executed.")
    for candidate in reranked.candidates:
        print(
            f"  post_rerank_rank={candidate.rank} "
            f"rerank_score={candidate.rerank_score:.4f} "
            f"hybrid_rank={candidate.hybrid_rank} "
            f"content={preview(candidate.chunk.content)!r}"
        )


if __name__ == "__main__":
    main()
