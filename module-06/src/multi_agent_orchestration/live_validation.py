"""Pure validation that turns untrusted model text into typed role content.

Raw model text is data. It becomes a typed value only by passing every check
here, and the raw text is never kept, echoed in an error or treated as evidence.
No function in this module calls a model, a provider or the network.
"""

import json
from enum import StrEnum

from pydantic import ValidationError

from .contracts import GraphRole
from .live_contracts import (
    MAX_REPLY_BYTES,
    AnalysisOutput,
    CritiqueOutput,
    LiveAccounting,
    LiveBudget,
    LiveContract,
    LiveEvidence,
    LiveFailure,
    LiveWorkflowResult,
    ModelProduced,
    ModelSelection,
    ModelUsage,
    ResearchOutput,
    role_schema,
)
from .live_errors import LiveExecutionError, LiveFailureCategory, LiveValidationError
from .model_gateway import ModelReply, ModelRequest

_DATA_SCHEMAS = (
    ResearchOutput,
    AnalysisOutput,
    CritiqueOutput,
    ModelSelection,
    LiveBudget,
    ModelUsage,
    LiveAccounting,
    ModelRequest,
    ModelReply,
    LiveEvidence,
    LiveWorkflowResult,
    LiveFailure,
)


def validate_live_data[LiveData: LiveContract](
    schema: type[LiveData], data: object
) -> LiveData:
    """Validate Python data without exposing raw Pydantic diagnostics.

    The application chooses one concrete non-authority Story 1 schema.
    This entry point validates provider replies and application-assembled
    requests, evidence, failures and results containing untrusted data.
    It does not authorize execution, check reply identity against a request,
    or parse raw JSON. Use ``require_live_authorization``, ``checked_reply``
    and ``parse_role_output`` for those respective boundaries.

    Direct constructors and Pydantic validation/accessors are internal only.
    Never log them: even hidden input values leave untrusted error locations.

    Raises:
        LiveValidationError: A fixed category/message, including when the
            schema is unsupported. No input or diagnostic fields are attached.
    """
    try:
        if not any(schema is allowed for allowed in _DATA_SCHEMAS):
            raise ValueError("Unsupported live data schema.")
        return schema.model_validate(data)
    except (ValueError, TypeError, AttributeError, RecursionError):
        pass
    # Raise after the handler so no raw diagnostic survives as __context__.
    raise LiveValidationError() from None


class _MalformedReason(StrEnum):
    """Internal-only closed reason a reply was malformed; never public output.

    Each value names one actual parser/validator boundary. It selects fixed
    application-authored repair wording and supports offline diagnosis; it is
    never attached to an exception, failure, receipt, event or UI value.
    """

    NOT_JSON = "not_json"
    NOT_OBJECT = "not_object"
    DUPLICATE_KEY = "duplicate_key"
    EXTRA_FIELD = "extra_field"
    MISSING_FIELD = "missing_field"
    WRONG_TYPE = "wrong_type"
    BOUNDS = "bounds"
    INVALID_VALUE = "invalid_value"
    INCOMPLETE_PROSE = "incomplete_prose"
    SEMANTIC = "semantic"


# Pydantic error types grouped by boundary; anything unlisted is INVALID_VALUE.
# Ordered by precedence when one reply has several schema errors.
_SCHEMA_REASONS = (
    (_MalformedReason.EXTRA_FIELD, frozenset({"extra_forbidden"})),
    (_MalformedReason.MISSING_FIELD, frozenset({"missing"})),
    (
        _MalformedReason.WRONG_TYPE,
        frozenset(
            {
                "string_type",
                "int_type",
                "tuple_type",
                "list_type",
                "dict_type",
                "model_type",
                "literal_error",
                "enum",
            }
        ),
    ),
    # Item-level validator failures precede bounds: Pydantic also reports the
    # resulting shortened tuple as ``too_short``, which is only a consequence.
    (_MalformedReason.INVALID_VALUE, frozenset({"value_error"})),
    # Prose terminal-punctuation completeness, checked only after visibility.
    (_MalformedReason.INCOMPLETE_PROSE, frozenset({"incomplete_prose"})),
    (
        _MalformedReason.BOUNDS,
        frozenset(
            {
                "string_too_short",
                "string_too_long",
                "too_short",
                "too_long",
                "less_than",
                "less_than_equal",
                "greater_than",
                "greater_than_equal",
            }
        ),
    ),
)


class _DuplicateKeyError(ValueError):
    """Internal marker for an ambiguous repeated JSON field name."""


