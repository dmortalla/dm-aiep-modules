"""Bounded plain-text ingestion; content remains data, never instructions.

Source keys are caller-declared opaque references, not verified origins or file
paths. Only their digests are retained. Caller metadata is immutable, untrusted,
and separate from derived provenance. No SDK, filesystem, or network is used.
"""

import hashlib
from dataclasses import InitVar, dataclass, field

from .errors import IngestionError, UnsupportedInputError

MAX_CONTENT_BYTES = 1_048_576
MAX_METADATA_ENTRIES = 32


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_text(value: str, *, maximum: int, label: str) -> bytes:
    if type(value) is not str or not value.strip():
        raise IngestionError(f"Supply a nonempty string for {label}.")
    if len(value) > maximum:
        raise IngestionError(f"Reduce {label} to at most {maximum} UTF-8 bytes.")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        raise IngestionError(f"Supply valid Unicode text for {label}.") from None
    if len(encoded) > maximum:
        raise IngestionError(f"Reduce {label} to at most {maximum} UTF-8 bytes.")
    if any(ord(char) < 32 and char not in "\t\n\r" for char in value):
        raise IngestionError(f"Remove unsupported control characters from {label}.")
    return encoded


@dataclass(frozen=True, slots=True)
class MetadataEntry:
    """One untrusted text attribute; keys never select application behavior.

    Args:
        key: Nonempty Unicode key, at most 128 UTF-8 bytes.
        value: Nonempty Unicode value, at most 2,048 UTF-8 bytes.

    Raises:
        IngestionError: If a field is malformed or exceeds its byte limit.
    """

    key: str
    value: str = field(repr=False)

    def __post_init__(self) -> None:
        """Validate immutable metadata without including input in errors."""
        _validate_text(self.key, maximum=128, label="metadata key")
        _validate_text(self.value, maximum=2_048, label="metadata value")


@dataclass(frozen=True, slots=True)
class DocumentProvenance:
    """Derived evidence, assigned by ingestion; never authorization.

    Attributes:
        source_id: SHA-256 of the declared source key; not origin authentication.
        content_sha256: SHA-256 of the exact UTF-8 content.
        document_id: Versioned digest combining source identity and content.
        media_type: The supported text/plain format.
        utf8_bytes: Exact encoded length.
        characters: Unicode code-point count, not tokens.
        lines: Python splitlines count, including internal blank lines.

    Raises:
        IngestionError: If hashes, format, counts, or derived identity are invalid.
    """

    source_id: str
    content_sha256: str
    document_id: str
    media_type: str
    utf8_bytes: int
    characters: int
    lines: int

    def __post_init__(self) -> None:
        """Validate structural evidence; this does not authenticate a source."""
        for digest in (self.source_id, self.content_sha256):
            if (
                type(digest) is not str
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
            ):
                raise IngestionError("Supply lowercase SHA-256 provenance hashes.")
        expected = "doc-v1-" + _digest(
            f"text/plain\0{self.source_id}\0{self.content_sha256}".encode("ascii")
        )
        if self.document_id != expected or self.media_type != "text/plain":
            raise IngestionError("Use derived document identity and text/plain format.")
        counts = (self.utf8_bytes, self.characters, self.lines)
        if any(type(count) is not int or count < 1 for count in counts):
            raise IngestionError("Supply positive integer provenance counts.")
        if not self.lines <= self.characters <= self.utf8_bytes <= MAX_CONTENT_BYTES:
            raise IngestionError("Supply consistent bounded provenance counts.")


