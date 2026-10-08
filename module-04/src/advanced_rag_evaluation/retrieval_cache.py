"""Deterministic in-memory retrieval-result caching (M4-OPT-04).

This caches Story 3 ``HybridResults`` retrieval outcomes only -- never a
Story 4 scorer, a loaded cross-encoder model, or any Hugging Face model
state. Cache identity (``RetrievalCacheKey``) is derived only from an
application-supplied query string and an explicit, application-derived
configuration fingerprint; nothing here ever reads retrieved chunk content,
model output, or any instruction-shaped text to decide a cache key or
policy. A cache hit returns the exact previously stored ``HybridResults``
object, never a copy, a rewrite, or a re-ranked/re-filtered derivative, so
Story 2/3 retrieval evidence (and its provenance/trust classification) is
preserved unchanged across hits. No persistence, network call, or external
cache service is used; each ``InMemoryRetrievalCache`` instance owns its own
private dictionary -- there is no module-level or otherwise hidden shared
mutable cache state.
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from .bm25 import BM25Config
from .context_filtering import ContextFilterConfig
from .dynamic_retrieval import DynamicRetrievalDecision, DynamicRetrievalPolicyConfig
from .errors import RetrievalCacheConfigurationError, RetrievalCacheError
from .hybrid_retrieval import HybridConfig, HybridResults
from .reranking import RerankConfig

MAX_QUERY_LENGTH = 32_768
MAX_FINGERPRINT_LENGTH = 256

# The exhaustive, closed set of Module 4 configuration/decision types
# fingerprint_configs accepts. Every member is a frozen, validated dataclass
# whose auto-generated repr() is deterministic and value-based (no field
# holds raw retrieved/chunk content or process-specific identity). This set
# is deliberately closed, not "any frozen dataclass": retrieval-evidence
# types such as CorpusChunk, HybridResults, or RerankedResults are frozen
# dataclasses too, but are not configuration/decision objects and must never
# be accepted here.
_SUPPORTED_FINGERPRINT_TYPES = (
    BM25Config,
    HybridConfig,
    RerankConfig,
    ContextFilterConfig,
    DynamicRetrievalPolicyConfig,
    DynamicRetrievalDecision,
)
_SUPPORTED_SCALAR_TYPES = (str, int, float, bool)


def fingerprint_configs(*configs: object) -> str:
    """Derive a deterministic cache fingerprint from supported config/decision objects.

    Accepts only plain ``str``/``int``/``float``/``bool`` values and
    instances of this repository's known Module 4 configuration/decision
    dataclasses (``BM25Config``, ``HybridConfig``, ``RerankConfig``,
    ``ContextFilterConfig``, ``DynamicRetrievalPolicyConfig``,
    ``DynamicRetrievalDecision``). Every accepted type's ``repr()`` is
    deterministic and value-based by construction (frozen dataclass,
    primitive fields only), so two fingerprints are equal exactly when every
    supplied value is equal. Any other object -- including retrieved content
    or retrieval-evidence types such as ``CorpusChunk`` or
    ``HybridResults``, which are frozen dataclasses too but are not
    configuration objects -- is rejected rather than hashed through a
    generic ``repr()``, which for an arbitrary object is not guaranteed
    deterministic and may embed a process-specific memory address.

    This validation is shallow (it checks each top-level argument's exact
    type against the supported set); it does not recursively re-validate
    that a supported dataclass's own fields are themselves safe, since every
    currently supported type is already known to hold only primitive
    fields.

    Args:
        *configs: One or more supported values that should distinguish
            otherwise-identical queries into separate cache identities.

    Returns:
        A 64-character hex SHA-256 digest of the configs' joined, type-
        qualified reprs.

    Raises:
        RetrievalCacheConfigurationError: If any argument is not one of the
            supported scalar or configuration/decision types.
    """
    for config in configs:
        if (
            type(config) not in _SUPPORTED_FINGERPRINT_TYPES
            and type(config) not in _SUPPORTED_SCALAR_TYPES
        ):
            raise RetrievalCacheConfigurationError(
                "fingerprint_configs only accepts str/int/float/bool or "
                "BM25Config/HybridConfig/RerankConfig/ContextFilterConfig/"
                "DynamicRetrievalPolicyConfig/DynamicRetrievalDecision "
                "instances; supply one of those instead of an arbitrary object."
            )
    canonical = "\x1f".join(
        f"{type(config).__name__}:{config!r}" for config in configs
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class RetrievalCacheKey:
    """A deterministic retrieval-cache identity from validated, owned input.

    Args:
        query: Nonblank query text, at most 32768 characters. Treated as
            opaque identity data, never interpreted or executed.
        config_fingerprint: Nonblank, application-derived string (see
            ``fingerprint_configs``) distinguishing retrieval configurations
            that must not share a cache entry even for the same query text.

    Raises:
        RetrievalCacheConfigurationError: For blank or oversized fields.
    """

    query: str
    config_fingerprint: str

    def __post_init__(self) -> None:
        """Validate key fields; both are treated as opaque identity data."""
        if (
            type(self.query) is not str
            or not self.query.strip()
            or len(self.query) > MAX_QUERY_LENGTH
        ):
            raise RetrievalCacheConfigurationError(
                "Use a nonblank query string of at most 32768 characters."
            )
        if (
            type(self.config_fingerprint) is not str
            or not self.config_fingerprint.strip()
            or len(self.config_fingerprint) > MAX_FINGERPRINT_LENGTH
        ):
            raise RetrievalCacheConfigurationError(
                "Use a nonblank config_fingerprint of at most 256 characters."
            )


@dataclass(frozen=True, slots=True)
class CacheLookup:
    """A single, explicit cache lookup outcome: a hit with a value, or a miss.

    Args:
        hit: True if a stored value was found for the looked-up key.
        value: The stored HybridResults on a hit; always None on a miss.

    Raises:
        RetrievalCacheError: If hit/value disagree (a hit without a value,
            or a miss carrying one).
    """

    hit: bool
    value: HybridResults | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Validate that hit and value are always mutually consistent."""
        if type(self.hit) is not bool:
            raise RetrievalCacheError("Use bool for hit.")
        if self.hit and type(self.value) is not HybridResults:
            raise RetrievalCacheError("A cache hit must carry a HybridResults value.")
        if not self.hit and self.value is not None:
            raise RetrievalCacheError("A cache miss must not carry a value.")


