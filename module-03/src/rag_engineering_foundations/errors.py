"""Content-safe failures at document-ingestion boundaries."""


class IngestionError(ValueError):
    """Correct invalid content, source references, or metadata before ingestion."""


class UnsupportedInputError(IngestionError):
    """Supply plain text or UTF-8 bytes with the text/plain media type."""


class ChunkingError(ValueError):
    """Correct chunk configuration, document input, or bounded output size."""


class SemanticSignalError(ChunkingError):
    """Repair the application-supplied semantic callback or its similarity output."""
