"""Raw JSON and typed-boundary failure paths without provider access."""

import json
import traceback

import pytest
from prompt_engineering_systems.contracts import JSONValue, ValidationLimits
from prompt_engineering_systems.errors import (
    JSONParsingError,
    SchemaDefinitionError,
    SchemaValidationError,
    TypedValidationError,
    ValidationLimitError,
)
from prompt_engineering_systems.structured.models import StructuredAnswer
from prompt_engineering_systems.structured.schemas import schema_for_model
from prompt_engineering_systems.structured.validation import (
    parse_json_text,
    validate_typed_output,
)
from pydantic import BaseModel


def test_valid_json_becomes_an_application_object() -> None:
    """A successful pipeline returns a typed model rather than a dictionary."""
    result = validate_typed_output('{"answer":"Validated."}', StructuredAnswer)
    assert isinstance(result, StructuredAnswer)
    assert result.answer == "Validated."


@pytest.mark.parametrize(
    "text",
    [
        "",
        " ",
        "{",
        "{'answer':'wrong quotes'}",
        '{"a":1,}',
        'Here is JSON: {"answer":"ok"}',
        '{"answer":"ok"} trailing prose',
        '```json\n{"answer":"ok"}\n```',
        "{} {}",
        '{"a":1,"a":2}',
        '{"outer":{"a":1,"a":2}}',
        r'{"a":1,"\u0061":2}',
        "NaN",
        "Infinity",
        "-Infinity",
        '{"a":NaN}',
        "[Infinity]",
        "1e400",
        "-1e400",
        '"\ud800"',
    ],
)
def test_non_strict_json_is_rejected(text: str) -> None:
    """Reject malformed, wrapped, ambiguous, or non-finite text.

    Args:
        text: Untrusted invalid document.
    """
    with pytest.raises(JSONParsingError):
        parse_json_text(text)


@pytest.mark.parametrize("text", ["null", "true", "42", "1.5", '"text"', "[]"])
def test_json_scalars_parse_but_do_not_satisfy_answer_contract(text: str) -> None:
    """JSON syntax alone must not establish application trust.

    Args:
        text: Syntactically valid non-answer JSON.
    """
    parse_json_text(text)
    with pytest.raises(SchemaValidationError):
        validate_typed_output(text, StructuredAnswer)


@pytest.mark.parametrize(
    "payload",
    [{}, {"answer": 4}, {"answer": "ok", "extra": 1}, {"answer": ""}],
)
def test_generated_schema_rejects_invalid_answer_fields(payload: JSONValue) -> None:
    """Contract-derived schema must enforce required types, bounds, and extras.

    Args:
        payload: Invalid answer data.
    """
    with pytest.raises(SchemaValidationError):
        validate_typed_output(json.dumps(payload), StructuredAnswer)


@pytest.mark.parametrize("payload", [{}, {"answer": 4}, {"answer": "ok", "extra": 1}])
def test_permissive_schema_cannot_bypass_typed_contract(payload: JSONValue) -> None:
    """Passing an explicit broad schema still requires strict application types.

    Args:
        payload: JSON that matches a permissive schema but fails the contract.
    """
    with pytest.raises(TypedValidationError) as caught:
        validate_typed_output(json.dumps(payload), StructuredAnswer, schema=True)
    assert "validation issue(s)" in str(caught.value)
    assert caught.value.__cause__ is None


def test_schema_match_cannot_bypass_answer_invariant() -> None:
    """A nonempty but whitespace-only answer passes schema and fails Pydantic."""
    with pytest.raises(TypedValidationError):
        validate_typed_output('{"answer":"   "}', StructuredAnswer)


def test_schema_match_cannot_bypass_unique_source_invariant() -> None:
    """Individually valid source records still need application-level uniqueness."""
    payload = {
        "answer": "ok",
        "sources": [{"source_id": "s", "excerpt": "fact"}] * 2,
    }
    with pytest.raises(TypedValidationError):
        validate_typed_output(json.dumps(payload), StructuredAnswer)


