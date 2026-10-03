"""Offline end-to-end FAISS vector-search demonstration; no network/credentials.

Run: uv run python module-03/examples/vector_search.py

Pipeline: ingest -> chunk -> embed (LocalHashEmbedder) -> FAISS index -> embed
query -> ranked retrieval. This is a deterministic lexical-hash demonstration
of retrieval mechanics, not a production semantic-quality showcase.
"""

import re
from itertools import pairwise

from rag_engineering_foundations.chunking import RecursiveConfig, chunk_recursive
from rag_engineering_foundations.embeddings import LocalHashEmbedder
from rag_engineering_foundations.faiss_index import FaissIndexConfig, FaissVectorIndex
from rag_engineering_foundations.ingestion import ingest_text
from rag_engineering_foundations.retrieval import SearchQuery, to_indexed_chunks

SOURCE_TEXT = (
    "Apples ripen in the orchard every autumn and are picked by hand. "
    "Pears grow on trees beside the apple rows and share the same harvest. "
    "Rockets launch from the coastal pad at dawn under tight safety checks. "
    "Satellites orbit the planet for decades, relaying data back to ground stations."
)
QUERY_TEXT = "apple harvest in an orchard"


def preview(text: str, limit: int = 48) -> str:
    """Return a short, intentionally truncated preview for learner-facing output."""
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def main() -> None:
    """Run the full offline ingest-to-ranked-retrieval workflow and explain it."""
    print("Step 1: ingest the source document.")
    document = ingest_text(SOURCE_TEXT, source_key="story-05-vector-search-demo")
    print(f"  document_id={document.provenance.document_id}")
    print(f"  characters={document.provenance.characters}")

    print("\nStep 2: chunk the document (recursive split on sentence boundaries).")
    chunks = chunk_recursive(
        document, RecursiveConfig(size=90, separators=(". ",))
    ).chunks
    print(f"  chunk_count={len(chunks)}")
    for chunk in chunks:
        print(f"    [{chunk.index}] {preview(chunk.content)!r}")

    print("\nStep 3: embed every chunk with the deterministic LocalHashEmbedder.")
    embedder = LocalHashEmbedder(dimension=64)
    batch = embedder.embed(tuple(chunk.content for chunk in chunks))
    print(f"  embedding_dimension={batch.dimension}")
    records = to_indexed_chunks(chunks, batch)

    print("\nStep 4: build a genuine FAISS index over the embedded chunks.")
    config = FaissIndexConfig(dimension=embedder.dimension, metric="cosine")
    index = FaissVectorIndex(records, config)
    print(f"  index={index!r}")
    print(
        "  IndexFlatIP over L2-normalized vectors: exact brute-force cosine "
        "similarity, not an approximate (ANN) index. Exact search is chosen "
        "here because the corpus is small and the goal is to teach correct "
        "retrieval mechanics without approximation error obscuring them."
    )

    print(f"\nStep 5: embed the query and search.\n  query={QUERY_TEXT!r}")
    query_vector = embedder.embed((QUERY_TEXT,)).vectors[0]
    results = index.search(SearchQuery(query_vector, top_k=len(chunks)))

    print("\nStep 6: ranked results (rank 0 is the best match; higher is better).")
    query_words = set(re.findall(r"\w+", QUERY_TEXT.casefold()))
    for hit in results.hits:
        hit_words = set(re.findall(r"\w+", hit.record.chunk.content.casefold()))
        shared = sorted(hit_words & query_words)
        print(
            f"  rank={hit.rank} score={hit.score:.6f} shared_words={shared} "
            f"chunk_id={hit.chunk_id[:16]}... document_id={hit.document_id[:16]}..."
        )
        print(f"    content: {preview(hit.record.chunk.content)!r}")

    top = results.hits[0]
    top_words = set(re.findall(r"\w+", top.record.chunk.content.casefold()))
    shared = sorted(top_words & query_words)
    print(
        f"\nWhy rank 0 won: its source chunk shares the words {shared} with the "
        "query. LocalHashEmbedder hashes each shared word into the same feature "
        "bucket for both texts, so their vectors point in a similar direction, "
        "and FAISS's inner product (cosine, since both sides are normalized) "
        "is highest for this pair."
    )
    for earlier, later in pairwise(results.hits):
        if earlier.score == later.score:
            print(
                f"\nNote: ranks {earlier.rank} and {later.rank} are tied at "
                f"{earlier.score:.6f}. This is a real hash collision, not a "
                "bug: at dimension=64, two different words can land in the "
                "same feature bucket and produce the same similarity by "
                "coincidence. This is exactly the quality limitation "
                "LocalHashEmbedder documents; a production embedding model "
                "would not collapse unrelated chunks together this way."
            )


if __name__ == "__main__":
    main()
