"""Explicit LangChain runtime RAG integration; core contracts stay SDK-free.

Real RunnableLambda/RunnableSequence execution schedules retrieval and bounded
context/generation. Domain helpers own transformation, embedding, ranking,
selection, trust separation, and evidence. No LangChain agents or tools exist.
"""

from langchain_core.runnables import RunnableLambda
from langsmith.run_helpers import tracing_context

from .embeddings import Embedder
from .errors import (
    ContextOptimizationError,
    GenerationError,
    LangChainIntegrationError,
    QueryTransformationError,
    RagPipelineError,
    RetrievalError,
)
from .generation import Generator
from .rag_pipeline import RagConfig, RagResult, _finish, _retrieve
from .retrieval import VectorIndex
from .retrieval_workflow import RetrievalWorkflowResult

_DEFAULT_CONFIG = RagConfig()


def run_langchain_rag(
    query: str,
    embedder: Embedder,
    index: VectorIndex,
    generator: Generator,
    *,
    config: RagConfig = _DEFAULT_CONFIG,
) -> RagResult:
    """Execute genuine LangChain sequencing in a credential-free RAG workflow.

    Args:
        query: Original query data, never runnable configuration.
        embedder: Application-selected accepted Embedder.
        index: Application-selected accepted VectorIndex.
        generator: Application-selected provider-neutral Generator.
        config: Fixed application policy; content cannot supply callbacks/tools.

    Returns:
        Same domain evidence as run_rag, labelled with the LangChain integration.

    Raises:
        LangChainIntegrationError: For unexpected runtime failure or invalid output.
        RagPipelineError: For invalid configuration or adapter failure.
        QueryTransformationError: For invalid transformation.
        RetrievalError: For invalid retrieval contracts.
        ContextOptimizationError: For invalid context contracts.
        GenerationError: For failed generation or malformed output.
    """
    if type(config) is not RagConfig:
        raise RagPipelineError("Supply a validated RagConfig.")

    def retrieval_stage(text: str) -> RetrievalWorkflowResult:
        return _retrieve(text, embedder, index, config)

    def generation_stage(evidence: RetrievalWorkflowResult) -> RagResult:
        return _finish(evidence, config, generator, integration="langchain")

    chain = RunnableLambda(retrieval_stage) | RunnableLambda(generation_stage)
    # Disable remote tracing even if the caller's environment enables LangSmith.
    # This interface deliberately accepts no content-provided RunnableConfig.
    try:
        with tracing_context(enabled=False):
            result = chain.invoke(query)
    except (
        RagPipelineError,
        QueryTransformationError,
        RetrievalError,
        ContextOptimizationError,
        GenerationError,
    ):
        raise
    except Exception:
        # Genuine third-party runtime boundary: suppress payload-bearing internals.
        raise LangChainIntegrationError(
            "LangChain execution failed; check runtime and integration compatibility."
        ) from None
    if type(result) is not RagResult or result.integration != "langchain":
        raise LangChainIntegrationError("Require complete LangChain RAG evidence.")
    return result
