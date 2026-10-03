"""Exact, offline-capable chunking over accepted immutable ingestion contracts.

Sizes and half-open offsets count Python Unicode code points, not UTF-8 bytes,
graphemes, or tokens. Separators/whitespace remain in the original slices.
Document content and metadata are data, never configuration or authority.
"""

import hashlib
import math
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Literal, Protocol

from .errors import ChunkingError, SemanticSignalError
from .ingestion import (
    MAX_CONTENT_BYTES,
    DocumentProvenance,
    IngestedDocument,
    MetadataEntry,
)

MAX_CHUNKS = 4_096
MAX_SEMANTIC_UNITS = 4_096
type Strategy = Literal["fixed", "recursive", "semantic"]


def _size(value: int) -> None:
    if type(value) is not int or not 1 <= value <= MAX_CONTENT_BYTES:
        raise ChunkingError("Use a character size between 1 and 1048576.")


def _document(document: IngestedDocument) -> None:
    if type(document) is not IngestedDocument:
        raise ChunkingError("Supply an accepted IngestedDocument, not raw source data.")


def _score(value: float) -> None:
    if type(value) not in (int, float) or not 0 <= value <= 1:
        raise SemanticSignalError("Return a finite numeric similarity from 0 to 1.")


@dataclass(frozen=True, slots=True)
class FixedConfig:
    """Application-owned fixed window settings in Unicode characters.

    Args:
        size: Maximum window length, 1..1048576; default 1000.
        overlap: Repeated characters between windows, 0 <= overlap < size.

    Raises:
        ChunkingError: For noninteger or inconsistent settings (including bool).
    """

    size: int = 1_000
    overlap: int = 0

    def __post_init__(self) -> None:
        """Validate progress and size bounds."""
        _size(self.size)
        if type(self.overlap) is not int or not 0 <= self.overlap < self.size:
            raise ChunkingError("Use integer overlap from zero to size minus one.")


@dataclass(frozen=True, slots=True)
class RecursiveConfig:
    """Application-owned hierarchy from strongest to weakest literal separator.

    Args:
        size: Maximum chunk length in Unicode characters; default 1000.
        separators: One to eight unique nonempty separators, each <=32 characters.
            Defaults prefer paragraphs, lines, then spaces; all remain in content.

    Raises:
        ChunkingError: For invalid size or separator hierarchy.
    """

    size: int = 1_000
    separators: tuple[str, ...] = field(default=("\n\n", "\n", " "), repr=False)

    def __post_init__(self) -> None:
        """Validate a bounded literal hierarchy without rendering separators."""
        _size(self.size)
        if (
            type(self.separators) is not tuple
            or not 1 <= len(self.separators) <= 8
            or any(type(s) is not str or not 1 <= len(s) <= 32 for s in self.separators)
            or len(set(self.separators)) != len(self.separators)
        ):
            raise ChunkingError("Supply 1..8 unique nonempty literal separators.")


@dataclass(frozen=True, slots=True)
class SemanticConfig:
    """Semantic grouping threshold and hard character ceiling, with no overlap.

    Args:
        size: Maximum chunk length in Unicode characters; default 1000.
        threshold: Similarity below this value starts a new group; equality joins.
            Finite number in [0, 1]; default 0.5.

    Raises:
        ChunkingError: For invalid size or threshold.
    """

    size: int = 1_000
    threshold: float = 0.5

    def __post_init__(self) -> None:
        """Validate size and threshold before invoking any semantic callback."""
        _size(self.size)
        _score(self.threshold)


