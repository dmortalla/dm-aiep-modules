"""Isolated FAISS adapter: a genuine exact flat index over Story 3/4 contracts.

Only this module imports faiss or numpy; ``retrieval.py`` stays provider-neutral
so a later story's ChromaDB or Pinecone adapter can sit beside this one without
changing those contracts. FAISS's own return values (positions, scores) are
untrusted output: every position is range-checked before it is used to
dereference an application record, and every score is checked finite, before
either value becomes part of a public result.
"""

import math
from typing import Literal

import faiss
import numpy as np

from .errors import FaissOperationError, RetrievalError, VectorError
from .retrieval import IndexedChunk, SearchHit, SearchQuery, SearchResults
from .vectors import _dimension

MAX_INDEX_SIZE = 10_000


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    """Scale each row to unit L2 norm using overflow-safe per-row max scaling.

    Dividing by each row's largest-magnitude coordinate first bounds every
    scaled coordinate to [-1, 1] before squaring, so this cannot overflow the
    way a direct ``v / norm(v)`` can for huge-magnitude finite coordinates;
    this mirrors ``vectors.cosine_similarity``'s own normalization technique.

    Args:
        matrix: Float32 array of shape (n, d).

    Returns:
        Row-wise unit-norm array of the same shape and dtype.

    Raises:
        RetrievalError: If any row is exactly the zero vector.
    """
    abs_max = np.max(np.abs(matrix), axis=1, keepdims=True)
    if np.any(abs_max == 0):
        raise RetrievalError(
            "Cosine indexing is undefined for a zero vector; supply nonzero vectors."
        )
    scaled = matrix / abs_max
    norms = np.linalg.norm(scaled, axis=1, keepdims=True)
    return np.ascontiguousarray(scaled / norms, dtype=np.float32)


class FaissIndexConfig:
    """Explicit application-chosen FAISS metric and expected vector dimension.

    Args:
        dimension: Expected coordinate count for every indexed/query vector,
            1..16384.
        metric: ``"cosine"`` builds ``faiss.IndexFlatIP`` over vectors that are
            explicitly L2-normalized before indexing and before every query, so
            the inner product FAISS computes is a true cosine similarity in
            [-1, 1]. ``"euclidean"`` builds ``faiss.IndexFlatL2`` over raw
            vectors with no normalization; lower scores are closer. Default
            ``"cosine"``.

    Raises:
        RetrievalError: For an invalid dimension or unsupported metric name.
    """

    __slots__ = ("dimension", "metric")

    def __init__(
        self, dimension: int, metric: Literal["cosine", "euclidean"] = "cosine"
    ) -> None:
        """Validate settings without touching FAISS, numpy, or any vector data."""
        try:
            _dimension(dimension)
        except VectorError as exc:
            raise RetrievalError("Use an index dimension from 1 to 16384.") from exc
        if type(metric) is not str or metric not in ("cosine", "euclidean"):
            raise RetrievalError('Use metric "cosine" or "euclidean".')
        self.dimension = dimension
        self.metric = metric

    def __repr__(self) -> str:
        """Return a safe repr; this configuration never carries vector data."""
        return f"FaissIndexConfig(dimension={self.dimension!r}, metric={self.metric!r})"

    def __eq__(self, other: object) -> bool:
        """Compare by value; configurations are immutable settings, not identity."""
        if type(other) is not FaissIndexConfig:
            return NotImplemented
        return self.dimension == other.dimension and self.metric == other.metric


