"""Minimal Module 4 corpus contract: immutable chunks with stable provenance.

Module 4 retrieves, fuses, reranks, filters, caches, and evaluates chunks; it
does not ingest or split documents. This module therefore owns only what
those stages need from a chunk: a stable ``chunk_id`` for fusion and caching,
the parent ``document_id``/``source_id`` provenance carried into evidence, a
zero-based position, and the inert text content. It is deliberately not an
ingestion or chunking subsystem: ``build_corpus`` accepts passages the
application has already split and only assigns identity and provenance.

Chunk content is untrusted data. Nothing here parses, executes, or renders
it, and content is hidden from ``repr`` so evidence objects never echo it.
"""

import hashlib
from dataclasses import dataclass, field

from .errors import CorpusError

MAX_ID_BYTES = 256
MAX_CHUNK_BYTES = 1_048_576
MAX_PASSAGES = 10_000


def _identifier(value: str, label: str) -> None:
    """Validate a nonblank, bounded identifier string."""
    if type(value) is not str or not value.strip():
        raise CorpusError(f"Supply a nonblank {label} string.")
    if len(value.encode("utf-8", errors="replace")) > MAX_ID_BYTES:
        raise CorpusError(f"Limit {label} to {MAX_ID_BYTES} UTF-8 bytes.")


@dataclass(frozen=True, slots=True)
class ChunkProvenance:
    """Where a chunk came from; retained unchanged into every evidence object.

    Args:
        source_id: Application-supplied source key, at most 256 UTF-8 bytes.
        document_id: Stable parent-document identifier, at most 256 bytes.

    Raises:
        CorpusError: For blank, non-string, or oversized identifiers.
    """

    source_id: str
    document_id: str

    def __post_init__(self) -> None:
        """Validate provenance identifiers."""
        _identifier(self.source_id, "source_id")
        _identifier(self.document_id, "document_id")


@dataclass(frozen=True, slots=True)
class CorpusChunk:
    """One immutable, retrievable Module 4 chunk.

    Args:
        chunk_id: Stable unique identifier used for fusion and caching.
        index: Zero-based position of the chunk within its document.
        content: Nonblank text, at most 1 MiB UTF-8; untrusted, hidden from repr.
        provenance: Validated ChunkProvenance.

    Raises:
        CorpusError: For malformed identity, position, content, or provenance.
    """

    chunk_id: str
    index: int
    content: str = field(repr=False)
    provenance: ChunkProvenance

    def __post_init__(self) -> None:
        """Validate identity, position, bounded content, and provenance."""
        _identifier(self.chunk_id, "chunk_id")
        if type(self.index) is not int or self.index < 0:
            raise CorpusError("Use a zero-based nonnegative integer chunk index.")
        if type(self.content) is not str or not self.content.strip():
            raise CorpusError("Supply nonblank chunk content.")
        try:
            size = len(self.content.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise CorpusError("Supply valid Unicode chunk content.") from exc
        if size > MAX_CHUNK_BYTES:
            raise CorpusError(f"Limit chunk content to {MAX_CHUNK_BYTES} UTF-8 bytes.")
        if type(self.provenance) is not ChunkProvenance:
            raise CorpusError("Supply validated ChunkProvenance.")


def build_corpus(source_id: str, passages: tuple[str, ...]) -> tuple[CorpusChunk, ...]:
    """Assign deterministic identity and provenance to pre-split passages.

    The document identifier is a SHA-256 digest of the source key and the
    ordered passages, so identical input always yields identical identifiers
    and different sources never share a document_id. Each passage becomes
    exactly one chunk; no splitting, merging, or rewriting is performed.

    Args:
        source_id: Application-supplied source key.
        passages: Ordered tuple of 1..10000 nonblank passage strings.

    Returns:
        Ordered tuple of CorpusChunk objects sharing one ChunkProvenance.

    Raises:
        CorpusError: For an invalid source key or passage tuple.
    """
    _identifier(source_id, "source_id")
    if (
        type(passages) is not tuple
        or not 1 <= len(passages) <= MAX_PASSAGES
        or any(type(passage) is not str for passage in passages)
    ):
        raise CorpusError(f"Supply a tuple of 1..{MAX_PASSAGES} passage strings.")
    digest = hashlib.sha256(source_id.encode("utf-8", errors="replace"))
    for passage in passages:
        digest.update(b"\x00")
        digest.update(passage.encode("utf-8", errors="replace"))
    provenance = ChunkProvenance(source_id, f"m4doc-{digest.hexdigest()[:16]}")
    return tuple(
        CorpusChunk(f"{provenance.document_id}-{index:05d}", index, text, provenance)
        for index, text in enumerate(passages)
    )