class SemanticSignal(Protocol):
    """Application-selected adjacent-unit meaning/similarity boundary.

    Implementations must be deterministic for reproducible output. They receive
    untrusted source text, not instructions or credentials. The chunker supplies
    no providers; later embeddings can implement this protocol independently.
    """

    def __call__(self, left: str, right: str) -> float:
        """Measure semantic similarity of two adjacent exact text units.

        Args:
            left: Original unit on the left, including its separators.
            right: Original unit on the right, including its separators.

        Returns:
            Finite similarity in [0, 1], higher meaning more related.

        Raises:
            Exception: Implementation-specific failures translated at the boundary.
        """
        ...


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    """Immutable exact slice of an ingested document with derived identity.

    Args:
        document: Accepted parent; retained by reference, hidden from repr.
        index: Zero-based ordering within the produced result, 0..4095.
        start: Inclusive Unicode character offset in original content.
        end: Exclusive Unicode character offset; must exceed start.
        strategy: Fixed, recursive, or semantic application-selected strategy.

    Attributes:
        chunk_id: Derived versioned digest of document ID, strategy, index, offsets.

    Raises:
        ChunkingError: For invalid document, strategy, ordering, or offsets.
    """

    document: IngestedDocument = field(repr=False)
    index: int
    start: int
    end: int
    strategy: Strategy
    chunk_id: str = field(init=False)

    def __post_init__(self) -> None:
        """Validate offsets then derive identity without searching for content."""
        _document(self.document)
        if type(self.index) is not int or not 0 <= self.index < MAX_CHUNKS:
            raise ChunkingError("Use a zero-based chunk index below 4096.")
        if (
            type(self.start) is not int
            or type(self.end) is not int
            or not 0 <= self.start < self.end <= len(self.document.content)
        ):
            raise ChunkingError("Use nonempty character offsets within the document.")
        if type(self.strategy) is not str or self.strategy not in (
            "fixed",
            "recursive",
            "semantic",
        ):
            raise ChunkingError("Select fixed, recursive, or semantic chunking.")
        identity = (
            f"{self.document.provenance.document_id}\0{self.strategy}\0"
            f"{self.index}\0{self.start}\0{self.end}"
        )
        object.__setattr__(
            self,
            "chunk_id",
            "chunk-v1-" + hashlib.sha256(identity.encode()).hexdigest(),
        )

    @property
    def content(self) -> str:
        """Return the exact original slice, including whitespace and separators."""
        return self.document.content[self.start : self.end]

    @property
    def provenance(self) -> DocumentProvenance:
        """Return inherited application-derived document evidence, never authority."""
        return self.document.provenance

    @property
    def user_metadata(self) -> tuple[MetadataEntry, ...]:
        """Return inherited untrusted metadata without merging it into provenance."""
        return self.document.user_metadata


@dataclass(frozen=True, slots=True)
class SemanticEvidence:
    """Inspectable similarity at a candidate boundary in original character units.

    Args:
        offset: Start of the right-hand adjacent unit, positive and bounded.
        similarity: Finite callback score in [0, 1].

    Raises:
        ChunkingError: For malformed offset or similarity.
    """

    offset: int
    similarity: float

    def __post_init__(self) -> None:
        """Reject malformed callback evidence without rendering its value."""
        if type(self.offset) is not int or not 0 < self.offset < MAX_CONTENT_BYTES:
            raise ChunkingError("Use a bounded positive semantic boundary offset.")
        _score(self.similarity)


@dataclass(frozen=True, slots=True)
class ChunkingResult:
    """Validated complete coverage in source order with optional semantic evidence.

    Args:
        chunks: One to 4096 chunks, same parent object/strategy, contiguous indices.
            Fixed chunks may overlap; recursive/semantic chunks partition the text.
        semantic_evidence: Ordered adjacent-unit scores, only for semantic results.

    Raises:
        ChunkingError: For gaps, mismatched parents, invalid order, or evidence.
    """

    chunks: tuple[DocumentChunk, ...]
    semantic_evidence: tuple[SemanticEvidence, ...] = ()

    def __post_init__(self) -> None:
        """Check source coverage, progress, and evidence bounds."""
        if (
            type(self.chunks) is not tuple
            or not 1 <= len(self.chunks) <= MAX_CHUNKS
            or any(type(chunk) is not DocumentChunk for chunk in self.chunks)
        ):
            raise ChunkingError("Supply a tuple of 1..4096 validated chunks.")
        first = self.chunks[0]
        previous: DocumentChunk | None = None
        for index, chunk in enumerate(self.chunks):
            if (
                chunk.document is not first.document
                or chunk.strategy != first.strategy
                or chunk.index != index
            ):
                raise ChunkingError(
                    "Keep one parent, one strategy, and ordered indices."
                )
            if previous is not None and (
                chunk.start <= previous.start
                or chunk.end <= previous.end
                or chunk.start > previous.end
                or (first.strategy != "fixed" and chunk.start != previous.end)
            ):
                raise ChunkingError(
                    "Preserve source order and complete gap-free coverage."
                )
            previous = chunk
        if first.start != 0 or self.chunks[-1].end != len(first.document.content):
            raise ChunkingError(
                "Cover the entire original document, including its edges."
            )
        if (
            type(self.semantic_evidence) is not tuple
            or len(self.semantic_evidence) >= MAX_SEMANTIC_UNITS
            or any(type(e) is not SemanticEvidence for e in self.semantic_evidence)
        ):
            raise ChunkingError("Supply bounded immutable semantic evidence.")
        last = 0
        for evidence in self.semantic_evidence:
            if (
                first.strategy != "semantic"
                or not last < evidence.offset < self.chunks[-1].end
            ):
                raise ChunkingError(
                    "Keep semantic evidence ordered within its document."
                )
            last = evidence.offset


