"""Content-safe, application-owned failures at Module 4 boundaries.

Each boundary (corpus, lexical and semantic retrieval, hybrid fusion,
reranking, caching, evaluation, observability) adds its own domain-error
subclasses here. Module 4 owns every error type it raises or classifies; it
imports no error hierarchy from an earlier academic module (Rule 44).
"""


class CorpusError(ValueError):
    """Correct Module 4 corpus chunk identity, provenance, or content input."""


class BM25Error(ValueError):
    """Correct BM25 configuration, corpus construction, or query input."""


class BM25ConfigurationError(BM25Error):
    """Correct BM25 k1/b parameters or the supplied document corpus."""


class BM25QueryError(BM25Error):
    """Correct lexical query shape, such as a tokenizable text and bounded top_k."""


class SemanticRetrievalError(ValueError):
    """Correct semantic-retrieval configuration, embeddings, or query input."""


class SemanticConfigurationError(SemanticRetrievalError):
    """Correct embedder, vector-store, namespace, or indexed corpus settings."""


class SemanticQueryError(SemanticRetrievalError):
    """Correct semantic query text, embedding input, or bounded top_k."""


class SemanticProviderError(SemanticRetrievalError):
    """Check the vector store; provider detail is withheld from this message."""


class HybridFusionError(ValueError):
    """Correct hybrid fusion configuration, leg results, or chunk consistency."""


class HybridConfigurationError(HybridFusionError):
    """Correct HybridConfig parameters, such as rrf_k or top_k."""


class HybridRetrievalError(HybridFusionError):
    """Correct mismatched lexical/semantic leg results fused by chunk identity."""


class RerankingError(ValueError):
    """Correct reranking configuration, query, hybrid input, or candidate evidence."""


class RerankConfigurationError(RerankingError):
    """Correct RerankConfig parameters, the query string, or hybrid input type."""


class RerankScorerError(RerankingError):
    """Repair the injected/adapter scorer, or reject its malformed output."""


class CrossEncoderUnavailableError(RerankScorerError):
    """Install sentence-transformers and verify model identifier/network access."""


class CrossEncoderInferenceError(RerankScorerError):
    """Investigate the loaded cross-encoder model's inference failure."""


class ContextFilterError(ValueError):
    """Correct context-filter configuration or reranked input shape."""


class ContextFilterConfigurationError(ContextFilterError):
    """Correct ContextFilterConfig parameters, such as score threshold/count cap."""


class RetrievalCacheError(ValueError):
    """Correct retrieval-cache key, value shape, or lookup/store input."""


class RetrievalCacheConfigurationError(RetrievalCacheError):
    """Correct a RetrievalCacheKey's query/fingerprint or the cached value type."""


class DynamicRetrievalError(ValueError):
    """Correct dynamic-retrieval policy configuration or query input."""


class DynamicRetrievalConfigurationError(DynamicRetrievalError):
    """Correct DynamicRetrievalPolicyConfig bounds or a blank query."""


class LatencyError(ValueError):
    """Correct latency timing/report input or clock output."""


class LatencyConfigurationError(LatencyError):
    """Correct a stage name, sequence, clock, or latency-budget configuration."""


class LatencyPolicyError(LatencyError):
    """Correct latency-budget policy input, such as an unmeasured budgeted stage."""


class CostError(ValueError):
    """Correct pricing, usage, or cost-budget input."""


class CostConfigurationError(CostError):
    """Correct PricingConfig, TokenUsage, or CostBudget configuration."""


class CostEstimationError(CostError):
    """Repair the injected TokenEstimator or reject its malformed output."""


class EvaluationError(ValueError):
    """Correct evaluation inputs or investigate the configured RAGAS boundary."""


class EvaluationInputError(EvaluationError):
    """Supply bounded evaluation data and explicit application-owned models."""


class EvaluationIntegrationError(EvaluationError):
    """Check RAGAS installation, configured model availability, or timeout."""


class EvaluationResultError(EvaluationError):
    """Reject malformed judge responses, embedding batches, or metric scores."""


class GenerationError(RuntimeError):
    """Classify a generation-stage integration failure for failure analysis.

    Only the failure category is owned here; Story 10's ``generation.py``
    raises it for invalid generation input, generator failures, and rejected
    generator output.
    """


class HybridRagError(ValueError):
    """Correct end-to-end hybrid RAG configuration, inputs, or result evidence."""
