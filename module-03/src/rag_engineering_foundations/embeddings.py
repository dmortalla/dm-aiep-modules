"""Offline embedding contracts; untrusted text never selects provider behavior."""

import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Protocol

from .errors import EmbeddingError, VectorError
from .vectors import Vector, _dimension

MAX_BATCH_SIZE = 64
MAX_TEXT_BYTES = 32_768
MAX_BATCH_BYTES = 1_048_576


def validate_texts(texts: tuple[str, ...]) -> None:
    """Validate strict bounded text batches without logging or rewriting input.

    Args:
        texts: Tuple of 1..64 nonblank strings; <=32768 UTF-8 bytes each and
            <=1048576 bytes combined. These are byte budgets, not token budgets.

    Raises:
        EmbeddingError: For invalid types, blank/invalid Unicode, or exceeded limits.
    """
    if type(texts) is not tuple or not 1 <= len(texts) <= MAX_BATCH_SIZE:
        raise EmbeddingError("Supply a tuple of 1..64 texts in input order.")
    total = 0
    for text in texts:
        if type(text) is not str or not text.strip():
            raise EmbeddingError("Supply nonblank strings as embedding input.")
        if len(text) > MAX_TEXT_BYTES:
            raise EmbeddingError("Reduce each input to at most 32768 UTF-8 bytes.")
        try:
            size = len(text.encode("utf-8"))
        except UnicodeEncodeError:
            raise EmbeddingError("Supply valid Unicode embedding input.") from None
        if size > MAX_TEXT_BYTES:
            raise EmbeddingError("Reduce each input to at most 32768 UTF-8 bytes.")
        total += size
    if total > MAX_BATCH_BYTES:
        raise EmbeddingError(
            "Reduce combined embedding input to at most 1048576 bytes."
        )


@dataclass(frozen=True, slots=True)
class EmbeddingBatch:
    """Ordered immutable vectors with explicit shared dimension, without raw text.

    Args:
        vectors: Tuple of 1..64 validated Vector objects, positional to input texts.
        dimension: Shared coordinate count, validated against every vector.

    Raises:
        EmbeddingError: For malformed batch shape or inconsistent dimensions.
    """

    vectors: tuple[Vector, ...] = field(repr=False)
    dimension: int

    def __post_init__(self) -> None:
        """Validate every vector's shared dimension and immutable container."""
        try:
            _dimension(self.dimension)
        except VectorError as exc:
            raise EmbeddingError(
                "Use a shared embedding dimension from 1 to 16384."
            ) from exc
        if (
            type(self.vectors) is not tuple
            or not 1 <= len(self.vectors) <= MAX_BATCH_SIZE
            or any(
                type(v) is not Vector or v.dimension != self.dimension
                for v in self.vectors
            )
        ):
            raise EmbeddingError(
                "Supply 1..64 validated vectors with the declared dimension."
            )


class Embedder(Protocol):
    """Provider-neutral ordered text-to-vector boundary chosen by application code."""

    @property
    def dimension(self) -> int:
        """Return the application's expected embedding dimension."""
        ...

    def embed(self, texts: tuple[str, ...]) -> EmbeddingBatch:
        """Generate one validated vector per input, keeping positional alignment.

        Args:
            texts: Explicit bounded tuple of untrusted texts in input order.

        Returns:
            Ordered finite vectors with the expected dimension.

        Raises:
            EmbeddingError: For invalid input, provider failure, or malformed output.
        """
        ...


@dataclass(frozen=True, slots=True)
class LocalHashEmbedder:
    """Deterministic normalized lexical hash features, not trained semantic quality.

    Args:
        dimension: Fixed feature count, 1..16384; default 64.

    Raises:
        EmbeddingError: For a malformed dimension.
    """

    dimension: int = 64

    def __post_init__(self) -> None:
        """Validate dimension without loading a provider SDK or credential."""
        try:
            _dimension(self.dimension)
        except VectorError as exc:
            raise EmbeddingError(
                "Use a local embedding dimension from 1 to 16384."
            ) from exc

    def embed(self, texts: tuple[str, ...]) -> EmbeddingBatch:
        """Hash case-folded Unicode word counts into normalized feature buckets.

        SHA-256 selects buckets independently of Python's randomized hash seed.
        A text with no words uses its exact text as one feature. Collisions and
        lexical overlap limit quality; this is offline engineering evidence only.

        Args:
            texts: Bounded nonblank text tuple; raw text is never retained in output.

        Returns:
            One unit-length nonnegative vector per text, in the same order.

        Raises:
            EmbeddingError: For invalid or oversized input batches.
        """
        validate_texts(texts)
        vectors = []
        for text in texts:
            features = re.findall(r"\w+", text.casefold()) or [text]
            values = [0.0] * self.dimension
            for feature in features:
                bucket = (
                    int.from_bytes(hashlib.sha256(feature.encode()).digest()[:8])
                    % self.dimension
                )
                values[bucket] += 1
            norm = math.hypot(*values)
            vectors.append(Vector(tuple(value / norm for value in values)))
        return EmbeddingBatch(tuple(vectors), self.dimension)