def _result(
    document: IngestedDocument,
    spans: list[tuple[int, int]],
    strategy: Strategy,
    evidence: tuple[SemanticEvidence, ...] = (),
) -> ChunkingResult:
    return ChunkingResult(
        tuple(
            DocumentChunk(document, i, a, b, strategy) for i, (a, b) in enumerate(spans)
        ),
        evidence,
    )


def _append(spans: list[tuple[int, int]], start: int, end: int) -> None:
    if len(spans) >= MAX_CHUNKS:
        raise ChunkingError("Increase chunk size; output exceeds the 4096-chunk limit.")
    spans.append((start, end))


_DEFAULT_FIXED = FixedConfig()
_DEFAULT_RECURSIVE = RecursiveConfig()
_DEFAULT_SEMANTIC = SemanticConfig()


def chunk_fixed(
    document: IngestedDocument, config: FixedConfig = _DEFAULT_FIXED
) -> ChunkingResult:
    """Create fixed windows with configured overlap and a final partial window.

    Stop when a window reaches document end, avoiding redundant overlap tails.

    Args:
        document: Accepted immutable ingestion contract.
        config: Validated application-owned size and overlap in characters.

    Returns:
        Complete source coverage and stable zero-based chunk ordering.

    Raises:
        ChunkingError: For wrong input/configuration or excessive output count.
    """
    _document(document)
    if type(config) is not FixedConfig:
        raise ChunkingError("Supply a validated FixedConfig.")
    length, step = len(document.content), config.size - config.overlap
    count = 1 + max(0, math.ceil((length - config.size) / step))
    if count > MAX_CHUNKS:
        raise ChunkingError(
            "Increase size or reduce overlap; at most 4096 chunks allowed."
        )
    spans = [
        (start, min(start + config.size, length))
        for start in range(0, count * step, step)
    ]
    return _result(document, spans, "fixed")


def chunk_recursive(
    document: IngestedDocument, config: RecursiveConfig = _DEFAULT_RECURSIVE
) -> ChunkingResult:
    """Recursively split oversized spans using a literal separator hierarchy.

    At each level, separators belong to the left span. Adjacent fitting spans
    merge greedily; oversized spans flush that group and descend to the next
    separator. Exhausted hierarchy uses exact character windows without overlap.

    Args:
        document: Accepted immutable ingestion contract.
        config: Validated character ceiling and separator priority.

    Returns:
        Deterministic complete partition, each chunk at most config.size.

    Raises:
        ChunkingError: For wrong input/configuration or excessive output count.
    """
    _document(document)
    if type(config) is not RecursiveConfig:
        raise ChunkingError("Supply a validated RecursiveConfig.")
    text, spans = document.content, []

    def split(start: int, end: int, level: int) -> None:
        if end - start <= config.size:
            _append(spans, start, end)
            return
        if level == len(config.separators):
            for offset in range(start, end, config.size):
                _append(spans, offset, min(offset + config.size, end))
            return
        separator = config.separators[level]
        cursor, group_start, group_end = start, start, start
        while cursor < end:
            found = text.find(separator, cursor, end)
            piece_end = found + len(separator) if found >= 0 else end
            if piece_end - cursor > config.size:
                if group_end > group_start:
                    _append(spans, group_start, group_end)
                split(cursor, piece_end, level + 1)
                group_start = group_end = piece_end
            else:
                if piece_end - group_start > config.size:
                    _append(spans, group_start, group_end)
                    group_start = cursor
                group_end = piece_end
            cursor = piece_end
        if group_end > group_start:
            _append(spans, group_start, group_end)

    split(0, len(text), 0)
    return _result(document, spans, "recursive")


