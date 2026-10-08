"""Application-owned failure facts; exception text never becomes authority."""

from dataclasses import dataclass
from enum import StrEnum

import httpx

from ..errors import (
    BM25Error,
    ContextFilterError,
    CorpusError,
    DynamicRetrievalError,
    EvaluationError,
    GenerationError,
    HybridFusionError,
    RerankingError,
    RetrievalCacheError,
    SemanticRetrievalError,
)
from .langsmith_adapter import TraceIntegrationError


class FailureInputError(ValueError):
    """Supply application-owned enums and validated structured failure facts."""


class MonitoringIntegrationError(RuntimeError):
    """Inspect the offline monitoring boundary; raw cause is local debug only."""


class Stage(StrEnum):
    """Closed stage vocabulary selected by application code."""

    RETRIEVAL = "retrieval"
    RERANKING = "reranking"
    CONTEXT_FILTERING = "context_filtering"
    EVALUATION = "evaluation"
    GENERATION = "generation"
    OBSERVABILITY = "observability"


class Category(StrEnum):
    """Safe deterministic classification, independent of messages or metadata."""

    RETRIEVAL = "retrieval"
    RERANKING = "reranking"
    CONTEXT_FILTERING = "context_filtering"
    EVALUATION = "evaluation"
    GENERATION = "generation_integration"
    OBSERVABILITY = "observability"
    TIMEOUT = "timeout"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class FailureAnalysis:
    """Sanitized facts with derived fatality and result usability.

    Args:
        stage: Application-owned stage at which the error was caught.
        category: Fixed category from the domain-error mapping.
        result_available: Whether an upstream workflow result already exists.

    Raises:
        FailureInputError: For malformed or inconsistent facts.
    """

    stage: Stage
    category: Category
    result_available: bool

    def __post_init__(self) -> None:
        """Reject free-form values and categories inconsistent with the stage."""
        if (
            type(self.stage) is not Stage
            or type(self.category) is not Category
            or type(self.result_available) is not bool
        ):
            raise FailureInputError("Supply closed enums and boolean availability.")
        expected = (
            Category(self.stage.value)
            if self.stage is not Stage.GENERATION
            else (Category.GENERATION)
        )
        if self.category not in (expected, Category.TIMEOUT, Category.OTHER):
            raise FailureInputError("Match the domain category to the caught stage.")

    @property
    def fatal(self) -> bool:
        """Observability is optional; other failed stages stop that workflow."""
        return self.stage is not Stage.OBSERVABILITY

    @property
    def result_usable(self) -> bool:
        """A retained result stays usable after an optional monitoring failure."""
        return self.result_available and not self.fatal


_DOMAIN_CATEGORIES = (
    (
        (
            BM25Error,
            HybridFusionError,
            RetrievalCacheError,
            DynamicRetrievalError,
            SemanticRetrievalError,
            CorpusError,
        ),
        Category.RETRIEVAL,
    ),
    ((RerankingError,), Category.RERANKING),
    ((ContextFilterError,), Category.CONTEXT_FILTERING),
    ((EvaluationError,), Category.EVALUATION),
    ((GenerationError,), Category.GENERATION),
    ((MonitoringIntegrationError, TraceIntegrationError), Category.OBSERVABILITY),
)


def analyze_failure(
    stage: Stage, error: Exception, *, result_available: bool = False
) -> FailureAnalysis:
    """Map caught domain types, never exception messages or chained text.

    Args:
        stage: Trusted application stage; never inferred from external data.
        error: Caught exception; only its Python domain type is inspected.
        result_available: Application fact about existing upstream output.

    Returns:
        Immutable sanitized facts. Unknown errors use ``other``.

    Raises:
        FailureInputError: For invalid facts or a domain/stage mismatch.
    """
    if not isinstance(error, Exception):
        raise FailureInputError("Supply a caught exception.")
    category = Category.OTHER
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        category = Category.TIMEOUT
    else:
        for types, mapped in _DOMAIN_CATEGORIES:
            if isinstance(error, types):
                category = mapped
                break
    return FailureAnalysis(stage, category, result_available)
