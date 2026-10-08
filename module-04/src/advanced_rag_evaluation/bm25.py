"""Deterministic, offline Okapi BM25 lexical retrieval over Module 4 chunks.

This module implements classic Okapi BM25 (Robertson/Sparck Jones) entirely
in the standard library: no SDK, network access, or credential is used or
required. It operates directly on Module 4's own immutable ``CorpusChunk``
contract (see ``advanced_rag_evaluation.corpus``), retaining each chunk by
reference so ``chunk_id``/``document_id`` provenance survives unchanged into
the hybrid-fusion stage (Story 3), which needs that identity to merge this
lexical leg with the semantic leg over the same corpus.

Tokenized chunk content is indexed and scored as inert data: nothing here
executes, imports, or otherwise acts on chunk content, and no document or
query string can alter scoring behavior beyond contributing term statistics.

Algorithm choice: a hand-written Okapi BM25 implementation was used instead
of a third-party library (for example ``rank_bm25``) to avoid adding a new
dependency for a course *topic* that is not one of Module 4's explicitly
required named *tools* (RAGAS, LangSmith, LangFuse, ChromaDB, Pinecone), and
to keep deterministic numeric primitives hand-written and fully auditable
(see also Module 4's ``semantic_retrieval.HashEmbedder``). The
formula, smoothing, and tie-breaking are documented below rather than hidden
behind a library call.
"""

import math
import re
from dataclasses import dataclass, field

from .corpus import CorpusChunk
from .errors import BM25ConfigurationError, BM25QueryError

MAX_TOP_K = 10_000
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> tuple[str, ...]:
    """Split text into lowercase ASCII-alphanumeric tokens, in original order.

    This is an explicit, limited tokenization boundary: no stemming,
    lemmatization, locale awareness, or stop-word removal is applied. Tokens
    are never executed or interpreted; they are only counted.

    Args:
        text: Source text, typically chunk content or a query string.

    Returns:
        Ordered tuple of tokens; empty when no alphanumeric run is present.
    """
    return tuple(_TOKEN_PATTERN.findall(text.lower()))


@dataclass(frozen=True, slots=True)
class BM25Config:
    """Application-owned Okapi BM25 smoothing parameters.

    Args:
        k1: Term-frequency saturation; 0.0 < k1 <= 10.0. Default 1.5.
        b: Document-length normalization strength; 0.0 <= b <= 1.0. Default 0.75.

    Raises:
        BM25ConfigurationError: For non-numeric or out-of-range settings.
    """

    k1: float = 1.5
    b: float = 0.75

    def __post_init__(self) -> None:
        """Validate smoothing parameters before any corpus is considered."""
        if (
            type(self.k1) not in (int, float)
            or type(self.k1) is bool
            or not 0.0 < self.k1 <= 10.0
        ):
            raise BM25ConfigurationError("Use a numeric k1 from above 0 up to 10.")
        if (
            type(self.b) not in (int, float)
            or type(self.b) is bool
            or not 0.0 <= self.b <= 1.0
        ):
            raise BM25ConfigurationError("Use a numeric b from 0 to 1.")


@dataclass(frozen=True, slots=True)
class LexicalQuery:
    """An application-issued BM25 search request against one lexical index.

    Args:
        text: Nonblank query text; tokenized the same way as indexed content.
        top_k: Requested maximum ranked results, 1..10000.

    Raises:
        BM25QueryError: For blank/non-string text, an out-of-range top_k, or
            text that tokenizes to no terms at all.
    """

    text: str
    top_k: int = 10

    def __post_init__(self) -> None:
        """Validate query shape; blank or term-free text cannot be searched."""
        if type(self.text) is not str or not self.text.strip():
            raise BM25QueryError("Supply a nonblank query string.")
        if type(self.top_k) is not int or type(self.top_k) is bool:
            raise BM25QueryError("Use an integer top_k from 1 to 10000.")
        if not 1 <= self.top_k <= MAX_TOP_K:
            raise BM25QueryError("Use an integer top_k from 1 to 10000.")
        if not tokenize(self.text):
            raise BM25QueryError(
                "Supply query text containing at least one alphanumeric term."
            )


