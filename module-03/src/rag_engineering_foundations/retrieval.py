"""Provider-neutral retrieval contracts over Story 3 chunks and Story 4 vectors.

These contracts never import FAISS, ChromaDB, Pinecone, or any other store SDK;
concrete adapters (for example ``faiss_index.py``) depend on this module, not
the reverse. Retrieved content is evidence for the application to act on, not
authority: nothing here executes, imports, or otherwise acts on chunk content.
"""

import math
from dataclasses import dataclass, field
from typing import Protocol

from .chunking import DocumentChunk
from .embeddings import EmbeddingBatch
from .errors import RetrievalError
from .vectors import Vector

MAX_TOP_K = 10_000


@dataclass(frozen=True, slots=True)
class IndexedChunk:
    """One embedded chunk bound to its exact source chunk, never copying its text.

    Args:
        chunk: Accepted Story 3 DocumentChunk, retained by reference and hidden
            from repr; its content is reachable only through explicit access
            (``record.chunk.content``), never through default representations.
        vector: Validated Story 4 Vector produced for that chunk's content.

    Attributes:
        chunk_id: The source chunk's own derived stable identifier.
        document_id: The source chunk's parent document identifier.

    Raises:
        RetrievalError: If the chunk or vector is not an accepted validated type.
    """

    chunk: DocumentChunk = field(repr=False)
    vector: Vector = field(repr=False)

    def __post_init__(self) -> None:
        """Validate accepted types without inspecting or copying chunk content."""
        if type(self.chunk) is not DocumentChunk:
            raise RetrievalError("Supply an accepted Story 3 DocumentChunk.")
        if type(self.vector) is not Vector:
            raise RetrievalError("Supply a validated Story 4 Vector.")

    @property
    def chunk_id(self) -> str:
        """Return the source chunk's own stable identifier."""
        return self.chunk.chunk_id

    @property
    def document_id(self) -> str:
        """Return the source chunk's parent document identifier."""
        return self.chunk.provenance.document_id


def to_indexed_chunks(
    chunks: tuple[DocumentChunk, ...], batch: EmbeddingBatch
) -> tuple[IndexedChunk, ...]:
    """Pair Story 3 chunks with their Story 4 embedding batch, preserving order.

    This only combines two already-produced outputs; it does not ingest, chunk,
    or embed anything itself.

    Args:
        chunks: Ordered chunks whose exact content was embedded, in that order.
        batch: The embedding batch produced for exactly those chunks' content.

    Returns:
        One IndexedChunk per input chunk, in the same order.

    Raises:
        RetrievalError: If the chunk and vector counts do not match exactly.
    """
    if (
        type(chunks) is not tuple
        or type(batch) is not EmbeddingBatch
        or len(chunks) != len(batch.vectors)
    ):
        raise RetrievalError(
            "Pair each chunk with exactly one batch vector, in matching order."
        )
    return tuple(
        IndexedChunk(chunk, vector)
        for chunk, vector in zip(chunks, batch.vectors, strict=True)
    )


