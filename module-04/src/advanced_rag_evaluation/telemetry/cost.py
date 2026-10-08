"""Versioned pricing and cost measurement/optimization evidence (M4-OPT-03).

Monetary arithmetic uses ``decimal.Decimal`` throughout, never ``float``:
pricing rates, token-derived fractions, and computed cost are all exact
decimal values, avoiding the rounding ambiguity binary floating point would
introduce into a dollar figure.

Pricing is always explicit, versioned, application-supplied configuration
(``PricingConfig``); nothing here hard-codes a current vendor price as
timeless truth, and no retrieved or model content can alter a price, a
provider/model identity, or a usage classification.

Two token-usage evidence classes are kept strictly separate:

- **Actual**: genuine provider-reported counts, built only by
  ``actual_usage``, always classified ``"actual"``.
- **Estimated**: produced by an injected ``TokenEstimator`` (or the
  provided ``CharacterRatioEstimator`` convention) via ``estimate_usage``,
  always classified ``"estimated"`` and always carrying an explicit,
  named estimation convention. An estimate is never silently presented as
  actual provider billing.

No accepted tokenizer dependency/contract exists elsewhere in this
repository (Module 3's context budgeting is explicitly character-based, not
token-based, for the same reason); ``CharacterRatioEstimator`` is a
deliberately simple, named, versioned heuristic documented with its
limitations, not a claim of tokenizer-accurate counting.
"""

import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from ..errors import CostConfigurationError, CostError, CostEstimationError

TOKENS_PER_RATE_UNIT = Decimal(1_000_000)
ESTIMATION_CONVENTION_CHARACTER_RATIO_V1 = "character-ratio-v1"


@dataclass(frozen=True, slots=True)
class PricingConfig:
    """Explicit, versioned, provider/model-identified pricing.

    Rates are USD per 1,000,000 tokens, matching common provider pricing-
    page conventions; this unit is fixed and explicit, not configurable per
    instance, so every PricingConfig in a given deployment is directly
    comparable.

    Args:
        provider: Nonblank provider identifier (for example "demo-provider").
        model: Nonblank model identifier.
        pricing_version: Nonblank version/date label for this specific rate
            snapshot (for example "demo-2026-10-fixture"), so a cost
            evaluation can always be traced back to exactly which pricing
            snapshot produced it.
        input_rate_usd_per_million_tokens: Nonnegative, finite Decimal.
        output_rate_usd_per_million_tokens: Nonnegative, finite Decimal.

    Raises:
        CostConfigurationError: For blank identifiers or invalid rates.
    """

    provider: str
    model: str
    pricing_version: str
    input_rate_usd_per_million_tokens: Decimal
    output_rate_usd_per_million_tokens: Decimal

    def __post_init__(self) -> None:
        """Validate pricing identity and rates before any cost is computed."""
        for label, value in (
            ("provider", self.provider),
            ("model", self.model),
            ("pricing_version", self.pricing_version),
        ):
            if type(value) is not str or not value.strip():
                raise CostConfigurationError(f"Use a nonblank {label}.")
        for label, rate in (
            (
                "input_rate_usd_per_million_tokens",
                self.input_rate_usd_per_million_tokens,
            ),
            (
                "output_rate_usd_per_million_tokens",
                self.output_rate_usd_per_million_tokens,
            ),
        ):
            if type(rate) is not Decimal or not rate.is_finite() or rate < 0:
                raise CostConfigurationError(
                    f"Use a finite nonnegative Decimal for {label}."
                )


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """One request's input/output token counts, with an honest usage label.

    Args:
        input_tokens: Nonnegative integer input token count.
        output_tokens: Nonnegative integer output token count.
        classification: Exactly "actual" or "estimated".
        estimation_convention: Required (nonblank) when classification is
            "estimated"; must be None when classification is "actual".

    Raises:
        CostConfigurationError: For invalid counts, an unknown
            classification, or an inconsistent estimation_convention pairing.
    """

    input_tokens: int
    output_tokens: int
    classification: str
    estimation_convention: str | None = field(default=None)

    def __post_init__(self) -> None:
        """Validate counts and the actual/estimated labeling invariant."""
        for label, value in (
            ("input_tokens", self.input_tokens),
            ("output_tokens", self.output_tokens),
        ):
            if type(value) is not int or type(value) is bool or value < 0:
                raise CostConfigurationError(f"Use a nonnegative integer {label}.")
        if self.classification not in ("actual", "estimated"):
            raise CostConfigurationError('Use classification "actual" or "estimated".')
        if self.classification == "actual" and self.estimation_convention is not None:
            raise CostConfigurationError(
                "Actual usage must not carry an estimation_convention."
            )
        if self.classification == "estimated" and (
            type(self.estimation_convention) is not str
            or not self.estimation_convention.strip()
        ):
            raise CostConfigurationError(
                "Estimated usage must carry a nonblank estimation_convention."
            )

    @property
    def is_actual(self) -> bool:
        """Return True for genuine provider-reported usage."""
        return self.classification == "actual"


