"""Module-4-owned semantic retrieval: embeddings, ChromaDB, and Pinecone.

This is the semantic leg of Module 4's hybrid retrieval (M4-RET-02). It owns
only what that leg needs:

* an ``Embedder`` boundary and a validated ``EmbeddingBatch`` contract;
* ``HashEmbedder``, a deterministic, credential-free feature-hashing embedder
  for tests and demonstrations (it is not a learned semantic model);
* ``SemanticQuery``/``SemanticHit``/``SemanticResults`` evidence contracts;
* ``ChromaSemanticIndex``, the Module 4 semantic retrieval implementation,
  run against a genuine local, ephemeral ChromaDB collection;
* ``PineconeSemanticIndex``, the Module 4 Pinecone integration boundary, which
  speaks the installed Pinecone SDK's value types through an injected index
  client so deterministic tests never need credentials or network access.

Scores are cosine similarities (higher is better) for both backends. Results
from either backend are validated before they are trusted: every returned
identifier must name a chunk this index was built from, every score must be
finite and inside the cosine range, and ordering is recomputed locally with a
deterministic ``chunk_id`` tie-break rather than taken from the provider.
Returned chunks are this application's own ``CorpusChunk`` objects, looked up
by identifier, so provenance never comes from a provider payload.

Provider failures become ``SemanticProviderError`` with a fixed message and
no chained provider exception, so credentials, hosts, or response payloads
cannot leak through error text. Chunk content is inert data throughout.
Importing this module loads neither ChromaDB nor Pinecone; each backend is
imported only when that backend is explicitly constructed.
"""

import hashlib
import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from .bm25 import tokenize
from .corpus import MAX_CHUNK_BYTES, CorpusChunk
from .errors import (
    SemanticConfigurationError,
    SemanticProviderError,
    SemanticQueryError,
)

type Backend = Literal["chromadb", "pinecone"]

MAX_TOP_K = 10_000
MAX_BATCH = 10_000
MAX_QUERY_BYTES = 32_768
MIN_DIMENSION = 8
MAX_DIMENSION = 4_096
_SCORE_TOLERANCE = 1e-5
_CHROMA_ADD_BATCH = 1_000
_PINECONE_UPSERT_BATCH = 100


def _validate_text(value: str, label: str, limit: int) -> None:
    """Require nonblank, valid, bounded Unicode text without rewriting it."""
    if type(value) is not str or not value.strip():
        raise SemanticQueryError(f"Supply nonblank {label}.")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise SemanticQueryError(f"Supply valid Unicode {label}.") from exc
    if size > limit:
        raise SemanticQueryError(f"Limit {label} to {limit} UTF-8 bytes.")


def validate_texts(texts: tuple[str, ...]) -> None:
    """Validate one embedding request: 1..MAX_BATCH bounded nonblank strings."""
    if type(texts) is not tuple or not 1 <= len(texts) <= MAX_BATCH:
        raise SemanticQueryError(f"Embed a tuple of 1..{MAX_BATCH} texts.")
    for text in texts:
        _validate_text(text, "embedding text", MAX_CHUNK_BYTES)


@dataclass(frozen=True, slots=True)
class EmbeddingBatch:
    """Ordered embedding vectors, one per input text, all one dimension.

    Args:
        vectors: Nonempty tuple of float tuples, each exactly ``dimension``
            finite values.
        dimension: Vector width, 8..4096.

    Raises:
        SemanticQueryError: For malformed, ragged, or nonfinite vectors.
    """

    vectors: tuple[tuple[float, ...], ...]
    dimension: int

    def __post_init__(self) -> None:
        """Validate shape and finiteness before any vector is used."""
        if (
            type(self.dimension) is not int
            or not MIN_DIMENSION <= self.dimension <= MAX_DIMENSION
        ):
            raise SemanticQueryError("Use an integer dimension from 8 to 4096.")
        if type(self.vectors) is not tuple or not 1 <= len(self.vectors) <= MAX_BATCH:
            raise SemanticQueryError(f"Return 1..{MAX_BATCH} embedding vectors.")
        for vector in self.vectors:
            if (
                type(vector) is not tuple
                or len(vector) != self.dimension
                or any(
                    type(value) is not float or not math.isfinite(value)
                    for value in vector
                )
            ):
                raise SemanticQueryError("Return finite floats of one dimension.")


