"""Tests for token cost management."""

from decimal import Decimal

import pytest
from ai_engineering_foundations.costs import (
    TokenPricing,
    estimate_token_cost,
)
from ai_engineering_foundations.models import TokenUsage
from pydantic import ValidationError


def test_estimate_token_cost_separates_input_and_output() -> None:
    """Cost estimation should apply the correct rate to each token category."""
    usage = TokenUsage(
        input_tokens=500_000,
        output_tokens=250_000,
    )
    pricing = TokenPricing(
        input_per_million=Decimal("2.00"),
        output_per_million=Decimal("8.00"),
    )

    cost = estimate_token_cost(usage, pricing)

    assert cost.input_cost == Decimal("1.00")
    assert cost.output_cost == Decimal("2.00")
    assert cost.total_cost == Decimal("3.00")


def test_zero_usage_has_zero_cost() -> None:
    """Requests with no reported usage should estimate zero cost."""
    pricing = TokenPricing(
        input_per_million=Decimal("2.00"),
        output_per_million=Decimal("8.00"),
    )

    cost = estimate_token_cost(TokenUsage(), pricing)

    assert cost.total_cost == Decimal("0")


def test_negative_pricing_is_rejected() -> None:
    """Pricing inputs must fail closed when a negative rate is supplied."""
    with pytest.raises(ValidationError):
        TokenPricing(
            input_per_million=Decimal("-1"),
            output_per_million=Decimal("8"),
        )


def test_unknown_pricing_fields_are_rejected() -> None:
    """Unexpected pricing fields should not silently alter cost behavior."""
    with pytest.raises(ValidationError):
        TokenPricing(
            input_per_million=Decimal("2"),
            output_per_million=Decimal("8"),
            cached_input_per_million=Decimal("1"),
        )