def _single_object(pairs: list[tuple[str, object]]) -> dict:
    keys = [key for key, _ in pairs]
    if len(set(keys)) != len(keys):
        raise _DuplicateKeyError("Duplicate keys are ambiguous and refused.")
    return dict(pairs)


def _schema_reason(error: ValidationError) -> _MalformedReason:
    """Classify by Pydantic error type only; inputs and locations are ignored."""
    kinds = set()
    try:
        kinds = {item["type"] for item in error.errors(include_input=False)}
    except (ValueError, TypeError, KeyError):
        pass
    if "json_invalid" in kinds:
        return _MalformedReason.NOT_JSON
    for reason, members in _SCHEMA_REASONS:
        if kinds & members:
            return reason
    return _MalformedReason.INVALID_VALUE


def _role_output(
    role: GraphRole, text: object, *, max_reply_bytes: int
) -> ModelProduced | _MalformedReason:
    """Strictly parse one reply, returning content or an internal reason.

    Same checks and order as ``parse_role_output``; only the outcome differs.

    Raises:
        LiveExecutionError: ``output_too_large`` when the reply exceeds its bound.
        ValueError: The role or bound is not an application-valid value.
    """
    schema = role_schema(role)
    if type(max_reply_bytes) is not int or not 1 <= max_reply_bytes <= MAX_REPLY_BYTES:
        raise ValueError("Reply bound is outside the hard application ceiling.")
    if type(text) is not str:
        return _MalformedReason.NOT_JSON
    try:
        size = len(text.encode("utf-8"))
    except UnicodeEncodeError:
        size = -1
    if size < 0:
        return _MalformedReason.NOT_JSON
    if size > max_reply_bytes:
        raise LiveExecutionError(LiveFailureCategory.OUTPUT_TOO_LARGE)
    reason = _MalformedReason.NOT_JSON
    try:
        if type(json.loads(text, object_pairs_hook=_single_object)) is not dict:
            reason = _MalformedReason.NOT_OBJECT
            raise ValueError("A role reply must be one JSON object.")
        return schema.model_validate_json(text)
    except _DuplicateKeyError:
        reason = _MalformedReason.DUPLICATE_KEY
    except ValidationError as error:
        reason = _schema_reason(error)
    except (ValueError, RecursionError):
        pass
    return reason


def parse_role_output(
    role: GraphRole, text: object, *, max_reply_bytes: int
) -> ModelProduced:
    """Validate one model reply as the content schema of an authorized role.

    The reply must be exactly one JSON object with the role's fields and
    nothing else. Extra keys, duplicate keys, wrong types, out-of-bound values,
    non-visible characters and prose without terminal punctuation all fail
    closed; nothing is stripped or repaired.

    Args:
        role: Application-chosen role from the accepted sequential plan. The
            reply never selects its own role or schema.
        text: Untrusted model text.
        max_reply_bytes: Application-owned bound from the authorized budget.

    Returns:
        A frozen ``ResearchOutput``, ``AnalysisOutput`` or ``CritiqueOutput``.

    Raises:
        LiveExecutionError: ``output_too_large`` when the reply exceeds its
            bound, otherwise ``malformed_output``. Neither carries reply text
            or the internal malformed reason.
        ValueError: The role or bound is not an application-valid value.
    """
    content = _role_output(role, text, max_reply_bytes=max_reply_bytes)
    if isinstance(content, _MalformedReason):
        raise LiveExecutionError(LiveFailureCategory.MALFORMED_OUTPUT) from None
    return content


def check_analysis(research: ResearchOutput, analysis: AnalysisOutput) -> None:
    """Require every cited finding to exist in the validated research.

    Raises:
        LiveExecutionError: ``malformed_output`` when either value is not an
            owned, valid contract or a citation points past the findings.
    """
    try:
        if type(research) is not ResearchOutput or type(analysis) is not AnalysisOutput:
            raise ValueError("Unowned role content.")
        research = ResearchOutput.model_validate(dict(research.__dict__))
        analysis = AnalysisOutput.model_validate(dict(analysis.__dict__))
        if max(analysis.supports) > len(research.findings):
            raise ValueError("Analysis cites a finding that does not exist.")
    except (ValueError, TypeError, AttributeError):
        pass
    else:
        return
    raise LiveExecutionError(LiveFailureCategory.MALFORMED_OUTPUT) from None


def _citation_reason(
    research: ResearchOutput, analysis: AnalysisOutput
) -> _MalformedReason | None:
    """Internal form of ``check_analysis``: ``SEMANTIC`` instead of raising."""
    valid = True
    try:
        check_analysis(research, analysis)
    except LiveExecutionError:
        valid = False
    return None if valid else _MalformedReason.SEMANTIC
