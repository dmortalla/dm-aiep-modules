"""Behavioral context ordering, provenance, and character-budget contracts."""

import traceback

import pytest
from prompt_engineering_systems.errors import PromptConstructionError
from prompt_engineering_systems.prompts.context import ContextRecord, select_context
from pydantic import ValidationError


def record(identity: str, content: str) -> ContextRecord:
    """Make a small source record for selection tests.

    Args:
        identity: Distinct source identity.
        content: Source text whose relevance/size is tested.

    Returns:
        Typed source with inspectable provenance.
    """
    return ContextRecord(
        record_id=identity, provenance=f"source-{identity}", content=content
    )


def test_relevance_casefold_distinct_words_and_stable_ties() -> None:
    """Count shared distinct words and retain supplied order within equal scores."""
    records = (
        record("none", "unrelated"),
        record("first", "BUDGET budget budget"),
        record("best", "Character budget"),
        record("second", "budget"),
    )
    first = select_context("character BUDGET budget", records)
    assert [item.record_id for item in first.records] == [
        "best",
        "first",
        "second",
        "none",
    ]
    assert first.records[0].provenance == "source-best"
    assert first.records[0].content == "Character budget"
    assert first == select_context("character BUDGET budget", records)
    reversed_ties = select_context("budget", (records[3], records[1]))
    assert [item.record_id for item in reversed_ties.records] == ["second", "first"]


def test_whole_record_skip_then_fit_and_exact_unicode_boundary() -> None:
    """Skip an oversized high-score record, then accept an exact character fit."""
    records = (record("large", "é large"), record("fits", "éé"), record("last", "x"))
    selected = select_context("é large", records, character_budget=2)
    assert selected.records == (records[1],)
    assert selected.content_characters == 2  # Four UTF-8 bytes, two characters.
    assert select_context("é", records, character_budget=0).records == ()
    assert select_context("é", records, character_budget=1).records == (records[2],)


def test_empty_context_and_zero_overlap_preserve_order() -> None:
    """Empty input is natural and unrelated sources remain eligible in order."""
    assert select_context("", ()).content_characters == 0
    records = (record("a", "first"), record("b", "second"))
    assert select_context("", records).records == records


@pytest.mark.parametrize("budget", [-1, 32_769, "10", True])
def test_invalid_selection_budgets_fail_explicitly(budget: object) -> None:
    """Reject unsupported ceilings/coercion instead of weakening selection limits.

    Args:
        budget: Invalid public boundary argument.
    """
    with pytest.raises(PromptConstructionError, match="valid budget"):
        select_context("query", (), character_budget=budget)


def test_duplicate_identity_and_record_count_are_rejected() -> None:
    """Provenance ambiguity and excess candidates fail before ranking."""
    source = record("same", "fact")
    with pytest.raises(PromptConstructionError, match="unique identities"):
        select_context("fact", (source, source))
    maximum = tuple(record(str(index), "x") for index in range(64))
    assert len(select_context("x", maximum).records) == 64
    with pytest.raises(PromptConstructionError):
        select_context("x", (*maximum, record("extra", "x")))


def test_source_field_bounds_and_revalidation_safe_diagnostic() -> None:
    """Accept exact field ceilings and reject invalid copied nested records."""
    ContextRecord(record_id="i" * 128, provenance="p" * 256, content="x" * 4_096)
    with pytest.raises(ValidationError):
        record("id", "x" * 4_097)
    invalid = record("id", "ok").model_copy(update={"content": "PRIVATE_CANARY" * 500})
    with pytest.raises(PromptConstructionError) as caught:
        select_context("ok", (invalid,))
    assert "PRIVATE_CANARY" not in "".join(traceback.format_exception(caught.value))
    assert caught.value.__cause__ is None


def test_query_bound_is_enforced() -> None:
    """The ranking query has a ceiling even when there are no candidates."""
    assert select_context("x" * 12_289, ()).records == ()
    with pytest.raises(PromptConstructionError):
        select_context("x" * 12_290, ())