def actual_usage(input_tokens: int, output_tokens: int) -> TokenUsage:
    """Build TokenUsage from genuine provider-reported counts.

    Args:
        input_tokens: Nonnegative integer input token count, as reported by
            the provider -- never derived from an estimator.
        output_tokens: Nonnegative integer output token count, as reported
            by the provider.

    Returns:
        A TokenUsage classified "actual".

    Raises:
        CostConfigurationError: For invalid counts.
    """
    return TokenUsage(input_tokens, output_tokens, "actual", None)


class TokenEstimator(Protocol):
    """Provider-neutral text-to-token-count estimation boundary."""

    def estimate(self, text: str) -> int:
        """Return a nonnegative estimated token count for the given text.

        Args:
            text: Application-supplied text, treated as data.

        Returns:
            A nonnegative integer estimate.

        Raises:
            Exception: Implementation-specific failures translated at the
                ``estimate_usage`` boundary.
        """
        ...


@dataclass(frozen=True, slots=True)
class CharacterRatioEstimator:
    """A simple, named, versioned character-count-ratio token estimator.

    This is explicitly a rough heuristic, not a tokenizer: it divides each
    text's character length by ``chars_per_token`` and rounds up. It cannot
    account for a real tokenizer's vocabulary, multi-byte characters, or
    whitespace handling, and must never be presented as an actual provider
    count -- ``estimate_usage`` always classifies its output "estimated".

    Args:
        chars_per_token: Positive integer divisor; default 4, a commonly
            cited rough English-text approximation.

    Raises:
        CostConfigurationError: For a non-positive chars_per_token.
    """

    chars_per_token: int = 4

    def __post_init__(self) -> None:
        """Validate the divisor before any text is estimated."""
        if (
            type(self.chars_per_token) is not int
            or type(self.chars_per_token) is bool
            or self.chars_per_token < 1
        ):
            raise CostConfigurationError("Use a positive integer chars_per_token.")

    def estimate(self, text: str) -> int:
        """Return ceil(len(text) / chars_per_token), or 0 for empty text.

        Args:
            text: Text to estimate a token count for.

        Returns:
            A nonnegative integer estimate.

        Raises:
            CostConfigurationError: If text is not a string.
        """
        if type(text) is not str:
            raise CostConfigurationError("Supply a string to estimate.")
        if not text:
            return 0
        return math.ceil(len(text) / self.chars_per_token)


_DEFAULT_ESTIMATOR = CharacterRatioEstimator()


def estimate_usage(
    input_text: str,
    output_text: str,
    estimator: TokenEstimator = _DEFAULT_ESTIMATOR,
    *,
    convention: str = ESTIMATION_CONVENTION_CHARACTER_RATIO_V1,
) -> TokenUsage:
    """Build TokenUsage from an injected estimator; always labeled "estimated".

    Args:
        input_text: Text whose input token count should be estimated.
        output_text: Text whose output token count should be estimated.
        estimator: Injected TokenEstimator; defaults to
            CharacterRatioEstimator.
        convention: Nonblank name/version for the estimation convention used;
            defaults to the character-ratio estimator's own convention name.
            Required when an application supplies a different estimator, so
            cost evidence always names the method that produced it.

    Returns:
        A TokenUsage classified "estimated", carrying ``convention``.

    Raises:
        CostConfigurationError: For a blank convention.
        CostEstimationError: If the estimator raises, or returns a
            non-integer or negative count.
    """
    if type(convention) is not str or not convention.strip():
        raise CostConfigurationError("Supply a nonblank estimation convention.")
    try:
        input_tokens = estimator.estimate(input_text)
        output_tokens = estimator.estimate(output_text)
    except CostError:
        raise
    except Exception as exc:
        raise CostEstimationError(
            "The injected TokenEstimator failed; repair the estimator or its input."
        ) from exc
    for label, value in (("input", input_tokens), ("output", output_tokens)):
        if type(value) is not int or type(value) is bool or value < 0:
            raise CostEstimationError(
                f"The estimator returned an invalid nonnegative-integer {label} count."
            )
    return TokenUsage(input_tokens, output_tokens, "estimated", convention)


@dataclass(frozen=True, slots=True)
class CostEvaluation:
    """One priced TokenUsage, with every figure needed to audit the result.

    Args:
        pricing: The PricingConfig used to compute cost_usd.
        usage: The TokenUsage priced, retaining its actual/estimated label.
        cost_usd: The computed Decimal cost; this is a computed figure from
            the supplied pricing/usage, not a claim of exact provider
            billing, which may differ (rounding, taxes, discounts, etc.).

    Raises:
        CostConfigurationError: For wrong types or a cost_usd inconsistent
            with pricing/usage.
    """

    pricing: PricingConfig
    usage: TokenUsage
    cost_usd: Decimal

    def __post_init__(self) -> None:
        """Re-validate types and recompute cost_usd to confirm consistency."""
        if type(self.pricing) is not PricingConfig:
            raise CostConfigurationError("Supply a validated PricingConfig.")
        if type(self.usage) is not TokenUsage:
            raise CostConfigurationError("Supply a validated TokenUsage.")
        if type(self.cost_usd) is not Decimal or not self.cost_usd.is_finite():
            raise CostConfigurationError("Use a finite Decimal cost_usd.")
        expected = _compute_cost(self.pricing, self.usage)
        if self.cost_usd != expected:
            raise CostConfigurationError(
                "cost_usd must equal pricing applied to usage exactly."
            )

    @property
    def is_actual(self) -> bool:
        """Return True when this cost was computed from actual provider usage."""
        return self.usage.is_actual


