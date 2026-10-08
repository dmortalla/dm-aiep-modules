"""End-to-end Module 4 hybrid RAG orchestration (Story 10, M4-LAB-01).

``run_hybrid_rag`` composes the accepted Module 4 stages, in order, into one
independent ``HybridRagResult``:

    query
      -> dynamic_retrieval   (Story 5 policy: retrieval breadth)
      -> retrieval           (Story 2 BM25 + Module 4 semantic leg, Story 3 RRF
                              fusion, optionally through the Story 5 cache)
      -> reranking           (Story 4, injected scorer)
      -> context_filtering   (Story 5, Module 4-native)
      -> generation          (Story 10, consumes FilteredContext directly)

Every stage is timed with the Story 6 ``measure_stage`` contract, and an
optional versioned ``PricingConfig`` prices the generation using actual
generator-reported usage when present, otherwise a labeled estimate
(Approved Human Resolution 8). Evaluation (Story 7) and observability
(Stories 8-9) consume the result afterwards: ``to_evaluation_case`` builds a
RAGAS case from the retained chunks by identity, and ``result.latency`` is the
report the LangSmith/LangFuse adapters accept. Module 4 imports no earlier
academic module (Rule 44).

A stage failure is caught at its boundary and re-raised as
``HybridRagStageFailure`` carrying Story 9's sanitized ``FailureAnalysis``,
with the stage's own domain error as its cause. No stage output, model
output, or retrieved text selects configuration, stages, or control flow.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from .bm25 import LexicalQuery, LexicalResults
from .context_filtering import ContextFilterConfig, FilteredContext, filter_context
from .dynamic_retrieval import (
    DynamicRetrievalDecision,
    DynamicRetrievalPolicyConfig,
    decide_retrieval,
)
from .errors import HybridRagError
from .evaluation.ragas_adapter import EvaluationCase
from .generation import (
    AnswerGenerator,
    ExtractiveAnswerGenerator,
    GeneratedAnswer,
    GenerationRequest,
    generate_answer,
)
from .hybrid_retrieval import HybridConfig, fuse_results
from .observability.failure_analysis import FailureAnalysis, Stage, analyze_failure
from .reranking import RerankConfig, RerankedResults, RerankScorer, rerank
from .retrieval_cache import (
    CachedRetrieval,
    RetrievalCache,
    RetrievalCacheKey,
    fingerprint_configs,
    get_or_retrieve,
)
from .semantic_retrieval import SemanticQuery, SemanticResults
from .telemetry.cost import CostEvaluation, PricingConfig, compute_cost, estimate_usage
from .telemetry.latency import (
    Clock,
    LatencyReport,
    PerfCounterClock,
    StageTiming,
    measure_stage,
)

STAGES = (
    "dynamic_retrieval",
    "retrieval",
    "reranking",
    "context_filtering",
    "generation",
)
_FAILURE_STAGES = {
    "dynamic_retrieval": Stage.RETRIEVAL,
    "retrieval": Stage.RETRIEVAL,
    "reranking": Stage.RERANKING,
    "context_filtering": Stage.CONTEXT_FILTERING,
    "generation": Stage.GENERATION,
}


class LexicalSearch(Protocol):
    """Lexical leg boundary, satisfied by Story 2's ``BM25Index``."""

    def search(self, query: LexicalQuery) -> LexicalResults:
        """Return validated lexical results for one query."""
        ...


class SemanticSearch(Protocol):
    """Semantic leg boundary, satisfied by ChromaDB and Pinecone indexes."""

    def search(self, query: SemanticQuery) -> SemanticResults:
        """Return validated semantic results for one query."""
        ...


class HybridRagStageFailure(RuntimeError):
    """A workflow stage failed; sanitized facts are in ``analysis``.

    The message names only the application-owned stage. The stage's own
    Module 4 domain error is the ``__cause__``.

    Args:
        stage: Application-owned stage name from ``STAGES``.
        analysis: Story 9 FailureAnalysis computed at the catch boundary.
    """

    def __init__(self, stage: str, analysis: FailureAnalysis) -> None:
        super().__init__(
            f"The hybrid RAG workflow stopped at the {stage} stage; "
            "inspect the failure analysis."
        )
        self.stage = stage
        self.analysis = analysis


