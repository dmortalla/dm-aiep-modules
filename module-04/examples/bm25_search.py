"""Offline Story 2 BM25 lexical-retrieval demonstration; no network/credentials.

Run: uv run python module-04/examples/bm25_search.py

Pipeline: build a Module 4 corpus from pre-split passages -> build a BM25
index (Module 4, Story 2) -> rank chunks for two queries. This demonstrates
lexical (term-overlap) ranking only; it is not a semantic-quality showcase.
Fusion with Module 4's semantic retrieval is shown in hybrid_search.py.
"""

from advanced_rag_evaluation.bm25 import BM25Index, LexicalQuery
from advanced_rag_evaluation.corpus import build_corpus

SOURCE_TEXT = (
    "Apples ripen in the orchard every autumn and are picked by hand.\n\n"
    "Pears grow on trees beside the apple rows and share the same harvest.\n\n"
    "Rockets launch from the coastal pad at dawn under tight safety checks.\n\n"
    "Satellites orbit the planet for decades, relaying data back to ground "
    "stations."
)
QUERIES = ("apple harvest in an orchard", "rocket launch safety")


def preview(text: str, limit: int = 60) -> str:
    """Return a short, intentionally truncated preview for learner-facing output."""
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def main() -> None:
    """Run the offline ingest-to-ranked-BM25-retrieval workflow and explain it."""
    print("Step 1: build a Module 4 corpus, one chunk per paragraph.")
    chunks = build_corpus("story-02-bm25-demo", tuple(SOURCE_TEXT.split("\n\n")))
    print(f"  document_id={chunks[0].provenance.document_id}")

    print("\nStep 2: inspect the chunks and their stable positions.")
    for chunk in chunks:
        print(f"  [{chunk.index}] {preview(chunk.content)!r}")

    print("\nStep 3: build a Module 4 BM25 lexical index over those chunks.")
    index = BM25Index(chunks)
    print(f"  indexed chunks={index.size}")

    for query_text in QUERIES:
        print(f"\nStep 4: rank chunks for query {query_text!r}.")
        results = index.search(LexicalQuery(query_text, top_k=len(chunks)))
        for hit in results.hits:
            print(
                f"  rank={hit.rank} score={hit.score:.4f} "
                f"chunk_id={hit.chunk_id[:16]}... "
                f"content={preview(hit.chunk.content)!r}"
            )

    print(
        "\nWhy this matters: BM25 ranks chunks by term overlap/frequency alone, "
        "independent of any embedding model. Story 3 fuses these chunk_id-"
        "addressable rankings with Module 4's semantic retrieval leg into one "
        "hybrid result."
    )


if __name__ == "__main__":
    main()