def _compute_cost(pricing: PricingConfig, usage: TokenUsage) -> Decimal:
    """Return the exact Decimal cost for usage priced at pricing's rates."""
    input_cost = (
        Decimal(usage.input_tokens)
        / TOKENS_PER_RATE_UNIT
        * pricing.input_rate_usd_per_million_tokens
    )
    output_cost = (
        Decimal(usage.output_tokens)
        / TOKENS_PER_RATE_UNIT
        * pricing.output_rate_usd_per_million_tokens
    )
    return input_cost + output_cost


def compute_cost(pricing: PricingConfig, usage: TokenUsage) -> CostEvaluation:
    """Price one TokenUsage against one PricingConfig.

    Args:
        pricing: Validated, versioned PricingConfig.
        usage: Validated TokenUsage, actual or estimated.

    Returns:
        A CostEvaluation retaining pricing, usage, and the computed cost.

    Raises:
        CostConfigurationError: For wrong-typed pricing/usage.
    """
    if type(pricing) is not PricingConfig:
        raise CostConfigurationError("Supply a validated PricingConfig.")
    if type(usage) is not TokenUsage:
        raise CostConfigurationError("Supply a validated TokenUsage.")
    return CostEvaluation(pricing, usage, _compute_cost(pricing, usage))


@dataclass(frozen=True, slots=True)
class CostBudget:
    """One application-owned maximum-cost-per-call budget.

    Args:
        max_cost_usd: Finite, nonnegative Decimal maximum.

    Raises:
        CostConfigurationError: For an invalid budget.
    """

    max_cost_usd: Decimal

    def __post_init__(self) -> None:
        """Validate the budget before any cost evaluation is compared to it."""
        if (
            type(self.max_cost_usd) is not Decimal
            or not self.max_cost_usd.is_finite()
            or self.max_cost_usd < 0
        ):
            raise CostConfigurationError(
                "Use a finite nonnegative Decimal max_cost_usd."
            )


@dataclass(frozen=True, slots=True)
class CostBudgetEvaluation:
    """One inspectable cost-budget comparison outcome.

    Args:
        cost_usd: The evaluated CostEvaluation's computed cost.
        budget_usd: The configured CostBudget's maximum.
        within_budget: True when cost_usd <= budget_usd.
        classification: The priced usage's "actual"/"estimated" label,
            retained so a budget decision is never made blind to whether
            the underlying cost was measured or estimated.
        rationale: Human-readable explanation naming the cost, budget, and
            outcome.

    Raises:
        CostConfigurationError: For malformed fields or an inconsistent
            within_budget flag.
    """

    cost_usd: Decimal
    budget_usd: Decimal
    within_budget: bool
    classification: str
    rationale: str

    def __post_init__(self) -> None:
        """Re-validate shape and that within_budget matches the compared values."""
        if type(self.within_budget) is not bool:
            raise CostConfigurationError("Use bool for within_budget.")
        if self.classification not in ("actual", "estimated"):
            raise CostConfigurationError('Use classification "actual" or "estimated".')
        if type(self.rationale) is not str or not self.rationale.strip():
            raise CostConfigurationError("Supply a nonblank rationale string.")
        if self.within_budget != (self.cost_usd <= self.budget_usd):
            raise CostConfigurationError(
                "within_budget must equal cost_usd <= budget_usd."
            )


def evaluate_cost_budget(
    evaluation: CostEvaluation, budget: CostBudget
) -> CostBudgetEvaluation:
    """Compare one computed cost against one configured budget.

    Args:
        evaluation: Validated CostEvaluation to evaluate.
        budget: Validated, explicit, application-owned CostBudget.

    Returns:
        A CostBudgetEvaluation with the comparison outcome and rationale.

    Raises:
        CostConfigurationError: For wrong-typed evaluation/budget.
    """
    if type(evaluation) is not CostEvaluation:
        raise CostConfigurationError("Supply a validated CostEvaluation.")
    if type(budget) is not CostBudget:
        raise CostConfigurationError("Supply a validated CostBudget.")
    within = evaluation.cost_usd <= budget.max_cost_usd
    rationale = (
        f"Computed cost ${evaluation.cost_usd} ({evaluation.usage.classification}) "
        f"against a configured budget of ${budget.max_cost_usd}; "
        f"{'within' if within else 'over'} budget."
    )
    return CostBudgetEvaluation(
        evaluation.cost_usd,
        budget.max_cost_usd,
        within,
        evaluation.usage.classification,
        rationale,
    )
