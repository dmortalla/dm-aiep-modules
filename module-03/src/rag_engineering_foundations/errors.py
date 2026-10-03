"""Content-safe failures at ingestion, chunking, vector, embedding, and retrieval
boundaries.
"""


class IngestionError(ValueError):
    """Correct invalid content, source references, or metadata before ingestion."""


class UnsupportedInputError(IngestionError):
    """Supply plain text or UTF-8 bytes with the text/plain media type."""


class ChunkingError(ValueError):
    """Correct chunk configuration, document input, or bounded output size."""


class SemanticSignalError(ChunkingError):
    """Repair the application-supplied semantic callback or its similarity output."""


class VectorError(ValueError):
    """Supply finite nonempty equal-dimensional vectors or reduce numeric scale."""


class EmbeddingError(ValueError):
    """Correct embedding text, batch shape, or application configuration."""


class EmbeddingRequestError(EmbeddingError):
    """Correct application credentials, model access, or provider request limits."""


class EmbeddingAvailabilityError(EmbeddingError):
    """Retry later or investigate provider connectivity, limits, or availability."""


class EmbeddingResponseError(EmbeddingError):
    """Reject malformed provider output; check indices, dimensions, and numeric data."""


class RetrievalError(ValueError):
    """Correct retrieval contracts, index configuration, or query shape."""


class FaissOperationError(RetrievalError):
    """Investigate FAISS/application index-state consistency; not caller input."""