def test_parser_preserves_decoder_cause_without_echoing_content() -> None:
    """Malformed text must retain an actionable decoding failure cause."""
    raw = '{"answer":"PRIVATE_CANARY",}'
    with pytest.raises(JSONParsingError) as caught:
        parse_json_text(raw)
    assert isinstance(caught.value.__cause__, json.JSONDecodeError)
    assert "PRIVATE_CANARY" not in str(caught.value)
    assert "PRIVATE_CANARY" not in "".join(traceback.format_exception(caught.value))


def test_typed_errors_and_rendered_causes_do_not_expose_values_or_extra_keys() -> None:
    """Public exception chains must omit attacker-controlled values and paths."""
    payload = {"answer": "ok", "PRIVATE_CANARY": "PRIVATE_CANARY"}
    raw = json.dumps(payload)
    with pytest.raises(TypedValidationError) as caught:
        validate_typed_output(raw, StructuredAnswer, schema=True)
    rendered = "".join(traceback.format_exception(caught.value))
    assert "PRIVATE_CANARY" not in rendered
    assert "1 validation issue(s)" in rendered


@pytest.mark.parametrize(
    ("text", "budgets"),
    [
        ('"abcdef"', ValidationLimits(max_text_bytes=4)),
        ('"éé"', ValidationLimits(max_text_bytes=5)),
        ("[[[0]]]", ValidationLimits(max_depth=2)),
        ("[1,2,3]", ValidationLimits(max_nodes=3)),
    ],
)
def test_raw_input_budgets_are_enforced(text: str, budgets: ValidationLimits) -> None:
    """Reject excessive byte size, nesting, and node count.

    Args:
        text: Candidate raw document.
        budgets: Explicit resource budgets.
    """
    with pytest.raises(ValidationLimitError):
        parse_json_text(text, limits=budgets)


def test_nesting_scan_ignores_brackets_and_escaped_quotes_in_strings() -> None:
    """Quoted JSON characters must not consume container-depth budget."""
    raw = json.dumps({"text": '[{\\"}]'})
    assert parse_json_text(raw, limits=ValidationLimits(max_depth=1)) == {
        "text": '[{\\"}]'
    }


def test_integer_decoder_limit_has_a_domain_failure() -> None:
    """Excessive numeric literals must not leak a native decoder exception."""
    with pytest.raises(JSONParsingError) as caught:
        parse_json_text("9" * 5_000)
    assert isinstance(caught.value.__cause__, ValueError)


def test_exact_compact_byte_budget_is_accepted() -> None:
    """Canonical inspection must not reject compact JSON through added spaces."""
    assert parse_json_text("[0,0]", limits=ValidationLimits(max_text_bytes=5)) == [0, 0]


@pytest.mark.parametrize(
    "contract", [None, StructuredAnswer(answer="ok"), BaseModel, str]
)
def test_invalid_contract_arguments_have_documented_domain_failures(
    contract: object,
) -> None:
    """Model instances/unrelated classes must not escape as attribute errors.

    Args:
        contract: Invalid model-class argument supplied to the public APIs.
    """
    with pytest.raises(SchemaDefinitionError, match="StrictContract model class"):
        schema_for_model(contract)
    with pytest.raises(TypedValidationError, match="StrictContract model class"):
        validate_typed_output('{"answer":"ok"}', contract, schema=True)


def test_unexpected_decoder_defect_is_not_reclassified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A decoder implementation defect is distinct from a numeric input failure.

    Args:
        monkeypatch: Fixture injecting an unexpected decoder ValueError.
    """
    defect = ValueError("Unexpected decoder defect.")

    def broken_decoder(*args: object, **kwargs: object) -> None:
        raise defect

    monkeypatch.setattr(json, "loads", broken_decoder)
    with pytest.raises(ValueError) as caught:
        parse_json_text('{"answer":"ok"}')
    assert caught.value is defect


def test_unexpected_model_validator_defect_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trusted model programmer errors must not look like rejected external data.

    Args:
        monkeypatch: Fixture injecting an unexpected model TypeError.
    """
    defect = TypeError("Unexpected model defect.")

    def broken_validator(*args: object, **kwargs: object) -> None:
        raise defect

    monkeypatch.setattr(StructuredAnswer, "model_validate", broken_validator)
    with pytest.raises(TypeError) as caught:
        validate_typed_output('{"answer":"ok"}', StructuredAnswer)
    assert caught.value is defect