class Embedder(Protocol):
    """Application-selected text-embedding boundary."""

    @property
    def dimension(self) -> int:
        """Return the fixed output vector width."""
        ...

    def embed(self, texts: tuple[str, ...]) -> EmbeddingBatch:
        """Return one vector per text, in input order."""
        ...


@dataclass(frozen=True, slots=True)
class HashEmbedder:
    """Deterministic, credential-free signed feature-hashing embedder.

    Each lowercase alphanumeric token (the same tokenization as BM25) is
    hashed with BLAKE2b into one of ``dimension`` buckets with a hash-derived
    sign; counts are summed and the vector is L2-normalized. Text with no
    alphanumeric token hashes its stripped form as a single feature, so every
    nonblank text yields a nonzero vector. Identical text always yields an
    identical vector. This measures token overlap, not learned meaning, and
    is labelled as such in evidence (``module-4-local-hash:<dimension>``).

    Args:
        dimension: Output width, 8..4096; default 64.

    Raises:
        SemanticConfigurationError: For an invalid dimension.
    """

    dimension: int = 64

    def __post_init__(self) -> None:
        """Validate the configured width."""
        if (
            type(self.dimension) is not int
            or not MIN_DIMENSION <= self.dimension <= MAX_DIMENSION
        ):
            raise SemanticConfigurationError("Use an integer dimension from 8 to 4096.")

    @property
    def embedding_id(self) -> str:
        """Return the truthful evidence label for this local embedder."""
        return f"module-4-local-hash:{self.dimension}"

    def _vector(self, text: str) -> tuple[float, ...]:
        """Hash one text's features into a normalized vector."""
        features = tokenize(text) or (text.strip(),)
        values = [0.0] * self.dimension
        for feature in features:
            digest = hashlib.blake2b(
                feature.encode("utf-8"), digest_size=8, person=b"m4-hash-embed"
            ).digest()
            number = int.from_bytes(digest, "big")
            values[number % self.dimension] += 1.0 if number >> 63 else -1.0
        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0.0:
            # Opposite-signed collisions cancelled exactly; fall back to a
            # fixed nonzero direction so cosine similarity stays defined.
            values[0], norm = 1.0, 1.0
        return tuple(value / norm for value in values)

    def embed(self, texts: tuple[str, ...]) -> EmbeddingBatch:
        """Embed validated texts deterministically, preserving input order.

        Raises:
            SemanticQueryError: For an empty, oversized, or blank text batch.
        """
        validate_texts(texts)
        return EmbeddingBatch(tuple(self._vector(t) for t in texts), self.dimension)


@dataclass(frozen=True, slots=True)
class SemanticQuery:
    """An application-issued semantic search request.

    Args:
        text: Nonblank query text, at most 32768 UTF-8 bytes; hidden from repr.
        top_k: Requested maximum ranked results, 1..10000.

    Raises:
        SemanticQueryError: For blank/oversized text or an out-of-range top_k.
    """

    text: str = field(repr=False)
    top_k: int = 10

    def __post_init__(self) -> None:
        """Validate query shape before any embedding or store call."""
        _validate_text(self.text, "query text", MAX_QUERY_BYTES)
        if (
            type(self.top_k) is not int
            or type(self.top_k) is bool
            or not 1 <= self.top_k <= MAX_TOP_K
        ):
            raise SemanticQueryError("Use an integer top_k from 1 to 10000.")


