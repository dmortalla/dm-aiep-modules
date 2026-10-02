"""Offline/provider-independent local acceptance and bounded schema lab behavior."""

import socket

import pytest
from prompt_engineering_systems.contracts import ValidationLimits
from prompt_engineering_systems.errors import (
    JSONParsingError,
    SchemaValidationError,
    StructuredOutputError,
    TypedValidationError,
    UnsupportedSchemaError,
    ValidationLimitError,
)
from prompt_engineering_systems.integrations.offline import OfflineProvider
from prompt_engineering_systems.prompts.construction import (
    ApplicationInstructions,
    PromptSpecification,
)
from prompt_engineering_systems.structured.models import StructuredAnswer
from prompt_engineering_systems.structured.schemas import Schema
from prompt_engineering_systems.workflows import (
    GenerationResult,
    generate_structured,
    validate_schema_lab,
)
from pydantic import ValidationError


def generate(
    text: str,
    *,
    schema: Schema | None = None,
    limits: ValidationLimits | None = None,
) -> GenerationResult[StructuredAnswer]:
    """Run an offline example through shared validation.

    Args:
        text: Raw deterministic example.
        schema: Optional bounded schema override.
        limits: Existing resource budgets.

    Returns:
        Accepted typed answer and explicit offline origin.

    Raises:
        StructuredOutputError: For any rejected JSON/schema/typed contract.
    """
    return generate_structured(
        ApplicationInstructions(
            policy="Follow policy.", task="Answer.", output_contract="Return JSON."
        ),
        PromptSpecification(user_request="Demonstrate."),
        OfflineProvider(text),
        StructuredAnswer,
        schema=schema,
        limits=limits,
    )


def test_offline_is_deterministic_typed_and_network_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify explicit offline acceptance.

    Args:
        monkeypatch: Fixture blocking socket/DNS access.
    """

    def deny(*args: object, **kwargs: object) -> None:
        raise AssertionError("network")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)
    first = generate('{"answer":"Valid."}')
    assert first == generate('{"answer":"Valid."}')
    assert first.mode == "offline" and isinstance(first.answer, StructuredAnswer)
    assert not hasattr(first, "text")
    with pytest.raises(ValidationError):
        OfflineProvider("x" * 65_537)


@pytest.mark.parametrize(
    "text,error",
    [
        ("{", JSONParsingError),
        ('{"answer":"a","answer":"b"}', JSONParsingError),
        ('{"answer":NaN}', JSONParsingError),
        ('prose {"answer":"ok"}', JSONParsingError),
        ('{"answer":1}', SchemaValidationError),
        ("[]", SchemaValidationError),
        ('{"answer":"   "}', TypedValidationError),
        ('{"answer":"ok","tool":"shell"}', SchemaValidationError),
    ],
)
def test_invalid_output_is_never_repaired(
    text: str,
    error: type[StructuredOutputError],
) -> None:
    """Reject invalid examples without repair.

    Args:
        text: Raw untrusted provider output.
        error: Expected local validation failure category.
    """
    with pytest.raises(error):
        generate(text)


def test_permissive_schema_still_requires_strict_pydantic_and_byte_budget() -> None:
    """Explicit schema cannot disable typed checks or Story 2 resource ceilings."""
    with pytest.raises(TypedValidationError):
        generate('{"answer":1}', schema=True)
    with pytest.raises(ValidationLimitError):
        generate('{"answer":"ééé"}', limits=ValidationLimits(max_text_bytes=10))


def test_schema_lab_preserves_local_references_and_network_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preserve bounded local schema behavior without retrieval.

    Args:
        monkeypatch: Fixture blocking socket/DNS access.
    """

    def deny(*args: object, **kwargs: object) -> None:
        raise AssertionError("network")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)
    schema = {"$defs": {"Value": {"type": "integer"}}, "$ref": "#/$defs/Value"}
    assert validate_schema_lab("1", schema) == 1
    with pytest.raises(SchemaValidationError):
        validate_schema_lab('"wrong"', schema)
    with pytest.raises(UnsupportedSchemaError):
        validate_schema_lab("1", {"$ref": "https://example.invalid/schema"})
    with pytest.raises(ValidationLimitError):
        validate_schema_lab("[1,2,3]", True, limits=ValidationLimits(max_nodes=3))
