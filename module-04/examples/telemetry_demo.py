"""Offline Story 6 latency/cost telemetry demonstration; no network/credentials.

Run: uv run python module-04/examples/telemetry_demo.py

Demonstrates: deterministic multi-stage latency measurement (injected
FakeClock, no sleeps), latency-budget evaluation (one within-budget and one
over-budget stage), actual-provider-usage cost calculation against clearly
labeled fixture pricing, estimated-usage cost calculation via a named
character-ratio estimation convention, and cost-budget evaluation.

IMPORTANT: the pricing below is labeled fixture/demonstration data. It is
not a claim about any real vendor's current pricing; applications must
supply their own versioned PricingConfig.
"""

from decimal import Decimal

from advanced_rag_evaluation.telemetry.cost import (
    CostBudget,
    PricingConfig,
    actual_usage,
    compute_cost,
    estimate_usage,
    evaluate_cost_budget,
)
from advanced_rag_evaluation.telemetry.latency import (
    FakeClock,
    LatencyBudget,
    LatencyBudgetConfig,
    LatencyReport,
    evaluate_latency_budget,
    measure_stage,
)

FIXTURE_PRICING = PricingConfig(
    provider="demo-provider",
    model="demo-model",
    pricing_version="demo-2026-10-fixture",
    input_rate_usd_per_million_tokens=Decimal("3.00"),
    output_rate_usd_per_million_tokens=Decimal("15.00"),
)


def main() -> None:
    """Measure stage latency, evaluate budgets, price actual/estimated usage."""
    print("=== Part 1: deterministic multi-stage latency measurement ===")
    print("Using a FakeClock with pre-set timestamps; no real wall-clock time")
    print("or sleep() is used anywhere in this demonstration.\n")

    # Six timestamps = three (start, end) pairs: lexical+semantic retrieval
    # (fast), reranking (fast), context filtering (deliberately slow, to
    # demonstrate an over-budget stage below).
    clock = FakeClock((0.0, 0.08, 0.08, 0.14, 0.14, 0.52))

    _, retrieval_timing = measure_stage("retrieval", lambda: None, clock, 0)
    _, rerank_timing = measure_stage("reranking", lambda: None, clock, 1)
    _, filter_timing = measure_stage("context_filtering", lambda: None, clock, 2)

    report = LatencyReport((retrieval_timing, rerank_timing, filter_timing))
    for timing in report.stages:
        print(f"  stage={timing.stage!r} elapsed_seconds={timing.elapsed_seconds:.4f}")
    print(f"  total_seconds={report.total_seconds:.4f}")

    print("\n=== Part 2: latency-budget evaluation ===")
    budget_config = LatencyBudgetConfig(
        (
            LatencyBudget("retrieval", 0.10),
            LatencyBudget("reranking", 0.10),
            LatencyBudget("context_filtering", 0.10),
        )
    )
    for evaluation in evaluate_latency_budget(report, budget_config):
        print(f"  {evaluation.rationale}")

    print("\n=== Part 3: cost measurement (fixture pricing, not a vendor claim) ===")
    print(
        f"  pricing: provider={FIXTURE_PRICING.provider!r} "
        f"model={FIXTURE_PRICING.model!r} "
        f"version={FIXTURE_PRICING.pricing_version!r} "
        f"(DEMONSTRATION DATA, not current vendor pricing)"
    )

    print("\n  -- actual, provider-reported usage --")
    actual = actual_usage(input_tokens=1_200, output_tokens=350)
    actual_evaluation = compute_cost(FIXTURE_PRICING, actual)
    print(
        f"  classification={actual.classification!r} "
        f"input_tokens={actual.input_tokens} output_tokens={actual.output_tokens} "
        f"cost_usd=${actual_evaluation.cost_usd}"
    )

    print("\n  -- estimated usage (no provider-reported count available) --")
    prompt_text = "Summarize the retrieved context for the user's question."
    response_text = "Here is a concise summary of the retrieved context."
    estimated = estimate_usage(prompt_text, response_text)
    estimated_evaluation = compute_cost(FIXTURE_PRICING, estimated)
    print(
        f"  classification={estimated.classification!r} "
        f"estimation_convention={estimated.estimation_convention!r} "
        f"input_tokens={estimated.input_tokens} "
        f"output_tokens={estimated.output_tokens} "
        f"cost_usd=${estimated_evaluation.cost_usd}"
    )

    print("\n=== Part 4: cost-budget evaluation ===")
    cost_budget = CostBudget(Decimal("0.01"))
    for label, evaluation in (
        ("actual", actual_evaluation),
        ("estimated", estimated_evaluation),
    ):
        result = evaluate_cost_budget(evaluation, cost_budget)
        print(f"  [{label}] {result.rationale}")

    print(
        "\nWhy this matters: none of this claims to benchmark real production "
        "performance or real vendor billing -- it is deterministic, "
        "inspectable measurement and policy-comparison evidence. The "
        "over-budget context_filtering stage and the cost-budget "
        "comparisons each show exactly which configured threshold was "
        "exceeded and by how much, which is what an application needs to "
        "act on, rather than an opaque pass/fail."
    )


if __name__ == "__main__":
    main()