@dataclass(frozen=True, slots=True)
class SemanticHit:
    """One ranked semantic result; the chunk is this application's own object.

    Args:
        rank: Zero-based descending-similarity position.
        score: Finite cosine similarity, higher is better.
        chunk: Retrieved CorpusChunk, hidden from repr.

    Raises:
        SemanticQueryError: For a malformed rank, score, or chunk.
    """

    rank: int
    score: float
    chunk: CorpusChunk = field(repr=False)

    def __post_init__(self) -> None:
        """Validate rank/score shape without rendering retrieved content."""
        if type(self.rank) is not int or self.rank < 0:
            raise SemanticQueryError("Use a zero-based nonnegative integer rank.")
        if (
            type(self.score) is not float
            or not math.isfinite(self.score)
            or abs(self.score) > 1.0 + _SCORE_TOLERANCE
        ):
            raise SemanticQueryError("Use a finite cosine similarity score.")
        if type(self.chunk) is not CorpusChunk:
            raise SemanticQueryError("Supply a validated CorpusChunk.")

    @property
    def chunk_id(self) -> str:
        """Return the retrieved chunk's stable identifier."""
        return self.chunk.chunk_id

    @property
    def document_id(self) -> str:
        """Return the retrieved chunk's parent document identifier."""
        return self.chunk.provenance.document_id


@dataclass(frozen=True, slots=True)
class SemanticResults:
    """Validated complete ranked semantic outcome for one query.

    Args:
        hits: 1..query.top_k SemanticHit rows, contiguous ranks, nonincreasing
            score, unique chunk_id.
        query: Retained SemanticQuery evidence, hidden from repr.
        backend: Which Module 4 vector-store boundary produced the hits.

    Raises:
        SemanticQueryError: For wrong types, rank gaps, order violations, or
            duplicate chunks.
    """

    hits: tuple[SemanticHit, ...]
    query: SemanticQuery = field(repr=False)
    backend: Backend

    def __post_init__(self) -> None:
        """Re-validate ordering and identity uniqueness."""
        if type(self.query) is not SemanticQuery:
            raise SemanticQueryError("Supply a validated SemanticQuery.")
        if self.backend not in ("chromadb", "pinecone"):
            raise SemanticQueryError("Identify the chromadb or pinecone backend.")
        if (
            type(self.hits) is not tuple
            or not 1 <= len(self.hits) <= self.query.top_k
            or any(type(hit) is not SemanticHit for hit in self.hits)
        ):
            raise SemanticQueryError("Supply 1..top_k validated semantic hits.")
        previous: float | None = None
        for index, hit in enumerate(self.hits):
            if hit.rank != index:
                raise SemanticQueryError("Keep hit ranks contiguous from zero.")
            if previous is not None and hit.score > previous:
                raise SemanticQueryError("Keep hits sorted by nonincreasing score.")
            previous = hit.score
        if len({hit.chunk_id for hit in self.hits}) != len(self.hits):
            raise SemanticQueryError("Deduplicate semantic chunk_id values.")

    @property
    def higher_is_better(self) -> bool:
        """Cosine similarity: a larger score is always more relevant."""
        return True


def _corpus_by_id(chunks: tuple[CorpusChunk, ...]) -> dict[str, CorpusChunk]:
    """Validate an indexable corpus and key it by unique chunk_id."""
    if (
        type(chunks) is not tuple
        or not 1 <= len(chunks) <= MAX_BATCH
        or any(type(chunk) is not CorpusChunk for chunk in chunks)
    ):
        raise SemanticConfigurationError(
            f"Supply a tuple of 1..{MAX_BATCH} validated CorpusChunk objects."
        )
    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    if len(by_id) != len(chunks):
        raise SemanticConfigurationError("Index each chunk_id exactly once.")
    return by_id


def _embed(
    embedder: Embedder, texts: tuple[str, ...]
) -> tuple[tuple[float, ...], ...]:
    """Call the embedder and validate its output before it reaches a store."""
    batch = embedder.embed(texts)
    if (
        type(batch) is not EmbeddingBatch
        or len(batch.vectors) != len(texts)
        or batch.dimension != embedder.dimension
        or any(math.hypot(*vector) == 0.0 for vector in batch.vectors)
    ):
        raise SemanticQueryError("Return one nonzero vector per text, in order.")
    return batch.vectors