@dataclass(frozen=True, slots=True)
class LexicalHit:
    """One ranked BM25 result; the chunk is retained by reference, not copied.

    BM25 relevance is always higher-is-better; there is no distance-metric
    convention to track.

    Args:
        rank: Zero-based descending-relevance position.
        score: Finite, nonnegative BM25 score.
        chunk: Retrieved Module 4 CorpusChunk; content is reachable only
            through ``hit.chunk.content``, never through this object's repr.

    Raises:
        BM25QueryError: For a malformed rank, nonfinite/negative score, or
            wrong chunk type.
    """

    rank: int
    score: float
    chunk: CorpusChunk = field(repr=False)

    def __post_init__(self) -> None:
        """Validate rank/score shape without rendering retrieved content."""
        if type(self.rank) is not int or self.rank < 0:
            raise BM25QueryError("Use a zero-based nonnegative integer rank.")
        if (
            type(self.score) not in (int, float)
            or not math.isfinite(self.score)
            or self.score < 0
        ):
            raise BM25QueryError("Use a finite nonnegative BM25 score.")
        if type(self.chunk) is not CorpusChunk:
            raise BM25QueryError("Supply a validated Module 4 CorpusChunk.")

    @property
    def chunk_id(self) -> str:
        """Return the retrieved chunk's stable identifier."""
        return self.chunk.chunk_id

    @property
    def document_id(self) -> str:
        """Return the retrieved chunk's parent document identifier."""
        return self.chunk.provenance.document_id


@dataclass(frozen=True, slots=True)
class LexicalResults:
    """Validated complete ranked BM25 outcome for one query against one index.

    Args:
        hits: Tuple of 1..query.top_k LexicalHit objects, contiguous rank
            order, nonincreasing score.
        query: Retained LexicalQuery evidence, hidden from repr.

    Raises:
        BM25QueryError: For wrong types, rank gaps, or score-order violations.
    """

    hits: tuple[LexicalHit, ...]
    query: LexicalQuery = field(repr=False)

    def __post_init__(self) -> None:
        """Re-validate rank contiguity and nonincreasing score order."""
        if type(self.query) is not LexicalQuery:
            raise BM25QueryError("Supply a validated LexicalQuery.")
        if (
            type(self.hits) is not tuple
            or not 1 <= len(self.hits) <= self.query.top_k
            or any(type(hit) is not LexicalHit for hit in self.hits)
        ):
            raise BM25QueryError("Supply 1..top_k validated ranked hits.")
        previous: float | None = None
        for index, hit in enumerate(self.hits):
            if hit.rank != index:
                raise BM25QueryError("Keep hit ranks contiguous from zero.")
            if previous is not None and hit.score > previous:
                raise BM25QueryError("Keep hits sorted by nonincreasing score.")
            previous = hit.score


_DEFAULT_CONFIG = BM25Config()


