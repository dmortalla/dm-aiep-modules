"""Local ingest/chunk/embed/Chroma/query demonstration with no credentials."""

from rag_engineering_foundations.chroma_index import (
    ChromaIndexConfig,
    ChromaVectorIndex,
)
from rag_engineering_foundations.chunking import FixedConfig, chunk_fixed
from rag_engineering_foundations.embeddings import LocalHashEmbedder
from rag_engineering_foundations.ingestion import ingest_text
from rag_engineering_foundations.retrieval import SearchQuery, to_indexed_chunks


def main() -> None:
    """Retrieve application-owned sources through a real ephemeral collection."""
    document = ingest_text("apple orchard. rocket orbit.", source_key="story6")
    chunks = chunk_fixed(document, FixedConfig(size=14)).chunks
    embedder = LocalHashEmbedder(64)
    records = to_indexed_chunks(
        chunks, embedder.embed(tuple(c.content for c in chunks))
    )
    index = ChromaVectorIndex(records, ChromaIndexConfig(64, ef_search=100))
    try:
        query = SearchQuery(embedder.embed(("apple orchard",)).vectors[0], top_k=10)
        result = index.search(query)
        print("REAL local ephemeral Chroma; configured HNSW cosine, ef_search=100.")
        for hit in result.hits:
            print(f"rank={hit.rank} score={hit.score:.6f} chunk_id={hit.chunk_id}")
            print(f"document_id={hit.document_id} content={hit.record.chunk.content!r}")
    finally:
        index.close()


if __name__ == "__main__":
    main()