def _check_embedder(embedder: Embedder) -> None:
    """Require an application-selected embedder with a valid fixed width."""
    dimension = getattr(embedder, "dimension", None)
    if (
        not callable(getattr(embedder, "embed", None))
        or type(dimension) is not int
        or not MIN_DIMENSION <= dimension <= MAX_DIMENSION
    ):
        raise SemanticConfigurationError("Supply an embedder with a valid dimension.")


def _ranked(
    matches: list[tuple[Any, Any]],
    chunks_by_id: dict[str, CorpusChunk],
    query: SemanticQuery,
    backend: Backend,
) -> SemanticResults:
    """Validate untrusted (id, score) matches and rank them deterministically."""
    if not 1 <= len(matches) <= query.top_k:
        raise SemanticProviderError("The vector store returned no usable matches.")
    seen: set[str] = set()
    checked: list[tuple[float, str]] = []
    for chunk_id, score in matches:
        if type(chunk_id) is not str or chunk_id not in chunks_by_id:
            raise SemanticProviderError("The vector store returned an unknown id.")
        if chunk_id in seen:
            raise SemanticProviderError("The vector store returned a duplicate id.")
        if (
            type(score) not in (int, float)
            or type(score) is bool
            or not math.isfinite(score)
            or abs(score) > 1.0 + _SCORE_TOLERANCE
        ):
            raise SemanticProviderError("The vector store returned an invalid score.")
        seen.add(chunk_id)
        checked.append((float(score), chunk_id))
    checked.sort(key=lambda item: (-item[0], item[1]))
    hits = tuple(
        SemanticHit(rank, score, chunks_by_id[chunk_id])
        for rank, (score, chunk_id) in enumerate(checked)
    )
    return SemanticResults(hits, query, backend)


