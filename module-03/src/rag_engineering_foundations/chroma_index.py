"""Genuine local Chroma boundary with explicit embeddings and HNSW settings."""

from dataclasses import dataclass
from uuid import uuid4

import chromadb
from chromadb.config import Settings
from chromadb.errors import ChromaError

from ._store_validation import (
    StoreConfig,
    prepare,
    query_vector,
    records_map,
    results,
)
from .errors import ChromaOperationError, RetrievalError
from .retrieval import IndexedChunk, SearchQuery, SearchResults


@dataclass(frozen=True, slots=True)
class ChromaIndexConfig(StoreConfig):
    """Local HNSW configuration; metric is fixed at collection creation.

    Args:
        dimension: Expected vector dimension.
        metric: cosine or euclidean; see StoreConfig.
        ef_search: HNSW search breadth, 1..10000; larger favors recall over latency.

    Raises:
        RetrievalError: For invalid settings.
    """

    ef_search: int = 100

    def __post_init__(self) -> None:
        """Validate settings without constructing a client."""
        StoreConfig.__post_init__(self)
        if type(self.ef_search) is not int or not 1 <= self.ef_search <= 10_000:
            raise RetrievalError("Use integer ef_search from 1 to 10000.")


class ChromaVectorIndex:
    """Own a fresh ephemeral Chroma collection and application record registry."""

    def __init__(
        self, records: tuple[IndexedChunk, ...], config: ChromaIndexConfig
    ) -> None:
        """Validate then insert explicit vectors into a genuine Chroma collection.

        Args:
            records: Unique validated records, bounded to 10000.
            config: Immutable local collection configuration.

        Raises:
            RetrievalError: For invalid input, before SDK mutation.
            ChromaOperationError: For SDK construction/insertion failures.
        """
        if type(config) is not ChromaIndexConfig:
            raise RetrievalError("Supply a validated ChromaIndexConfig.")
        mapping = records_map(records, config)
        try:
            client = chromadb.EphemeralClient(Settings(anonymized_telemetry=False))
            collection = client.create_collection(
                name="story6-" + uuid4().hex,
                embedding_function=None,
                configuration={
                    "hnsw": {
                        "space": "cosine" if config.metric == "cosine" else "l2",
                        "ef_search": config.ef_search,
                    }
                },
            )
            # Respect the installed backend's maximum batch size.
            batch_size = client.get_max_batch_size()
            for offset in range(0, len(records), batch_size):
                batch = records[offset : offset + batch_size]
                collection.add(
                    ids=[r.chunk_id for r in batch],
                    embeddings=[prepare(r.vector, config) for r in batch],
                    metadatas=[{"document_id": r.document_id} for r in batch],
                )
        except (ChromaError, ValueError, RuntimeError):
            raise ChromaOperationError(
                "Chroma construction failed; verify local SDK configuration."
            ) from None
        self._client, self._collection = client, collection
        self._records, self._config = mapping, config
        self._closed = False

    @property
    def dimension(self) -> int:
        """Return configured vector dimension."""
        return self._config.dimension

    @property
    def size(self) -> int:
        """Return application registry size."""
        return len(self._records)

    def close(self) -> None:
        """Delete this owned collection; repeated close is harmless.

        Raises:
            ChromaOperationError: If SDK cleanup fails.
        """
        if not self._closed:
            try:
                self._client.delete_collection(self._collection.name)
            except (ChromaError, ValueError, RuntimeError):
                raise ChromaOperationError(
                    "Chroma cleanup failed; retry cleanup."
                ) from None
            self._closed = True

    def search(self, query: SearchQuery) -> SearchResults:
        """Query explicit vectors, validate distances/IDs, and rank candidates.

        Args:
            query: Validated dimension-compatible query.

        Returns:
            Provider-neutral results with cosine similarity or Euclidean distance.

        Raises:
            RetrievalError: For invalid query or closed collection.
            ChromaOperationError: For SDK failures or malformed responses.
        """
        vector = query_vector(query, self._config)
        if self._closed:
            raise RetrievalError(
                "Build a new collection before searching a closed index."
            )
        try:
            response = self._collection.query(
                query_embeddings=[vector],
                n_results=min(query.top_k, self.size),
                include=["distances"],
            )
        except (ChromaError, ValueError, RuntimeError):
            raise ChromaOperationError(
                "Chroma query failed; verify collection state."
            ) from None
        if type(response) is not dict:
            raise ChromaOperationError("Chroma returned a malformed query response.")
        ids, distances = response.get("ids"), response.get("distances")
        if (
            type(ids) is not list
            or type(distances) is not list
            or len(ids) != 1
            or len(distances) != 1
            or type(ids[0]) is not list
            or type(distances[0]) is not list
            or len(ids[0]) != len(distances[0])
        ):
            raise ChromaOperationError("Chroma returned malformed result rows.")
        return results(
            list(zip(ids[0], distances[0], strict=True)),
            self._records,
            query,
            self._config.metric,
            ChromaOperationError,
            cosine_distance=True,
        )
