"""Strict Pydantic construction and serialization contracts for Story 2."""

import pytest
from prompt_engineering_systems.contracts import ValidationLimits
from prompt_engineering_systems.structured.models import (
    SourceReference,
    StructuredAnswer,
)
from prompt_engineering_systems.structured.validation import validate_typed_output
from pydantic import ValidationError


def test_typed_answer_contains_typed_sources() -> None:
    """Nested source records must become explicit application model instances."""
    answer = StructuredAnswer(
        answer="Supported answer.",
        sources=[{"source_id": "source-1", "excerpt": "Supporting fact."}],
    )
    assert isinstance(answer.sources[0], SourceReference)
    assert answer.model_dump() == {
        "answer": "Supported answer.",
        "sources": [{"source_id": "source-1", "excerpt": "Supporting fact."}],
    }


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"answer": 7},
        {"answer": True},
        {"answer": None},
        {"answer": ""},
        {"answer": " \n "},
        {"answer": "x" * 8_193},
        {"answer": "ok", "unexpected": "not accepted"},
        {"answer": "ok", "sources": [{"source_id": "s"}]},
        {"answer": "ok", "sources": [{"source_id": 1, "excerpt": "fact"}]},
        {
            "answer": "ok",
            "sources": [{"source_id": "s", "excerpt": "fact", "extra": 1}],
        },
        {"answer": "ok", "sources": [{"source_id": "s", "excerpt": "fact"}] * 2},
        {
            "answer": "ok",
            "sources": [{"source_id": str(i), "excerpt": "f"} for i in range(33)],
        },
    ],
)
def test_invalid_typed_answers_are_rejected(payload: dict[str, object]) -> None:
    """Reject coercion, omitted fields, extras, and invariant violations.

    Args:
        payload: Malformed candidate answer.
    """
    with pytest.raises(ValidationError):
        StructuredAnswer.model_validate(payload)


def test_answer_defaults_are_independent() -> None:
    """Separate answers must not share the default source list."""
    first = StructuredAnswer(answer="first")
    second = StructuredAnswer(answer="second")
    first.sources.append(SourceReference(source_id="s", excerpt="fact"))
    assert second.sources == []


def test_deterministic_typed_round_trip() -> None:
    """Serialization must survive the full raw JSON trust boundary unchanged."""
    original = StructuredAnswer(
        answer="A Unicode answer: café.",
        sources=[SourceReference(source_id="s", excerpt="Document evidence.")],
    )
    serialized = original.model_dump_json()
    restored = validate_typed_output(serialized, StructuredAnswer)
    assert restored == original
    assert restored.model_dump_json() == serialized


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_text_bytes": 0},
        {"max_depth": 65},
        {"max_nodes": 10_001},
        {"max_validation_work": 1_000_001},
        {"max_depth": "32"},
        {"unexpected": 1},
    ],
)
def test_invalid_validation_budgets_are_rejected(overrides: dict[str, object]) -> None:
    """Budgets must remain positive, explicit, strict, and bounded.

    Args:
        overrides: Invalid budget configuration.
    """
    with pytest.raises(ValidationError):
        ValidationLimits.model_validate(overrides)