@dataclass(frozen=True, slots=True)
class SearchQuery:
    """An application-issued similarity search request against one index.

    Args:
        vector: Validated finite query Vector. Its own Vector contract already
            guarantees finite coordinates; the index checks its dimension.
        top_k: Requested maximum ranked results, 1..10000. Requesting more than
            the index holds is not an error; see VectorIndex.search.

    Raises:
        RetrievalError: For a non-Vector query or an out-of-range top_k.
    """

    vector: Vector = field(repr=False)
    top_k: int = 10

    def __post_init__(self) -> None:
        """Validate query shape; Vector's own contract guarantees finiteness."""
        if type(self.vector) is not Vector:
            raise RetrievalError("Supply a validated query Vector.")
        if type(self.top_k) is not int or not 1 <= self.top_k <= MAX_TOP_K:
            raise RetrievalError("Use an integer top_k from 1 to 10000.")


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One ranked retrieval result; the record is retained by reference.

    Rank 0 is the best match under the producing index's metric convention
    (highest similarity or lowest distance; see SearchResults.higher_is_better).
    Ranks are contiguous from zero within one SearchResults collection.

    Args:
        rank: Zero-based descending-relevance position.
        score: Finite metric value; sign/meaning depends on the index metric.
        record: Retrieved IndexedChunk; content is reachable only through
            ``hit.record.chunk``, never through this object's own repr.

    Raises:
        RetrievalError: For a malformed rank, nonfinite score, or wrong record type.
    """

    rank: int
    score: float
    record: IndexedChunk = field(repr=False)

    def __post_init__(self) -> None:
        """Validate rank/score shape without rendering retrieved content."""
        if type(self.rank) is not int or self.rank < 0:
            raise RetrievalError("Use a zero-based nonnegative integer rank.")
        if type(self.score) not in (int, float) or not math.isfinite(self.score):
            raise RetrievalError("Use a finite numeric relevance score.")
        if type(self.record) is not IndexedChunk:
            raise RetrievalError("Supply a validated IndexedChunk record.")

    @property
    def chunk_id(self) -> str:
        """Return the retrieved chunk's stable identifier."""
        return self.record.chunk_id

    @property
    def document_id(self) -> str:
        """Return the retrieved chunk's parent document identifier."""
        return self.record.document_id


@dataclass(frozen=True, slots=True)
class SearchResults:
    """Validated complete ranked outcome for one query against one index.

    Args:
        hits: Tuple of 1..query.top_k SearchHit objects, contiguous rank order.
        query: Retained SearchQuery evidence, hidden from repr.
        higher_is_better: True when rank 0 holds the highest score (similarity
            metrics such as cosine); False when rank 0 holds the lowest score
            (distance metrics such as Euclidean).

    Raises:
        RetrievalError: For wrong types, rank gaps, or score-direction violations.
    """

    hits: tuple[SearchHit, ...]
    query: SearchQuery = field(repr=False)
    higher_is_better: bool = True

    def __post_init__(self) -> None:
        """Re-validate rank contiguity and declared score-direction monotonicity.

        An index that already sorted hits correctly pays only this one cheap
        pass; a defective index cannot silently hand back misordered results.
        """
        if type(self.query) is not SearchQuery:
            raise RetrievalError("Supply a validated SearchQuery.")
        if type(self.higher_is_better) is not bool:
            raise RetrievalError("Use bool for higher_is_better.")
        if (
            type(self.hits) is not tuple
            or not 1 <= len(self.hits) <= self.query.top_k
            or any(type(hit) is not SearchHit for hit in self.hits)
        ):
            raise RetrievalError("Supply 1..top_k validated ranked hits.")
        previous: float | None = None
        for index, hit in enumerate(self.hits):
            if hit.rank != index:
                raise RetrievalError("Keep hit ranks contiguous from zero.")
            if previous is not None:
                worse = (
                    hit.score > previous
                    if self.higher_is_better
                    else hit.score < previous
                )
                if worse:
                    raise RetrievalError(
                        "Keep hits sorted by the declared score direction."
                    )
            previous = hit.score


class VectorIndex(Protocol):
    """Provider-neutral build/search boundary; FAISS is one concrete adapter.

    A later story's ChromaDB or Pinecone adapter can implement this same
    structural protocol without changing these retrieval contracts.
    """

    @property
    def dimension(self) -> int:
        """Return the coordinate count every indexed/query vector must match."""
        ...

    @property
    def size(self) -> int:
        """Return the number of indexed records."""
        ...

    def search(self, query: SearchQuery) -> SearchResults:
        """Return deterministic ranked hits for one validated query.

        Args:
            query: Validated SearchQuery matching this index's dimension.

        Returns:
            Complete ranked SearchResults.

        Raises:
            RetrievalError: For invalid query shape or a dimension mismatch.
        """
        ...
