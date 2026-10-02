"""Domain failures at structured-output and prompt-construction boundaries.

Public validation functions produce content-safe messages. Data-bearing library
exceptions are suppressed in rendered chains; safe parser causes are retained.
Internal exception context can still retain raw data and must not be serialized
or exposed to users. Direct Pydantic construction has its own native errors.
"""


class StructuredOutputError(ValueError):
    """Base class for failures that must prevent accepting external output."""


class JSONParsingError(StructuredOutputError):
    """Reject invalid JSON; supply one finite, unambiguous UTF-8 document."""


class ValidationLimitError(StructuredOutputError):
    """Reduce input/work or explicitly select a larger supported resource budget."""


class SchemaDefinitionError(StructuredOutputError):
    """Correct the supplied schema or model-class argument before validating data."""


class UnsupportedSchemaError(SchemaDefinitionError):
    """Replace unsupported schema behavior; external retrieval is never attempted."""


class SchemaValidationError(StructuredOutputError):
    """Correct JSON fields/constraints to match the selected schema."""


class TypedValidationError(StructuredOutputError):
    """Correct the model-class argument, strict fields, or application invariants."""


class PromptConstructionError(ValueError):
    """Correct prompt fields, role selection, or character budgets before rendering."""


class TemplateRenderingError(PromptConstructionError):
    """Select an approved template and supply exactly its bounded text variables."""
