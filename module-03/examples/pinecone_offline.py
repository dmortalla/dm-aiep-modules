"""Offline Pinecone adapter demonstration; never a live service demonstration."""

from pinecone import (
    DenseVectorField,
    IndexModel,
    IndexSchema,
    IndexStatus,
    ManagedDeployment,
    QueryResponse,
    ScoredVector,
    UpsertResponse,
)
from rag_engineering_foundations.chunking import FixedConfig, chunk_fixed
from rag_engineering_foundations.embeddings import LocalHashEmbedder
from rag_engineering_foundations.ingestion import ingest_text
from rag_engineering_foundations.pinecone_index import (
    PineconeIndexConfig,
    PineconeVectorIndex,
)
from rag_engineering_foundations.retrieval import SearchQuery, to_indexed_chunks


class OfflineClient:
    """Fixed provider response fixture using real Pinecone SDK value types.

    This fixture records translation requests; it does not simulate ANN search.
    """

    def __init__(self, dimension: int = 8, metric: str = "cosine") -> None:
        """Set the declared existing index configuration and empty request log."""
        self.dimension, self.metric = dimension, metric
        self.calls: list[tuple[str, object]] = []
        self.response: QueryResponse | None = None

    def describe_index(self, name: str) -> IndexModel:
        """Return genuine SDK index description; no HTTP client exists."""
        self.calls.append(("describe", name))
        return IndexModel(
            name=name,
            status=IndexStatus(ready=True, state="Ready"),
            schema=IndexSchema(
                fields={
                    "vector": DenseVectorField(
                        dimension=self.dimension, metric=self.metric
                    )
                }
            ),
            deployment=ManagedDeployment(cloud="aws", region="us-east-1"),
            deletion_protection="enabled",
        )

    def Index(self, name: str) -> "OfflineClient":
        """Record existing index selection and expose the offline data plane."""
        self.calls.append(("index", name))
        return self

    def upsert(self, **kwargs) -> UpsertResponse:
        """Record the real SDK vector payload and acknowledge its count."""
        self.calls.append(("upsert", kwargs))
        return UpsertResponse(upserted_count=len(kwargs["vectors"]))

    def query(self, **kwargs) -> QueryResponse:
        """Return explicit fixed matches, deliberately in reverse ID tie order."""
        self.calls.append(("query", kwargs))
        if self.response is not None:
            return self.response
        payload = next(value for kind, value in self.calls if kind == "upsert")
        ids = sorted((v.id for v in payload["vectors"]), reverse=True)
        return QueryResponse(
            namespace=kwargs["namespace"],
            matches=[
                ScoredVector(id=identity, score=0.5)
                for identity in ids[: kwargs["top_k"]]
            ],
        )


def demo_records():
    """Build exact source chunks and deterministic application embeddings."""
    document = ingest_text("apple orchard. rocket orbit.", source_key="story6")
    chunks = chunk_fixed(document, FixedConfig(size=14)).chunks
    embedder = LocalHashEmbedder(8)
    return to_indexed_chunks(chunks, embedder.embed(tuple(c.content for c in chunks)))


def main() -> None:
    """Print offline translation and fixed response mapping evidence."""
    client = OfflineClient()
    records = demo_records()
    index = PineconeVectorIndex(records, PineconeIndexConfig(8), client)
    query = SearchQuery(LocalHashEmbedder(8).embed(("apple",)).vectors[0], top_k=10)
    result = index.search(query)
    print("OFFLINE Pinecone adapter demonstration; no live service verification.")
    print("SDK request calls:", [kind for kind, _ in client.calls])
    for hit in result.hits:
        print(f"rank={hit.rank} score={hit.score:.6f} chunk_id={hit.chunk_id}")
    print("Scores are fixed fixture values, not measured semantic similarity.")


if __name__ == "__main__":
    main()