@dataclass(frozen=True, slots=True)
class HybridRagConfig:
    """Application-owned settings for every orchestrated stage.

    Retrieval breadth is not set here: the dynamic-retrieval decision selects
    the fusion and reranking ``top_k`` for each query.

    Args:
        dynamic_policy: Story 5 dynamic-retrieval policy bounds.
        rrf_k: Story 3 Reciprocal Rank Fusion constant; default 60.0.
        context_filter: Story 5 context-filtering policy.

    Raises:
        HybridRagError: For wrong-typed settings.
        HybridConfigurationError: For an out-of-range ``rrf_k``.
    """

    dynamic_policy: DynamicRetrievalPolicyConfig = field(
        default_factory=DynamicRetrievalPolicyConfig
    )
    rrf_k: float = 60.0
    context_filter: ContextFilterConfig = field(default_factory=ContextFilterConfig)

    def __post_init__(self) -> None:
        """Validate stage configuration types and the fusion constant."""
        if type(self.dynamic_policy) is not DynamicRetrievalPolicyConfig:
            raise HybridRagError("Supply a validated DynamicRetrievalPolicyConfig.")
        if type(self.context_filter) is not ContextFilterConfig:
            raise HybridRagError("Supply a validated ContextFilterConfig.")
        HybridConfig(rrf_k=self.rrf_k)


@dataclass(frozen=True, slots=True)
class HybridRagResult:
    """Complete, cross-validated evidence for one hybrid RAG run.

    Every stage output is retained by identity, so each citation in
    ``answer`` resolves through the filtered context, reranking, and fusion
    back to both retrieval legs and the chunk's provenance.

    Args:
        query: The application-supplied query; hidden from repr.
        decision: Story 5 dynamic-retrieval decision.
        retrieval: Story 5 cache wrapper around the Story 3 HybridResults,
            with a truthful ``from_cache`` marker; hidden from repr.
        reranked: Story 4 RerankedResults; hidden from repr.
        context: Story 5 FilteredContext; hidden from repr.
        answer: Story 10 GeneratedAnswer over ``context``.
        latency: Story 6 LatencyReport with exactly the ``STAGES`` in order.
        cost: Story 6 CostEvaluation, or None when no pricing was supplied.

    Raises:
        HybridRagError: For wrong types or any broken cross-stage link.
    """

    query: str = field(repr=False)
    decision: DynamicRetrievalDecision
    retrieval: CachedRetrieval = field(repr=False)
    reranked: RerankedResults = field(repr=False)
    context: FilteredContext = field(repr=False)
    answer: GeneratedAnswer
    latency: LatencyReport
    cost: CostEvaluation | None = None

    def __post_init__(self) -> None:
        """Re-validate stage types and the identity chain between stages."""
        expected = (
            (self.decision, DynamicRetrievalDecision),
            (self.retrieval, CachedRetrieval),
            (self.reranked, RerankedResults),
            (self.context, FilteredContext),
            (self.answer, GeneratedAnswer),
            (self.latency, LatencyReport),
        )
        if any(type(value) is not kind for value, kind in expected):
            raise HybridRagError("Retain validated evidence from every stage.")
        if self.cost is not None and type(self.cost) is not CostEvaluation:
            raise HybridRagError("Retain cost as a validated CostEvaluation or None.")
        if type(self.query) is not str or not self.query.strip():
            raise HybridRagError("Supply a nonblank query string.")
        if (
            self.reranked.hybrid is not self.retrieval.hybrid
            or self.context.reranked is not self.reranked
            or self.answer.request.context is not self.context
        ):
            raise HybridRagError("Keep every stage linked to its exact input.")
        if self.reranked.query != self.query or self.answer.request.query != self.query:
            raise HybridRagError("Answer and rerank the same query that was run.")
        if tuple(timing.stage for timing in self.latency.stages) != STAGES:
            raise HybridRagError("Time exactly the orchestrated stages, in order.")


def _stage[T](
    name: str, sequence: int, operation: Callable[[], T], clock: Clock
) -> tuple[T, StageTiming]:
    """Run one timed stage, translating any failure at this boundary."""
    try:
        return measure_stage(name, operation, clock, sequence)
    except Exception as exc:
        analysis = analyze_failure(_FAILURE_STAGES[name], exc)
        raise HybridRagStageFailure(name, analysis) from exc