def _semantic_units(text: str) -> list[tuple[int, int]]:
    """Scan candidate boundaries with monotonically advancing character offsets.

    Consume each punctuation or horizontal-space run once, including failed
    boundary candidates. Successful candidates retain trailing Unicode whitespace
    on the left, matching the original sentence/blank-LF-line rules in O(n) work.

    Args:
        text: Exact accepted document content.

    Returns:
        Original half-open spans, including any final unmatched remainder.

    Raises:
        ChunkingError: If more than 4096 candidate units are encountered.
    """
    units: list[tuple[int, int]] = []
    start, cursor, length = 0, 0, len(text)
    while cursor < length:
        char = text[cursor]
        boundary = False
        if char in ".!?":
            cursor += 1
            while cursor < length and text[cursor] in ".!?":
                cursor += 1
            boundary = cursor == length or text[cursor].isspace()
        elif char == "\n":
            cursor += 1
            while cursor < length and text[cursor] in " \t":
                cursor += 1
            if cursor < length and text[cursor] == "\n":
                cursor += 1
                boundary = True
        else:
            cursor += 1
        if boundary:
            while cursor < length and text[cursor].isspace():
                cursor += 1
            units.append((start, cursor))
            start = cursor
            if len(units) > MAX_SEMANTIC_UNITS:
                raise ChunkingError(
                    "Reduce document units to at most 4096 for semantic scoring."
                )
    if start < length:
        units.append((start, length))
    if len(units) > MAX_SEMANTIC_UNITS:
        raise ChunkingError(
            "Reduce document units to at most 4096 for semantic scoring."
        )
    return units


def chunk_semantic(
    document: IngestedDocument,
    signal: SemanticSignal,
    config: SemanticConfig = _DEFAULT_SEMANTIC,
) -> ChunkingResult:
    """Group adjacent sentence/paragraph units according to injected similarity.

    Candidate units end after .!? followed by whitespace/end, or a blank LF line;
    following whitespace belongs to the left unit. Low similarity starts a new
    group; related units join while they fit. Oversized individual units use hard
    character windows, clearly a size fallback, not inferred semantic boundaries.

    Args:
        document: Accepted ingestion contract containing untrusted literal text.
        signal: Trusted application-selected deterministic meaning/similarity code.
        config: Validated hard size ceiling and similarity threshold.

    Returns:
        Complete nonoverlapping chunks plus all adjacent-unit similarity evidence.

    Raises:
        ChunkingError: For wrong input/configuration or excessive units/chunks.
        SemanticSignalError: If callback fails or returns a malformed score. Raw
            callback exceptions are suppressed in displayed chains for privacy.
    """
    _document(document)
    if type(config) is not SemanticConfig or not callable(signal):
        raise ChunkingError(
            "Supply SemanticConfig and an application semantic callback."
        )
    text = document.content
    units = _semantic_units(text)
    evidence: list[SemanticEvidence] = []
    for left, right in pairwise(units):
        try:
            similarity = signal(text[left[0] : left[1]], text[right[0] : right[1]])
        except Exception:
            raise SemanticSignalError(
                "Semantic callback failed; repair its implementation or adapter."
            ) from None
        _score(similarity)
        evidence.append(SemanticEvidence(right[0], float(similarity)))
    spans: list[tuple[int, int]] = []
    group_start, group_end = 0, 0
    for i, (start, end) in enumerate(units):
        if group_end > group_start and (
            evidence[i - 1].similarity < config.threshold
            or end - group_start > config.size
        ):
            _append(spans, group_start, group_end)
            group_start = group_end = start
        if end - start > config.size:
            for offset in range(start, end, config.size):
                _append(spans, offset, min(offset + config.size, end))
            group_start = group_end = end
        else:
            if group_start == group_end:
                group_start = start
            group_end = end
    if group_end > group_start:
        _append(spans, group_start, group_end)
    return _result(document, spans, "semantic", tuple(evidence))
