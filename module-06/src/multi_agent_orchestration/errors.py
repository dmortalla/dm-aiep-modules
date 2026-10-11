"""Sanitized application exceptions for real runtime and validation boundaries."""


class RuntimeFoundationError(Exception):
    """Base error for callers to handle without parsing framework messages."""


class UnknownRuntimeError(RuntimeFoundationError):
    """An explicit runtime identifier is not recognized."""


class RuntimeUnavailableError(RuntimeFoundationError):
    """A runtime is missing or cannot execute within this milestone."""


class InvalidWorkflowRequestError(RuntimeFoundationError):
    """Untrusted request data failed the application contract."""


class InvalidRuntimeOutputError(RuntimeFoundationError):
    """Runtime output failed schema or request-correlation checks."""


class ExecutionFailureError(RuntimeFoundationError):
    """A runtime failed unexpectedly; its cause is retained for internal diagnosis."""


class ExecutionTimeoutError(ExecutionFailureError):
    """The application deadline expired and execution was cancelled."""