def run_hybrid_rag(
    query: str,
    *,
    lexical: LexicalSearch,
    semantic: SemanticSearch,
    scorer: RerankScorer,
    generator: AnswerGenerator | None = None,
    config: HybridRagConfig | None = None,
    cache: RetrievalCache | None = None,
    clock: Clock | None = None,
    pricing: PricingConfig | None = None,
) -> HybridRagResult:
    """Run the full Module 4 hybrid RAG workflow for one query.

    One ``cache`` instance must serve only one lexical/semantic index pair:
    its key covers the query, fusion configuration, and dynamic decision,
    never index identity or retrieved content.

    Args:
        query: Nonblank application-supplied query, treated as data.
        lexical: Story 2 lexical leg, such as ``BM25Index``.
        semantic: Module 4 semantic leg (``ChromaSemanticIndex`` or
            ``PineconeSemanticIndex``).
        scorer: Story 4 scorer; deterministic or a genuine cross-encoder.
        generator: Story 10 generator; defaults to ExtractiveAnswerGenerator.
        config: Stage settings; defaults to HybridRagConfig().
        cache: Optional Story 5 retrieval cache.
        clock: Story 6 clock; defaults to PerfCounterClock.
        pricing: Optional versioned pricing for the generation cost record.

    Returns:
        HybridRagResult retaining every stage's evidence.

    Raises:
        HybridRagError: For a wrong-typed config or pricing.
        HybridRagStageFailure: When a stage fails, including an invalid
            generator (a generation-stage failure); ``analysis`` holds the
            sanitized category and ``__cause__`` the stage's domain error.
        CostError: If pricing is supplied and the cost cannot be computed.
    """
    config = HybridRagConfig() if config is None else config
    generator = ExtractiveAnswerGenerator() if generator is None else generator
    clock = PerfCounterClock() if clock is None else clock
    if type(config) is not HybridRagConfig:
        raise HybridRagError("Supply a validated HybridRagConfig.")
    if pricing is not None and type(pricing) is not PricingConfig:
        raise HybridRagError("Supply a validated PricingConfig or None.")

    decision, decision_timing = _stage(
        "dynamic_retrieval",
        0,
        lambda: decide_retrieval(query, config.dynamic_policy),
        clock,
    )
    hybrid_config = HybridConfig(rrf_k=config.rrf_k, top_k=decision.top_k)

    def retrieve():
        lexical_results = lexical.search(LexicalQuery(query, top_k=decision.top_k))
        semantic_results = semantic.search(SemanticQuery(query, top_k=decision.top_k))
        return fuse_results(lexical_results, semantic_results, hybrid_config)

    def retrieve_with_cache() -> CachedRetrieval:
        if cache is None:
            return CachedRetrieval(retrieve(), from_cache=False)
        key = RetrievalCacheKey(query, fingerprint_configs(hybrid_config, decision))
        return get_or_retrieve(cache, key, retrieve)

    retrieval, retrieval_timing = _stage("retrieval", 1, retrieve_with_cache, clock)
    reranked, rerank_timing = _stage(
        "reranking",
        2,
        lambda: rerank(
            query, retrieval.hybrid, scorer, RerankConfig(top_k=decision.top_k)
        ),
        clock,
    )
    context, filter_timing = _stage(
        "context_filtering",
        3,
        lambda: filter_context(reranked, config.context_filter),
        clock,
    )
    answer, generation_timing = _stage(
        "generation",
        4,
        lambda: generate_answer(GenerationRequest(query, context), generator),
        clock,
    )
    latency = LatencyReport(
        (
            decision_timing,
            retrieval_timing,
            rerank_timing,
            filter_timing,
            generation_timing,
        )
    )
    cost = None
    if pricing is not None:
        usage = answer.usage
        if usage is None:
            prompt = "\n\n".join(
                (query, *(item.chunk.content for item in context.items))
            )
            usage = estimate_usage(prompt, answer.text)
        cost = compute_cost(pricing, usage)
    return HybridRagResult(
        query, decision, retrieval, reranked, context, answer, latency, cost
    )


def to_evaluation_case(
    result: HybridRagResult, *, case_id: str, reference: str
) -> EvaluationCase:
    """Build a Story 7 RAGAS case from a hybrid RAG result.

    The case reuses the retained chunks and the FilteredContext by identity,
    so evaluation scores stay attached to the exact evidence that was used.

    Args:
        result: Validated HybridRagResult with a non-abstained answer.
        case_id: Application case identifier.
        reference: Application-supplied reference answer.

    Returns:
        EvaluationCase over the generated answer and retained context.

    Raises:
        HybridRagError: For a wrong-typed result or an abstained answer.
        EvaluationInputError: For an invalid case identifier or reference.
    """
    if type(result) is not HybridRagResult:
        raise HybridRagError("Supply a validated HybridRagResult.")
    if result.answer.abstained:
        raise HybridRagError("An abstained answer has no context to evaluate.")
    return EvaluationCase(
        case_id,
        result.query,
        result.answer.text,
        reference,
        tuple(item.chunk for item in result.context.items),
        result.context,
    )
