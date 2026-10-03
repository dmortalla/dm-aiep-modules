"""Shared private validation for Story 6 adapters; no provider dependencies."""

import math
from dataclasses import dataclass
from typing import Literal

from .errors import RetrievalError, VectorError
from .retrieval import IndexedChunk, SearchHit, SearchQuery, SearchResults
from .vectors import Vector, _dimension


@dataclass(frozen=True, slots=True)
class StoreConfig:
    """Immutable dimension/metric settings inherited by concrete store configs.

    Args:
        dimension: Coordinate count, 1..16384.
        metric: Cosine similarity or genuine Euclidean distance.

    Raises:
        RetrievalError: For unsupported metrics or dimensions.
    """

    dimension: int
    metric: Literal["cosine", "euclidean"] = "cosine"

    def __post_init__(self) -> None:
        """Validate explicit application settings before SDK use."""
        try:
            _dimension(self.dimension)
        except VectorError as exc:
            raise RetrievalError("Use a store dimension from 1 to 16384.") from exc
        if type(self.metric) is not str or self.metric not in ("cosine", "euclidean"):
            raise RetrievalError("Use cosine or euclidean store metrics.")


def prepare(vector: Vector, config: StoreConfig) -> list[float]:
    """Validate dimension and prepare finite float32-compatible coordinates."""
    if vector.dimension != config.dimension:
        raise RetrievalError("Vector dimension must match the store configuration.")
    values = vector.values
    if config.metric == "cosine":
        scale = max(abs(value) for value in values)
        if scale == 0:
            raise RetrievalError("Cosine requires nonzero vectors.")
        scaled = tuple(value / scale for value in values)
        norm = math.hypot(*scaled)
        values = tuple(value / norm for value in scaled)
    # Providers use float32. Reject overflow and complete underflow, rather than
    # silently changing a finite application's vector into infinity or zero.
    if any(abs(value) > 3.4028234663852886e38 for value in values):
        raise RetrievalError("Reduce vector magnitudes to the float32 range.")
    if config.metric == "cosine" and not any(abs(v) >= 1.401298464e-45 for v in values):
        raise RetrievalError("Supply representable nonzero cosine coordinates.")
    return list(values)


def records_map(records: tuple[IndexedChunk, ...], config: StoreConfig) -> dict:
    """Validate the entire bounded batch before any provider mutation."""
    if (
        type(records) is not tuple
        or not 1 <= len(records) <= 10_000
        or any(type(record) is not IndexedChunk for record in records)
    ):
        raise RetrievalError("Supply 1..10000 validated IndexedChunk records.")
    mapping = {record.chunk_id: record for record in records}
    if len(mapping) != len(records):
        raise RetrievalError("Reject duplicate chunk identifiers before insertion.")
    for record in records:
        prepare(record.vector, config)
    return mapping


def query_vector(query: SearchQuery, config: StoreConfig) -> list[float]:
    """Validate query type before preparing its coordinates."""
    if type(query) is not SearchQuery:
        raise RetrievalError("Supply a validated SearchQuery.")
    return prepare(query.vector, config)


def results(
    pairs: list[tuple[str, float]],
    mapping: dict[str, IndexedChunk],
    query: SearchQuery,
    metric: str,
    error: type[RetrievalError],
    *,
    cosine_distance: bool = False,
) -> SearchResults:
    """Check provider identities/numbers before lookup, convert, and rank."""
    if not 1 <= len(pairs) <= min(query.top_k, len(mapping)):
        raise error("Provider returned an invalid result count; verify store state.")
    seen = set()
    candidates = []
    for identity, raw in pairs:
        if type(identity) is not str or identity not in mapping or identity in seen:
            raise error(
                "Provider returned unknown or duplicate IDs; verify store state."
            )
        seen.add(identity)
        if type(raw) not in (int, float):
            raise error("Provider returned a malformed metric value.")
        try:
            finite = math.isfinite(raw)
        except OverflowError:
            finite = False
        if not finite:
            raise error("Provider returned a nonfinite metric value.")
        if metric == "cosine":
            score = 1.0 - raw if cosine_distance else raw
            if not -1.000001 <= score <= 1.000001:
                raise error("Provider returned an out-of-range cosine value.")
            score = max(-1.0, min(1.0, score))
        else:
            if raw < 0:
                raise error("Provider returned a negative squared distance.")
            score = math.sqrt(raw)
        candidates.append((identity, score))
    higher = metric == "cosine"
    candidates.sort(key=lambda item: (-item[1] if higher else item[1], item[0]))
    hits = tuple(
        SearchHit(rank, score, mapping[identity])
        for rank, (identity, score) in enumerate(candidates)
    )
    return SearchResults(hits, query, higher)