class RetrievalCache(Protocol):
    """Provider-neutral retrieval-cache boundary; in-memory is the only adapter."""

    def get(self, key: RetrievalCacheKey) -> CacheLookup:
        """Look up a previously stored retrieval outcome for one key.

        Args:
            key: Validated RetrievalCacheKey.

        Returns:
            A CacheLookup reporting a hit with the stored value, or a miss.
        """
        ...

    def put(self, key: RetrievalCacheKey, value: HybridResults) -> None:
        """Store one retrieval outcome under one key, replacing any prior entry.

        Args:
            key: Validated RetrievalCacheKey.
            value: Validated Story 3 HybridResults to store by reference.
        """
        ...


class InMemoryRetrievalCache:
    """The required concrete retrieval cache: a private, in-process dictionary.

    No persistence, network access, or external service is used. Each
    instance owns an independent store; constructing a new instance never
    reuses another instance's entries.
    """

    __slots__ = ("_store",)

    def __init__(self) -> None:
        """Create an empty, private cache store owned by this instance alone."""
        self._store: dict[RetrievalCacheKey, HybridResults] = {}

    def __repr__(self) -> str:
        """Return a safe repr; cached retrieval content is never rendered."""
        return f"InMemoryRetrievalCache(size={len(self._store)!r})"

    @property
    def size(self) -> int:
        """Return the number of entries currently stored."""
        return len(self._store)

    def get(self, key: RetrievalCacheKey) -> CacheLookup:
        """Look up a stored HybridResults by key; a miss is explicit, not an error.

        Args:
            key: Validated RetrievalCacheKey.

        Returns:
            A CacheLookup reporting a hit with the stored value, or a miss.

        Raises:
            RetrievalCacheError: For a wrong-typed key.
        """
        if type(key) is not RetrievalCacheKey:
            raise RetrievalCacheError("Supply a validated RetrievalCacheKey.")
        value = self._store.get(key)
        return CacheLookup(hit=value is not None, value=value)

    def put(self, key: RetrievalCacheKey, value: HybridResults) -> None:
        """Store one HybridResults by reference under one key.

        Args:
            key: Validated RetrievalCacheKey.
            value: Validated Story 3 HybridResults, stored by reference,
                never copied or re-derived.

        Raises:
            RetrievalCacheError: For a wrong-typed key or value. This never
                accepts a Story 4 scorer, a loaded cross-encoder model, or
                any other non-retrieval-result object.
        """
        if type(key) is not RetrievalCacheKey:
            raise RetrievalCacheError("Supply a validated RetrievalCacheKey.")
        if type(value) is not HybridResults:
            raise RetrievalCacheError(
                "Cache only validated Story 3 HybridResults retrieval outcomes."
            )
        self._store[key] = value

    def clear(self) -> None:
        """Explicitly discard every stored entry; no implicit expiry exists."""
        self._store.clear()


