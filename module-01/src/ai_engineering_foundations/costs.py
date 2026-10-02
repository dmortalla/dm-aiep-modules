"""Token-based LLM cost estimation utilities."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .models import TokenUsage


class TokenPricing(BaseModel):
    """Represent model pricing per one million tokens."""

    model_config = ConfigDict(extra="forbid")

    input_per_million: Decimal = Field(ge=0)
    output_per_million: Decimal = Field(ge=0)


class TokenCost(BaseModel):
    """Represent estimated input, output, and total request cost."""

    model_config = ConfigDict(extra="forbid")

    input_cost: Decimal = Field(ge=0)
    output_cost: Decimal = Field(ge=0)

    @property
    def total_cost(self) -> Decimal:
        """Return combined estimated request cost."""

        return self.input_cost + self.output_cost


def estimate_token_cost(
    usage: TokenUsage,
    pricing: TokenPricing,
) -> TokenCost:
    """Estimate request cost from provider-reported token usage.

    Pricing is supplied explicitly so this module does not embed vendor prices
    that can become stale.
    """
    million = Decimal(1_000_000)

    input_cost = (
        Decimal(usage.input_tokens) * pricing.input_per_million / million
    )
    output_cost = (
        Decimal(usage.output_tokens) * pricing.output_per_million / million
    )

    return TokenCost(
        input_cost=input_cost,
        output_cost=output_cost,
    )