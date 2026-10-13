"""Pure validation that turns untrusted model text into typed role content.

Raw model text is data. It becomes a typed value only by passing every check
here, and the raw text is never kept, echoed in an error or treated as evidence.
No function in this module calls a model, a provider or the network.
"""

import json

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


def _single_object(pairs: list[tuple[str, object]]) -> dict:
    keys = [key for key, _ in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate keys are ambiguous and refused.")
    return dict(pairs)


def parse_role_output(
    role: GraphRole, text: object, *, max_reply_bytes: int
) -> ModelProduced:
    """Validate one model reply as the content schema of an authorized role.

    The reply must be exactly one JSON object with the role's fields and
    nothing else. Extra keys, duplicate keys, wrong types, out-of-bound values
    and non-visible characters all fail closed; nothing is stripped or repaired.

    Args:
        role: Application-chosen role from the accepted sequential plan. The
            reply never selects its own role or schema.
        text: Untrusted model text.
        max_reply_bytes: Application-owned bound from the authorized budget.

    Returns:
        A frozen ``ResearchOutput``, ``AnalysisOutput`` or ``CritiqueOutput``.

    Raises:
        LiveExecutionError: ``output_too_large`` when the reply exceeds its
            bound, otherwise ``malformed_output``. Neither carries reply text.
        ValueError: The role or bound is not an application-valid value.
    """
    schema = role_schema(role)
    if type(max_reply_bytes) is not int or not 1 <= max_reply_bytes <= MAX_REPLY_BYTES:
        raise ValueError("Reply bound is outside the hard application ceiling.")
    if type(text) is not str:
        raise LiveExecutionError(LiveFailureCategory.MALFORMED_OUTPUT)
    try:
        size = len(text.encode("utf-8"))
    except UnicodeEncodeError:
        size = -1
    if size < 0:
        raise LiveExecutionError(LiveFailureCategory.MALFORMED_OUTPUT) from None
    if size > max_reply_bytes:
        raise LiveExecutionError(LiveFailureCategory.OUTPUT_TOO_LARGE)
    try:
        if type(json.loads(text, object_pairs_hook=_single_object)) is not dict:
            raise ValueError("A role reply must be one JSON object.")
        return schema.model_validate_json(text)
    except (ValueError, ValidationError, RecursionError):
        pass
    raise LiveExecutionError(LiveFailureCategory.MALFORMED_OUTPUT) from None


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