class BM25Index:
    """Provider-neutral, in-memory Okapi BM25 lexical index over one corpus.

    BM25 has no embedding dimension to expose. It exposes the same
    ``size``/``search`` shape as Module 4's semantic indexes where the concepts
    genuinely correspond, so hybrid fusion can treat both as ranked-result
    sources over the same chunk identities.
    """

    __slots__ = (
        "_chunks",
        "_config",
        "_doc_term_freqs",
        "_doc_lengths",
        "_avg_doc_length",
        "_idf",
    )

    def __init__(
        self, chunks: tuple[CorpusChunk, ...], config: BM25Config = _DEFAULT_CONFIG
    ) -> None:
        """Build a BM25 index from an immutable chunk corpus.

        Args:
            chunks: One or more validated Module 4 CorpusChunk objects,
                retained by reference. Chunk content is read once, to derive
                term statistics, and never copied into a mutable form.
            config: Validated Okapi BM25 smoothing parameters.

        Raises:
            BM25ConfigurationError: For an empty/invalid corpus or config.
        """
        if (
            type(chunks) is not tuple
            or not chunks
            or any(type(chunk) is not CorpusChunk for chunk in chunks)
        ):
            raise BM25ConfigurationError(
                "Supply a nonempty tuple of validated Module 4 CorpusChunk objects."
            )
        if type(config) is not BM25Config:
            raise BM25ConfigurationError("Supply a validated BM25Config.")
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        if len(set(chunk_ids)) != len(chunk_ids):
            raise BM25ConfigurationError(
                "Reject duplicate chunk identifiers; index each chunk exactly once."
            )

        doc_term_freqs: list[dict[str, int]] = []
        doc_freq: dict[str, int] = {}
        doc_lengths: list[int] = []
        for chunk in chunks:
            tokens = tokenize(chunk.content)
            doc_lengths.append(len(tokens))
            counts: dict[str, int] = {}
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1
            doc_term_freqs.append(counts)
            for token in counts:
                doc_freq[token] = doc_freq.get(token, 0) + 1

        n = len(chunks)
        idf = {
            term: math.log(1 + (n - df + 0.5) / (df + 0.5))
            for term, df in doc_freq.items()
        }

        self._chunks = chunks
        self._config = config
        self._doc_term_freqs = tuple(doc_term_freqs)
        self._doc_lengths = tuple(doc_lengths)
        self._avg_doc_length = (sum(doc_lengths) / n) if n else 0.0
        self._idf = idf

    @property
    def size(self) -> int:
        """Return the number of indexed chunks."""
        return len(self._chunks)

    def _score(self, index: int, query_terms: tuple[str, ...]) -> float:
        """Return the Okapi BM25 score for one indexed chunk against terms."""
        counts = self._doc_term_freqs[index]
        length = self._doc_lengths[index]
        k1, b = self._config.k1, self._config.b
        total = 0.0
        for term in query_terms:
            freq = counts.get(term)
            idf = self._idf.get(term)
            if not freq or idf is None:
                continue
            normalized_length = (
                length / self._avg_doc_length if self._avg_doc_length else 0
            )
            denominator = freq + k1 * (1 - b + b * normalized_length)
            total += idf * (freq * (k1 + 1)) / denominator
        return total

    def search(self, query: LexicalQuery) -> LexicalResults:
        """Return deterministic ranked BM25 hits for one validated query.

        Ties are broken by original corpus order, so results are fully
        reproducible for a fixed corpus/config/query. Requesting more than
        the index holds is not an error; every indexed chunk is returned,
        ranked, when ``query.top_k`` exceeds ``self.size``.

        Args:
            query: Validated LexicalQuery.

        Returns:
            Complete ranked LexicalResults, 1..min(query.top_k, size) hits.

        Raises:
            BM25QueryError: For an invalid query.
        """
        if type(query) is not LexicalQuery:
            raise BM25QueryError("Supply a validated LexicalQuery.")
        terms = tokenize(query.text)
        scored = sorted(
            range(self.size),
            key=lambda index: (-self._score(index, terms), index),
        )[: query.top_k]
        hits = tuple(
            LexicalHit(rank, max(self._score(index, terms), 0.0), self._chunks[index])
            for rank, index in enumerate(scored)
        )
        return LexicalResults(hits, query)


def build_bm25_index(
    chunks: tuple[CorpusChunk, ...], config: BM25Config = _DEFAULT_CONFIG
) -> BM25Index:
    """Build a BM25Index from a chunk corpus; a thin, explicit entry point.

    Args:
        chunks: Nonempty tuple of validated Module 4 CorpusChunk objects.
        config: Validated Okapi BM25 smoothing parameters.

    Returns:
        A ready-to-query BM25Index.

    Raises:
        BM25ConfigurationError: For an empty/invalid corpus or config.
    """
    return BM25Index(chunks, config)