class ChromaSemanticIndex:
    """Module 4 semantic retrieval over a genuine ChromaDB collection.

    By default this opens an in-process ``chromadb.EphemeralClient`` with
    anonymized telemetry disabled and creates a uniquely named cosine-space
    collection. Vectors come from the application's embedder; ChromaDB's own
    default embedding function is never used, so no model is downloaded.
    Only chunk identifiers and vectors are stored; content stays local. The
    collection this object created is deleted by ``close`` (also on exiting
    a ``with`` block). Remote Chroma services are not exercised here.

    Args:
        chunks: Tuple of 1..10000 unique CorpusChunk objects.
        embedder: Application-selected Embedder.
        client: Optional preconfigured ChromaDB client; default is ephemeral.

    Raises:
        SemanticConfigurationError: For an invalid corpus or embedder.
        SemanticQueryError: For malformed embedder output.
        SemanticProviderError: If ChromaDB fails; provider detail is withheld.
    """

    __slots__ = ("_chunks", "_client", "_collection", "_embedder", "_name")

    def __init__(
        self,
        chunks: tuple[CorpusChunk, ...],
        embedder: Embedder,
        *,
        client: Any = None,
    ) -> None:
        """Embed the corpus and add it to a new ephemeral Chroma collection."""
        self._chunks = _corpus_by_id(chunks)
        _check_embedder(embedder)
        self._embedder = embedder
        vectors = _embed(embedder, tuple(chunk.content for chunk in chunks))
        self._name = f"m4-semantic-{uuid.uuid4().hex}"
        self._collection = None
        try:
            if client is None:
                import chromadb
                from chromadb.config import Settings

                client = chromadb.EphemeralClient(
                    settings=Settings(anonymized_telemetry=False)
                )
            self._client = client
            self._collection = client.create_collection(
                self._name,
                embedding_function=None,
                configuration={"hnsw": {"space": "cosine"}},
            )
            ids = [chunk.chunk_id for chunk in chunks]
            for start in range(0, len(ids), _CHROMA_ADD_BATCH):
                end = start + _CHROMA_ADD_BATCH
                self._collection.add(
                    ids=ids[start:end],
                    embeddings=[list(vector) for vector in vectors[start:end]],
                )
        except Exception:
            self.close()
            raise SemanticProviderError(
                "ChromaDB indexing failed; check the local Chroma runtime."
            ) from None

    @property
    def size(self) -> int:
        """Return the number of indexed chunks."""
        return len(self._chunks)

    @property
    def collection_name(self) -> str:
        """Return the generated name of the collection this index owns."""
        return self._name

    def search(self, query: SemanticQuery) -> SemanticResults:
        """Return validated, deterministically ordered cosine-similarity hits.

        Requesting more than the index holds returns every chunk, ranked.

        Raises:
            SemanticQueryError: For an invalid query or embedder output.
            SemanticConfigurationError: After ``close``.
            SemanticProviderError: For a ChromaDB failure or invalid response.
        """
        if type(query) is not SemanticQuery:
            raise SemanticQueryError("Supply a validated SemanticQuery.")
        if self._collection is None:
            raise SemanticConfigurationError("Search an open Chroma index.")
        vector = _embed(self._embedder, (query.text,))[0]
        try:
            response = self._collection.query(
                query_embeddings=[list(vector)],
                n_results=min(query.top_k, self.size),
                include=["distances"],
            )
            ids = response["ids"]
            distances = response["distances"]
        except Exception:
            raise SemanticProviderError(
                "ChromaDB query failed; check the local Chroma runtime."
            ) from None
        if (
            type(ids) is not list
            or type(distances) is not list
            or len(ids) != 1
            or len(distances) != 1
            or type(ids[0]) is not list
            or type(distances[0]) is not list
            or len(ids[0]) != len(distances[0])
        ):
            raise SemanticProviderError("ChromaDB returned a malformed response.")
        matches: list[tuple[Any, Any]] = []
        for chunk_id, distance in zip(ids[0], distances[0], strict=True):
            if type(distance) not in (int, float) or type(distance) is bool:
                raise SemanticProviderError("ChromaDB returned an invalid distance.")
            # Chroma's cosine space reports distance = 1 - cosine similarity.
            matches.append((chunk_id, 1.0 - float(distance)))
        return _ranked(matches, self._chunks, query, "chromadb")

    def close(self) -> None:
        """Delete the collection this index created; safe to call repeatedly."""
        collection, self._collection = self._collection, None
        if collection is not None:
            try:
                self._client.delete_collection(self._name)
            except Exception:
                pass

    def __enter__(self) -> "ChromaSemanticIndex":
        """Return this index for use in a ``with`` block."""
        return self

    def __exit__(self, *_exc: object) -> None:
        """Delete the owned collection on leaving a ``with`` block."""
        self.close()


class PineconeIndexClient(Protocol):
    """The two ``pinecone.Index`` operations this boundary uses."""

    def upsert(self, *, vectors: Any, namespace: str, show_progress: bool) -> Any:
        """Store vectors in one namespace."""
        ...

    def query(
        self,
        *,
        top_k: int,
        vector: list[float],
        namespace: str,
        include_values: bool,
        include_metadata: bool,
    ) -> Any:
        """Return a ``pinecone.QueryResponse`` for one dense vector."""
        ...


def connect_pinecone_index(*, api_key: str, host: str) -> PineconeIndexClient:
    """Open a real Pinecone SDK index handle from application configuration.

    Credentials and host come only from application configuration, never
    from retrieved content or provider responses. Constructing the handle
    does not contact Pinecone; the first upsert/query does.

    Raises:
        SemanticConfigurationError: For a blank key or a non-HTTPS host.
        SemanticProviderError: If the SDK rejects the configuration.
    """
    if type(api_key) is not str or not api_key.strip():
        raise SemanticConfigurationError("Supply a Pinecone API key.")
    if type(host) is not str or not host.startswith("https://"):
        raise SemanticConfigurationError("Supply an https:// Pinecone index host.")
    try:
        from pinecone import Pinecone

        return Pinecone(api_key=api_key).Index(host=host)
    except Exception:
        raise SemanticProviderError(
            "Pinecone client setup failed; check SDK configuration."
        ) from None