class FaissVectorIndex:
    """Immutable exact FAISS index over validated Story 3/4 chunk/vector records.

    Construction performs exactly one deterministic FAISS ``add`` call; there
    is no incremental ``add`` afterward, matching the "deterministic
    construction" requirement rather than mutable online indexing. FAISS's own
    IndexFlatIP/IndexFlatL2 are exact (brute-force) indexes: search compares
    the query against every stored vector, as described in the module
    documentation and ``STORY_05.md``.
    """

    __slots__ = ("_index", "_records", "_config")

    def __init__(
        self, records: tuple[IndexedChunk, ...], config: FaissIndexConfig
    ) -> None:
        """Validate records/config, then build one real FAISS index.

        Args:
            records: Tuple of 1..10000 validated IndexedChunk objects, each
                with config.dimension coordinates and a unique chunk_id.
                Duplicate chunk identifiers are rejected explicitly, not
                silently deduplicated or overwritten.
            config: Validated dimension and metric selection.

        Raises:
            RetrievalError: For wrong types, empty/oversized input, dimension
                mismatch, or duplicate chunk identifiers.
            FaissOperationError: If the underlying FAISS ``add`` call fails
                unexpectedly; this signals an internal defect, not bad input,
                since every invariant FAISS could reasonably reject is already
                checked above it.
        """
        if type(config) is not FaissIndexConfig:
            raise RetrievalError("Supply a validated FaissIndexConfig.")
        if (
            type(records) is not tuple
            or not 1 <= len(records) <= MAX_INDEX_SIZE
            or any(type(record) is not IndexedChunk for record in records)
        ):
            raise RetrievalError("Supply 1..10000 validated IndexedChunk records.")
        if any(record.vector.dimension != config.dimension for record in records):
            raise RetrievalError(
                "Every indexed vector must match the configured dimension."
            )
        chunk_ids = [record.chunk_id for record in records]
        if len(set(chunk_ids)) != len(chunk_ids):
            raise RetrievalError(
                "Reject duplicate chunk identifiers; index each chunk exactly once."
            )
        matrix = np.ascontiguousarray(
            [record.vector.values for record in records], dtype=np.float32
        )
        if config.metric == "cosine":
            matrix = _normalize_rows(matrix)
            index = faiss.IndexFlatIP(config.dimension)
        else:
            index = faiss.IndexFlatL2(config.dimension)
        try:
            index.add(matrix)
        except RuntimeError as exc:
            raise FaissOperationError(
                "FAISS rejected the prepared index batch; "
                "investigate index/configuration consistency."
            ) from exc
        self._index = index
        self._records = records
        self._config = config

    def __repr__(self) -> str:
        """Return a safe repr; indexed chunk/vector content is never rendered."""
        return (
            f"FaissVectorIndex(dimension={self._config.dimension!r}, "
            f"metric={self._config.metric!r}, size={len(self._records)})"
        )

    @property
    def dimension(self) -> int:
        """Return the configured coordinate count every vector must match."""
        return self._config.dimension

    @property
    def metric(self) -> str:
        """Return the configured metric name: "cosine" or "euclidean"."""
        return self._config.metric

    @property
    def size(self) -> int:
        """Return the number of indexed records."""
        return len(self._records)

    def search(self, query: SearchQuery) -> SearchResults:
        """Return deterministic ranked hits for one validated query.

        Requesting more results than indexed records is not an error: at most
        ``size`` hits are returned. FAISS's returned positions and scores are
        treated as untrusted until range/finiteness-checked here; ties in
        FAISS's raw score are broken by ascending chunk_id so repeated runs
        and repeated builds of an equivalent index always produce the same
        order, independent of FAISS's own internal tie behavior.

        Args:
            query: Validated SearchQuery whose vector dimension matches this
                index. The query Vector's own contract already guarantees
                finite coordinates; nothing non-finite reaches FAISS.

        Returns:
            SearchResults ranked best-first per the configured metric.

        Raises:
            RetrievalError: For a wrong query type or a dimension mismatch.
            FaissOperationError: For an unexpected FAISS failure, an
                out-of-range returned position (never dereferenced), or a
                nonfinite returned score.
        """
        if type(query) is not SearchQuery:
            raise RetrievalError("Supply a validated SearchQuery.")
        if query.vector.dimension != self._config.dimension:
            raise RetrievalError("Query vector dimension must match the index.")
        effective_k = min(query.top_k, self.size)
        row = np.ascontiguousarray([query.vector.values], dtype=np.float32)
        if self._config.metric == "cosine":
            row = _normalize_rows(row)
        try:
            scores, positions = self._index.search(row, effective_k)
        except RuntimeError as exc:
            raise FaissOperationError(
                "FAISS rejected the prepared query; "
                "investigate index/configuration consistency."
            ) from exc
        higher_is_better = self._config.metric == "cosine"
        candidates: list[tuple[float, int]] = []
        for raw_score, raw_position in zip(
            scores[0].tolist(), positions[0].tolist(), strict=True
        ):
            position = int(raw_position)
            if not 0 <= position < len(self._records):
                # Also catches FAISS's -1 sentinel for "no further neighbor";
                # that should be unreachable since effective_k <= self.size.
                raise FaissOperationError(
                    "FAISS returned a position outside the indexed record range."
                )
            if not math.isfinite(raw_score):
                raise FaissOperationError("FAISS returned a nonfinite score.")
            if higher_is_better:
                score = float(raw_score)
            else:
                # IndexFlatL2 returns *squared* L2 distance; take the genuine
                # Euclidean distance so this matches vectors.euclidean_distance's
                # semantics. Tiny negative values are a known floating-point
                # artifact of FAISS's expansion identity for near-zero
                # distances, not a real negative squared distance.
                score = math.sqrt(max(0.0, float(raw_score)))
            candidates.append((score, position))
        if len(candidates) != effective_k:
            raise FaissOperationError(
                "FAISS returned fewer valid results than the index size allows."
            )
        candidates.sort(
            key=lambda item: (
                -item[0] if higher_is_better else item[0],
                self._records[item[1]].chunk_id,
            )
        )
        hits = tuple(
            SearchHit(rank=rank, score=score, record=self._records[position])
            for rank, (score, position) in enumerate(candidates)
        )
        return SearchResults(hits=hits, query=query, higher_is_better=higher_is_better)
