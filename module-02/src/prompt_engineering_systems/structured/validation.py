"""Release typed data only after strict parsing, schema, and invariant validation.

Expected input/library failures become domain errors. Data-bearing validation
errors are not rendered as causes; safe decoder causes remain available.
Unexpected defects in trusted application models or library code propagate.
"""

import json
import math

from pydantic import ValidationError

from ..contracts import JSONValue, StrictContract, ValidationLimits
from ..errors import JSONParsingError, TypedValidationError, ValidationLimitError
from ._bounds import inspect_json
from .schemas import Schema, schema_for_model, validate_against_schema


def _object_without_duplicates(
    pairs: list[tuple[str, JSONValue]],
) -> dict[str, JSONValue]:
    """Reject ambiguous objects rather than accepting the decoder's last key value."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise JSONParsingError("Duplicate JSON object keys are not accepted.")
        result[key] = value
    return result


def _finite_float(text: str) -> float:
    """Reject finite-looking JSON literals whose float representation overflows."""
    value = float(text)
    if not math.isfinite(value):
        raise JSONParsingError("Non-finite numbers are not accepted in JSON.")
    return value


def _reject_constant(_: str) -> None:
    """Disable the decoder's permissive support for NaN and Infinity tokens."""
    raise JSONParsingError("NaN and Infinity are not accepted in JSON.")


def _bounded_integer(text: str) -> int:
    """Translate the native integer digit-limit failure at its actual boundary."""
    try:
        return int(text)
    except ValueError as exc:
        raise JSONParsingError(
            "JSON numeric data exceeds the decoder's supported range."
        ) from exc


def parse_json_text(text: str, *, limits: ValidationLimits | None = None) -> JSONValue:
    """Decode exactly one bounded, finite JSON document without coercive repair.

    Args:
        text: Raw model/external text; fences and surrounding prose are rejected.
        limits: Optional explicit resource budgets.

    Returns:
        Parsed JSON data, still untrusted until schema and typed checks pass.

    Raises:
        JSONParsingError: For malformed, ambiguous, non-finite, or non-UTF-8 data.
        ValidationLimitError: If byte size, nesting, or node budgets are exceeded.
    """
    budgets = limits or ValidationLimits()
    if type(text) is not str:
        raise JSONParsingError("Raw output must be JSON text.")
    if len(text) > budgets.max_text_bytes:
        raise ValidationLimitError(
            "Raw output byte budget exceeded; request a smaller output."
        )
    try:
        size = len(text.encode("utf-8"))
    except UnicodeError as exc:
        raise JSONParsingError("Raw output must be valid UTF-8 text.") from exc
    if size > budgets.max_text_bytes:
        raise ValidationLimitError(
            "Raw output byte budget exceeded; request a smaller output."
        )
    # Bound nesting before invoking the recursive standard-library JSON decoder.
    depth, quoted, escaped = 0, False, False
    for character in text:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            if depth > budgets.max_depth:
                raise ValidationLimitError(
                    "Raw output depth budget exceeded; reduce nesting."
                )
        elif character in "]}":
            depth -= 1
    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_float=_finite_float,
            parse_constant=_reject_constant,
            parse_int=_bounded_integer,
        )
    except json.JSONDecodeError as exc:
        raise JSONParsingError(
            "Expected one strict JSON document; remove prose or fix syntax."
        ) from exc
    inspect_json(value, budgets)
    return value


def validate_typed_output[Contract: StrictContract](
    text: str,
    contract: type[Contract],
    *,
    schema: Schema | None = None,
    limits: ValidationLimits | None = None,
) -> Contract:
    """Release a typed object only after parsing, schema, and invariant checks.

    These checks establish the data contract, not factual correctness or
    permission to execute actions. Models and their validators are trusted code.

    Args:
        text: Raw, untrusted JSON text from a model or external source.
        contract: Application-owned StrictContract subclass establishing final
            invariants; never a model instance or user-defined executable type.
        schema: Optional explicit schema; defaults to the contract-derived schema.
        limits: Optional explicit resource budgets.

    Returns:
        A strictly validated contract instance, never merely a parsed dictionary.

    Raises:
        JSONParsingError: If raw text is not strict finite JSON.
        SchemaDefinitionError: If the selected schema is malformed.
        UnsupportedSchemaError: If the schema/model exceeds the supported policy.
        SchemaValidationError: If parsed JSON fails the selected schema.
        TypedValidationError: If contract is not a StrictContract model class or
            strict fields/application invariants fail.
        ValidationLimitError: If input or validation work exceeds resource budgets.
    """
    if not isinstance(contract, type) or not issubclass(contract, StrictContract):
        raise TypedValidationError("Contract must be a StrictContract model class.")
    budgets = limits or ValidationLimits()
    payload = parse_json_text(text, limits=budgets)
    selected_schema = (
        schema if schema is not None else schema_for_model(contract, limits=budgets)
    )
    validate_against_schema(payload, selected_schema, limits=budgets)
    try:
        return contract.model_validate(payload, strict=True, extra="forbid")
    except ValidationError as exc:
        # Count is safe; library paths, contexts, and rejected values are not.
        raise TypedValidationError(
            "JSON failed strict contract fields or application invariants "
            f"({exc.error_count()} validation issue(s)); correct the output."
        ) from None