class PineconeSemanticIndex:
    """Module 4 Pinecone semantic-retrieval boundary over an injected index.

    The index client is injected, so deterministic tests supply an offline
    double that accepts and returns the installed Pinecone SDK's own
    ``Vector``/``QueryResponse``/``ScoredVector`` types, while production code
    passes a handle from ``connect_pinecone_index``. Only chunk identifiers
    and vectors are upserted; content and provenance stay local. The target
    Pinecone index must use the cosine metric with this embedder's dimension.

    Args:
        chunks: Tuple of 1..10000 unique CorpusChunk objects.
        embedder: Application-selected Embedder.
        client: Injected Pinecone index client.
        namespace: Application-owned namespace, nonblank, at most 256 bytes.

    Raises:
        SemanticConfigurationError: For an invalid corpus, embedder, client,
            or namespace.
        SemanticQueryError: For malformed embedder output.
        SemanticProviderError: If the upsert fails; provider detail withheld.
    """

    __slots__ = ("_chunks", "_client", "_embedder", "_namespace")

    def __init__(
        self,
        chunks: tuple[CorpusChunk, ...],
        embedder: Embedder,
        client: PineconeIndexClient,
        *,
        namespace: str = "module-4-semantic",
    ) -> None:
        """Embed the corpus and upsert identifier/vector pairs to Pinecone."""
        self._chunks = _corpus_by_id(chunks)
        _check_embedder(embedder)
        if not callable(getattr(client, "upsert", None)) or not callable(
            getattr(client, "query", None)
        ):
            raise SemanticConfigurationError("Supply a Pinecone index client.")
        if (
            type(namespace) is not str
            or not namespace.strip()
            or len(namespace.encode("utf-8", errors="replace")) > 256
        ):
            raise SemanticConfigurationError("Supply a nonblank bounded namespace.")
        self._embedder = embedder
        self._client = client
        self._namespace = namespace
        vectors = _embed(embedder, tuple(chunk.content for chunk in chunks))
        from pinecone import Vector

        records = [
            Vector(id=chunk.chunk_id, values=list(vector))
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        try:
            for start in range(0, len(records), _PINECONE_UPSERT_BATCH):
                client.upsert(
                    vectors=records[start : start + _PINECONE_UPSERT_BATCH],
                    namespace=namespace,
                    show_progress=False,
                )
        except Exception:
            raise SemanticProviderError(
                "Pinecone upsert failed; check index host, credentials, and quota."
            ) from None

    @property
    def size(self) -> int:
        """Return the number of chunks this boundary upserted."""
        return len(self._chunks)

    @property
    def namespace(self) -> str:
        """Return the application-owned namespace."""
        return self._namespace

    def search(self, query: SemanticQuery) -> SemanticResults:
        """Query Pinecone and validate its response before trusting it.

        Raises:
            SemanticQueryError: For an invalid query or embedder output.
            SemanticProviderError: For a Pinecone failure or invalid response.
        """
        if type(query) is not SemanticQuery:
            raise SemanticQueryError("Supply a validated SemanticQuery.")
        vector = _embed(self._embedder, (query.text,))[0]
        from pinecone import QueryResponse, ScoredVector

        try:
            response = self._client.query(
                top_k=min(query.top_k, self.size),
                vector=list(vector),
                namespace=self._namespace,
                include_values=False,
                include_metadata=False,
            )
        except Exception:
            raise SemanticProviderError(
                "Pinecone query failed; check index host, credentials, and quota."
            ) from None
        if (
            type(response) is not QueryResponse
            or type(response.matches) is not list
            or any(type(match) is not ScoredVector for match in response.matches)
        ):
            raise SemanticProviderError("Pinecone returned a malformed response.")
        return _ranked(
            [(match.id, match.score) for match in response.matches],
            self._chunks,
            query,
            "pinecone",
        )
