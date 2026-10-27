"""Closed, sanitized failure vocabulary for the additive live-model path.

Execution failures use closed categories; data validation uses one fixed error.
No provider text, reply content, credential or exception body is ever
part of a category or its message. Nothing here contacts a model or provider.
"""

from enum import StrEnum

from .errors import RuntimeFoundationError


class LiveValidationError(RuntimeFoundationError):
    """Public data-validation failure with no input, locations or diagnostics.

    This is not an execution outcome and does not extend the 12 execution
    categories. Raw Pydantic errors are internal untrusted diagnostics.
    """

    category = "invalid_live_data"

    def __init__(self) -> None:
        super().__init__("Live data failed application validation and was discarded.")


class LiveFailureCategory(StrEnum):
    """Why a live run was refused or ended; never derived from model output."""

    AUTHORIZATION_REFUSED = "authorization_refused"
    BUDGET_REFUSED = "budget_refused"
    BUDGET_EXHAUSTED = "budget_exhausted"
    MALFORMED_OUTPUT = "malformed_output"
    OUTPUT_TOO_LARGE = "output_too_large"
    TIMED_OUT = "timed_out"
    PROVIDER_AUTHENTICATION_FAILED = "provider_authentication_failed"
    PROVIDER_AUTHORIZATION_FAILED = "provider_authorization_failed"
    RATE_LIMITED = "rate_limited"
    PROVIDER_SERVICE_FAILED = "provider_service_failed"
    CONNECTION_FAILED = "connection_failed"
    UNEXPECTED_PROVIDER_FAILURE = "unexpected_provider_failure"


_FAILURE_TEXT = {
    LiveFailureCategory.AUTHORIZATION_REFUSED: (
        "Live execution was not explicitly authorized. Nothing ran."
    ),
    LiveFailureCategory.BUDGET_REFUSED: (
        "The live budget is missing or outside its hard bounds. Nothing ran."
    ),
    LiveFailureCategory.BUDGET_EXHAUSTED: (
        "The live budget is spent. No further model call was made."
    ),
    LiveFailureCategory.MALFORMED_OUTPUT: (
        "Model output failed application validation and was discarded."
    ),
    LiveFailureCategory.OUTPUT_TOO_LARGE: (
        "Model output exceeded its hard size bound and was discarded."
    ),
    LiveFailureCategory.TIMED_OUT: "The live run exceeded its deadline.",
    LiveFailureCategory.PROVIDER_AUTHENTICATION_FAILED: (
        "The model provider rejected the credential."
    ),
    LiveFailureCategory.PROVIDER_AUTHORIZATION_FAILED: (
        "The model provider refused permission for this request."
    ),
    LiveFailureCategory.RATE_LIMITED: "The model provider rate-limited the request.",
    LiveFailureCategory.PROVIDER_SERVICE_FAILED: (
        "The model provider reported a service error."
    ),
    LiveFailureCategory.CONNECTION_FAILED: ("The model provider could not be reached."),
    LiveFailureCategory.UNEXPECTED_PROVIDER_FAILURE: (
        "The model provider failed in an unclassified way."
    ),
}


def failure_text(category: LiveFailureCategory) -> str:
    """Return the fixed application wording for a closed failure category.

    Raises:
        ValueError: The value is not one of the closed categories.
    """
    return _FAILURE_TEXT[LiveFailureCategory(category)]


class LiveExecutionError(RuntimeFoundationError):
    """A live run was refused or failed; carries a closed category only.

    The message is always the fixed text of the category. Callers cannot attach
    provider text, model output or a credential, and no retry or fallback to
    another provider or model is implied by any category.

    Args:
        category: One of the closed ``LiveFailureCategory`` values.

    Raises:
        ValueError: The category is not one of the closed values.
    """

    def __init__(self, category: LiveFailureCategory) -> None:
        self.category = LiveFailureCategory(category)
        super().__init__(failure_text(self.category))
