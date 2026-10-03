"""Pinecone SDK boundary; injected clients keep normal demonstrations offline."""

import re
from dataclasses import dataclass, field
from typing import Protocol

from pinecone import (
    DenseVectorField,
    IndexModel,
    IndexSchema,
    IndexStatus,
    PineconeException,
    QueryResponse,
    ScoredVector,
    UpsertResponse,
    Vector,
)

from ._store_validation import (
    StoreConfig,
    prepare,
    query_vector,
    records_map,
    results,
)
from .errors import PineconeOperationError, RetrievalError
from .retrieval import IndexedChunk, SearchQuery, SearchResults


class PineconeIndexBoundary(Protocol):
    """Structural seam matching the genuine synchronous SDK data-plane calls."""

    def upsert(
        self, *, vectors: list[Vector], namespace: str, timeout: float
    ) -> UpsertResponse:
        """Upsert explicit SDK vectors into an application-selected namespace."""
        ...

    def query(
        self,
        *,
        vector: list[float],
        top_k: int,
        namespace: str,
        include_values: bool,
        include_metadata: bool,
        timeout: float,
    ) -> QueryResponse:
        """Query vectors without fetching document text or external metadata."""
        ...


class PineconeClientBoundary(Protocol):
    """Application-owned synchronous Pinecone client or explicit offline double."""

    def describe_index(self, name: str) -> IndexModel:
        """Read index configuration without creating or deleting indexes."""
        ...

    def Index(self, name: str) -> PineconeIndexBoundary:
        """Bind the data plane to the configured existing index name."""
        ...


@dataclass(frozen=True, slots=True)
class PineconeIndexConfig(StoreConfig):
    """Explicit existing index/namespace selection; no credentials retained.

    Args:
        dimension: Expected dense dimension.
        metric: cosine or euclidean, verified against describe_index.
        index_name: Existing index name; no provisioning occurs.
        namespace: Dedicated application corpus namespace, mandatory and nonempty.
        timeout_seconds: Finite request deadline, 0 < timeout <= 120.

    Raises:
        RetrievalError: For invalid settings.
    """

    index_name: str = field(default="story6", repr=False)
    namespace: str = field(default="story6", repr=False)
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        """Validate bounded configuration before any client call."""
        StoreConfig.__post_init__(self)
        for value in (self.index_name, self.namespace):
            if (
                type(value) is not str
                or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,44}", value) is None
            ):
                raise RetrievalError(
                    "Use bounded lowercase index/namespace identifiers."
                )
        if (
            type(self.timeout_seconds) not in (int, float)
            or not 0 < self.timeout_seconds <= 120
        ):
            raise RetrievalError("Use a finite timeout from above zero to 120 seconds.")


class PineconeVectorIndex:
    """Translate existing retrieval contracts into genuine SDK request objects."""

    def __init__(
        self,
        records: tuple[IndexedChunk, ...],
        config: PineconeIndexConfig,
        client: PineconeClientBoundary,
    ) -> None:
        """Validate corpus and remote configuration, then upsert bounded batches.

        Args:
            records: Unique application records; their source objects stay local.
            config: Existing index and dedicated namespace configuration.
            client: Application-owned SDK client or explicit offline double.

        Raises:
            RetrievalError: For invalid inputs or incompatible remote index.
            PineconeOperationError: For SDK failures or malformed acknowledgements.
        """
        if type(config) is not PineconeIndexConfig:
            raise RetrievalError("Supply a validated PineconeIndexConfig.")
        mapping = records_map(records, config)
        try:
            description = client.describe_index(config.index_name)
        except PineconeException:
            raise PineconeOperationError(
                "Pinecone description failed; verify access and index availability."
            ) from None
        if (
            type(description) is not IndexModel
            or type(description.schema) is not IndexSchema
            or type(description.status) is not IndexStatus
        ):
            raise PineconeOperationError(
                "Pinecone returned malformed index configuration."
            )
        fields = list(description.schema.fields.values())
        if (
            description.name != config.index_name
            or description.status.ready is not True
            or len(fields) != 1
            or type(fields[0]) is not DenseVectorField
            or type(fields[0].dimension) is not int
            or fields[0].dimension != config.dimension
            or fields[0].metric != config.metric
        ):
            raise RetrievalError(
                "Select a ready dense index with matching dimension/metric."
            )
        try:
            index = client.Index(config.index_name)
            # Conservative JSON float/ID budget stays below the 2 MB limit.
            batch_size = min(100, 1_000_000 // (config.dimension * 25 + 500))
            for offset in range(0, len(records), batch_size):
                batch = records[offset : offset + batch_size]
                acknowledgement = index.upsert(
                    vectors=[
                        Vector(
                            id=r.chunk_id,
                            values=prepare(r.vector, config),
                            metadata={"document_id": r.document_id},
                        )
                        for r in batch
                    ],
                    namespace=config.namespace,
                    timeout=config.timeout_seconds,
                )
                if (
                    type(acknowledgement) is not UpsertResponse
                    or type(acknowledgement.upserted_count) is not int
                    or acknowledgement.upserted_count != len(batch)
                ):
                    raise PineconeOperationError(
                        "Pinecone did not acknowledge the batch; verify writes."
                    )
        except PineconeException:
            raise PineconeOperationError(
                "Pinecone upsert failed; verify access and write state."
            ) from None
        self._index, self._records, self._config = index, mapping, config

    @property
    def dimension(self) -> int:
        """Return expected coordinate count."""
        return self._config.dimension

    @property
    def size(self) -> int:
        """Return local registry count, not a claim about remote namespace size."""
        return len(self._records)

    def search(self, query: SearchQuery) -> SearchResults:
        """Query and validate SDK matches before application record lookup.

        Args:
            query: Validated query with matching vector dimension.

        Returns:
            Deterministically ordered provider-neutral candidate results.

        Raises:
            RetrievalError: For invalid query.
            PineconeOperationError: For SDK failures or untrusted response violations.
        """
        vector = query_vector(query, self._config)
        try:
            response = self._index.query(
                vector=vector,
                top_k=min(query.top_k, self.size),
                namespace=self._config.namespace,
                include_values=False,
                include_metadata=False,
                timeout=self._config.timeout_seconds,
            )
        except PineconeException:
            raise PineconeOperationError(
                "Pinecone query failed; verify access and index availability."
            ) from None
        if (
            type(response) is not QueryResponse
            or response.namespace != self._config.namespace
            or type(response.matches) is not list
            or any(type(m) is not ScoredVector for m in response.matches)
        ):
            raise PineconeOperationError(
                "Pinecone returned malformed matches or namespace."
            )
        for match in response.matches:
            # Values are not requested. If supplied unexpectedly, validate them.
            if type(match.values) is not list:
                raise PineconeOperationError(
                    "Pinecone returned malformed vector values."
                )
            if match.values:
                from .errors import VectorError
                from .vectors import Vector as ApplicationVector

                try:
                    value = ApplicationVector(tuple(match.values))
                except VectorError:
                    raise PineconeOperationError(
                        "Pinecone returned invalid vector values."
                    ) from None
                if value.dimension != self.dimension:
                    raise PineconeOperationError(
                        "Pinecone returned a mismatched dimension."
                    )
        return results(
            [(m.id, m.score) for m in response.matches],
            self._records,
            query,
            self._config.metric,
            PineconeOperationError,
        )