@dataclass(frozen=True, slots=True)
class CachedRetrieval:
    """One retrieval outcome, explicitly marked fresh or served from cache.

    Args:
        hybrid: The Story 3 HybridResults, retained by reference whether
            freshly computed or served from an existing cache entry; never
            copied or rewritten, hidden from repr.
        from_cache: True if this value was served from an existing cache
            entry; False if it was freshly computed and just stored. This
            flag is truthful by construction: ``get_or_retrieve`` is the
            only producer of this type, and only ever sets it to match
            whichever branch actually ran.

    Raises:
        RetrievalCacheError: For a wrong-typed hybrid value or from_cache flag.
    """

    hybrid: HybridResults = field(repr=False)
    from_cache: bool

    def __post_init__(self) -> None:
        """Validate the wrapped retrieval outcome and its cache-origin flag."""
        if type(self.hybrid) is not HybridResults:
            raise RetrievalCacheError("Supply a validated Story 3 HybridResults.")
        if type(self.from_cache) is not bool:
            raise RetrievalCacheError("Use bool for from_cache.")


def get_or_retrieve(
    cache: RetrievalCache,
    key: RetrievalCacheKey,
    retrieve: Callable[[], HybridResults],
) -> CachedRetrieval:
    """Return a cached retrieval outcome, or compute, store, and return a fresh one.

    On a cache hit, ``retrieve`` is never called, and the exact stored
    HybridResults object is returned unchanged. On a cache miss, ``retrieve``
    is called exactly once; its result is validated, stored under ``key``,
    and returned.

    Args:
        cache: A RetrievalCache (concretely, an InMemoryRetrievalCache).
        key: Validated RetrievalCacheKey identifying this retrieval.
        retrieve: Zero-argument callable producing a fresh Story 3
            HybridResults; invoked only on a miss.

    Returns:
        A CachedRetrieval wrapping either the stored or the freshly computed
        HybridResults, with ``from_cache`` set accordingly.

    Raises:
        RetrievalCacheError: For a wrong-typed key or a ``retrieve`` result
            that is not a validated Story 3 HybridResults.
    """
    if type(key) is not RetrievalCacheKey:
        raise RetrievalCacheError("Supply a validated RetrievalCacheKey.")
    lookup = cache.get(key)
    if lookup.hit:
        return CachedRetrieval(lookup.value, from_cache=True)
    value = retrieve()
    if type(value) is not HybridResults:
        raise RetrievalCacheError(
            "retrieve() must return a validated Story 3 HybridResults."
        )
    cache.put(key, value)
    return CachedRetrieval(value, from_cache=False)