@dataclass(frozen=True, slots=True)
class IngestedDocument:
    """Validated text with immutable metadata and derived provenance.

    Content is preserved verbatim, including whitespace and instruction-like
    text. Validation establishes structural suitability, not trust in meaning.
    The source key is used during construction and is not retained. Same source
    and exact content produce the same ID; metadata does not affect identity.

    Args:
        content: Nonblank valid text, at most MAX_CONTENT_BYTES UTF-8 bytes.
        source_key: Declared source reference, at most 1,024 UTF-8 bytes.
        user_metadata: Tuple of up to 32 MetadataEntry objects with unique keys.

    Attributes:
        provenance: Application-derived hashes and content statistics.

    Raises:
        IngestionError: If content, source key, or metadata is invalid.
    """

    content: str = field(repr=False)
    source_key: InitVar[str]
    user_metadata: tuple[MetadataEntry, ...] = field(default=(), repr=False)
    provenance: DocumentProvenance = field(init=False)

    def __post_init__(self, source_key: str) -> None:
        """Validate inputs and derive provenance without promoting metadata.

        Args:
            source_key: Caller-declared opaque source reference.

        Raises:
            IngestionError: If strict field types, limits, or uniqueness fail.
        """
        encoded = _validate_text(
            self.content, maximum=MAX_CONTENT_BYTES, label="document content"
        )
        source = _validate_text(source_key, maximum=1_024, label="source key")
        if (
            type(self.user_metadata) is not tuple
            or len(self.user_metadata) > MAX_METADATA_ENTRIES
            or any(type(entry) is not MetadataEntry for entry in self.user_metadata)
        ):
            raise IngestionError("Supply a tuple of at most 32 MetadataEntry objects.")
        keys = [entry.key for entry in self.user_metadata]
        if len(set(keys)) != len(keys):
            raise IngestionError("Supply unique metadata keys.")
        source_id = _digest(source)
        content_hash = _digest(encoded)
        document_id = "doc-v1-" + _digest(
            f"text/plain\0{source_id}\0{content_hash}".encode("ascii")
        )
        provenance = DocumentProvenance(
            source_id=source_id,
            content_sha256=content_hash,
            document_id=document_id,
            media_type="text/plain",
            utf8_bytes=len(encoded),
            characters=len(self.content),
            lines=len(self.content.splitlines()),
        )
        object.__setattr__(self, "provenance", provenance)


def ingest_text(
    content: str, *, source_key: str, metadata: tuple[MetadataEntry, ...] = ()
) -> IngestedDocument:
    """Ingest literal text without executing or interpreting its meaning.

    Args:
        content: Exact text to preserve.
        source_key: Declared reference used for reproducible source identity.
        metadata: Untrusted text attributes, kept apart from derived provenance.

    Returns:
        Validated immutable document suitable for later chunk processing.

    Raises:
        IngestionError: If content, reference, or metadata is malformed.
    """
    return IngestedDocument(content, source_key, metadata)


def ingest_bytes(
    content: bytes,
    *,
    source_key: str,
    media_type: str = "text/plain",
    metadata: tuple[MetadataEntry, ...] = (),
) -> IngestedDocument:
    """Decode bounded UTF-8 plain text and pass it through document validation.

    No encoding guessing, replacement decoding, BOM removal, or normalization
    occurs. A supplied media type is a declaration, not format authentication.

    Args:
        content: Exact bytes, at most MAX_CONTENT_BYTES.
        source_key: Caller-declared source reference; never opened as a path.
        media_type: Exactly text/plain; other formats are deliberately unsupported.
        metadata: Untrusted immutable text attributes.

    Returns:
        Document retaining the exact decoded Unicode text.

    Raises:
        UnsupportedInputError: If the type or declared format is unsupported.
        IngestionError: If decoding, content, source, or metadata validation fails.
    """
    if type(content) is not bytes or type(media_type) is not str:
        raise UnsupportedInputError("Supply bytes and the text/plain media type.")
    if media_type != "text/plain":
        raise UnsupportedInputError("Use text/plain; other formats are unsupported.")
    if len(content) > MAX_CONTENT_BYTES:
        raise IngestionError("Reduce document content to at most 1048576 UTF-8 bytes.")
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise IngestionError("Encode document content as valid UTF-8.") from None
    return ingest_text(text, source_key=source_key, metadata=metadata)
