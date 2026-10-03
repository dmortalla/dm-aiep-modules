"""Provider-neutral RAG orchestration composing accepted Stories 4–7 contracts."""

from dataclasses import dataclass, field

from .context_optimization import (
    ContextOptimizationConfig,
    OptimizedContext,
    optimize_context,
)
from .embeddings import Embedder, EmbeddingBatch
from .errors import RagPipelineError, RagRetrievalError, VectorError
from .generation import (
    GenerationRequest,
    GenerationResult,
    Generator,
    generate,
    validate_generation_result,
)
from .query_transformation import QueryTransformConfig
from .retrieval import MAX_TOP_K, SearchQuery, SearchResults, VectorIndex
from .retrieval_workflow import RetrievalWorkflowResult, retrieve
from .vectors import _dimension


@dataclass(frozen=True, slots=True)
class RagConfig:
    """Application-owned immutable policy retained with every result.

    Args:
        top_k: Maximum results per derived query (1..10000).
        transformation: Accepted deterministic query policy.
        context: Accepted whole-chunk character/count budget policy.

    Raises:
        RagPipelineError: For invalid configuration.
    """

    top_k: int = 10
    transformation: QueryTransformConfig = field(default_factory=QueryTransformConfig)
    context: ContextOptimizationConfig = field(
        default_factory=ContextOptimizationConfig
    )

    def __post_init__(self) -> None:
        """Check only the new composition configuration boundary."""
        if (
            type(self.top_k) is not int
            or not 1 <= self.top_k <= MAX_TOP_K
            or type(self.transformation) is not QueryTransformConfig
            or type(self.context) is not ContextOptimizationConfig
        ):
            raise RagPipelineError("Supply bounded top_k and accepted stage configs.")


@dataclass(frozen=True, slots=True)
class RagResult:
    """Inspectable immutable retrieval, bounded prompt, output, and policy evidence.

    Args:
        retrieval: Original/derived queries and merged candidates with scores.
        request: Exact bounded generation envelope, retaining context provenance.
        generation: Answer and generator-reported model/citation evidence.
        config: Application-selected stage policies.
        integration: Fixed vocabulary identifying the executing orchestration path.

    Raises:
        RagPipelineError: For inconsistent cross-stage evidence.
        GenerationError: For output citing chunks outside supplied context.
    """

    retrieval: RetrievalWorkflowResult = field(repr=False)
    request: GenerationRequest = field(repr=False)
    generation: GenerationResult = field(repr=False)
    config: RagConfig
    integration: str = "core"

    def __post_init__(self) -> None:
        """Verify cross-stage associations using accepted selection logic."""
        if (
            type(self.retrieval) is not RetrievalWorkflowResult
            or type(self.request) is not GenerationRequest
            or type(self.generation) is not GenerationResult
            or type(self.config) is not RagConfig
            or type(self.integration) is not str
            or self.integration not in ("core", "langchain")
        ):
            raise RagPipelineError("Supply validated RAG stage evidence and policy.")
        if (
            self.request.query != self.retrieval.transformation.original_query
            or self.request.context.config != self.config.context
            or self.request.context
            != optimize_context(self.retrieval.candidates, self.config.context)
        ):
            raise RagPipelineError(
                "Keep query, retrieval, and bounded context consistent."
            )
        queries = {query.text for query in self.retrieval.transformation.queries}
        if len(queries) > self.config.transformation.max_queries or any(
            not candidate.produced_by
            or len(set(candidate.produced_by)) != len(candidate.produced_by)
            or not set(candidate.produced_by) <= queries
            for candidate in self.retrieval.candidates
        ):
            raise RagPipelineError("Keep candidate attribution within derived queries.")
        validate_generation_result(self.generation, self.request)

    @property
    def original_query(self) -> str:
        """Return the exact original query for deliberate inspection."""
        return self.retrieval.transformation.original_query

    @property
    def context(self) -> OptimizedContext:
        """Return the exact optimized context passed to generation."""
        return self.request.context


def _adapter_dimension(adapter: Embedder | VectorIndex) -> int:
    """Sanitize arbitrary injected adapter property failures at that boundary."""
    try:
        dimension = adapter.dimension
    except Exception:
        raise RagRetrievalError(
            "Read a valid dimension from the configured adapter."
        ) from None
    try:
        _dimension(dimension)
    except VectorError:
        raise RagRetrievalError("Use an adapter dimension from 1 to 16384.") from None
    return dimension


class _EmbeddingBoundary:
    """Sanitize only arbitrary external Embedder callbacks, not domain logic."""

    def __init__(self, adapter: Embedder) -> None:
        self.dimension = _adapter_dimension(adapter)
        self._adapter = adapter

    def embed(self, texts: tuple[str, ...]) -> EmbeddingBatch:
        try:
            batch = self._adapter.embed(texts)
        except Exception:
            raise RagRetrievalError(
                "Query embedding failed; check the configured embedding adapter."
            ) from None
        if type(batch) is not EmbeddingBatch or batch.dimension != self.dimension:
            raise RagRetrievalError(
                "Require an embedding batch matching adapter dimension."
            )
        return batch


class _IndexBoundary:
    """Sanitize only arbitrary external VectorIndex callbacks."""

    def __init__(self, adapter: VectorIndex) -> None:
        self.dimension = _adapter_dimension(adapter)
        self._adapter = adapter

    @property
    def size(self) -> int:
        """Retain the accepted VectorIndex structural surface."""
        try:
            return self._adapter.size
        except Exception:
            raise RagRetrievalError(
                "Read a valid size from the configured index adapter."
            ) from None

    def search(self, query: SearchQuery) -> SearchResults:
        try:
            result = self._adapter.search(query)
        except Exception:
            raise RagRetrievalError(
                "Vector search failed; check the configured index adapter."
            ) from None
        if type(result) is not SearchResults or result.query != query:
            raise RagRetrievalError(
                "Require search evidence matching the issued query."
            )
        return result


def _retrieve(
    query: str, embedder: Embedder, index: VectorIndex, config: RagConfig
) -> RetrievalWorkflowResult:
    """Reuse Story 7 transformation, embedding, search, merge, and dedup."""
    return retrieve(
        query,
        _EmbeddingBoundary(embedder),
        _IndexBoundary(index),
        top_k=config.top_k,
        transform_config=config.transformation,
    )


def _finish(
    retrieval: RetrievalWorkflowResult,
    config: RagConfig,
    generator: Generator,
    *,
    integration: str = "core",
) -> RagResult:
    """Reuse the sole accepted context selector and generation boundary."""
    context = optimize_context(retrieval.candidates, config.context)
    request = GenerationRequest(retrieval.transformation.original_query, context)
    result = generate(request, generator)
    return RagResult(retrieval, request, result, config, integration)


_DEFAULT_CONFIG = RagConfig()


def run_rag(
    query: str,
    embedder: Embedder,
    index: VectorIndex,
    generator: Generator,
    *,
    config: RagConfig = _DEFAULT_CONFIG,
) -> RagResult:
    """Run query -> transform/embed/retrieve/merge -> context -> generate -> evidence.

    Args:
        query: Original bounded query, treated as data.
        embedder: Application-selected accepted embedding capability.
        index: One application-selected accepted vector index.
        generator: Application-selected provider-neutral generation capability.
        config: Immutable transformation, retrieval, and character-budget policy.

    Returns:
        Complete inspectable RAG evidence, never merely an answer string.

    Raises:
        RagPipelineError: For configuration, adapter failure, or inconsistent evidence.
        QueryTransformationError: For invalid query or transformation.
        RetrievalWorkflowError: For incompatible retrieval/embedding contracts.
        ContextOptimizationError: For invalid context contracts.
        GenerationError: For failed generation or malformed output.
    """
    if type(config) is not RagConfig:
        raise RagPipelineError("Supply a validated RagConfig.")
    return _finish(_retrieve(query, embedder, index, config), config, generator)
