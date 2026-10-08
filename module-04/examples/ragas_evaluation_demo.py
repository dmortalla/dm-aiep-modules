"""Credential-free Story 7 lab: real RAGAS metrics with fixed offline judgments.

Run: uv run python module-04/examples/ragas_evaluation_demo.py

Expected: supported answer scores 1/1/1; a mixed unsupported answer with the
useful chunk ranked second scores 0.5/0.5/1; an evasive answer scores 0/1/0.
RAGAS computes these values. The replay judge and local hash embeddings do not
establish semantic judge quality or live/provider-backed verification.
"""

import asyncio

from advanced_rag_evaluation.corpus import build_corpus
from advanced_rag_evaluation.evaluation.ragas_adapter import (
    EvaluationCase,
    EvaluationResult,
    RagasEvaluator,
    build_replay_judge,
)
from advanced_rag_evaluation.semantic_retrieval import HashEmbedder

QUESTION = "Where do apples grow?"
REFERENCE = "Apples grow in orchards."


async def run_demo() -> tuple[EvaluationResult, ...]:
    """Evaluate three fixed cases through the genuine RAGAS integration.

    Returns:
        Supported, mixed/unranked, and evasive results, with original provenance.

    Raises:
        EvaluationError: For invalid data or a RAGAS integration failure.
    """
    useful = build_corpus("story-07-orchard", (REFERENCE,))[0]
    unrelated = build_corpus("story-07-rocket", ("Rockets launch at dawn.",))[0]
    supported = EvaluationCase(
        "supported", QUESTION, REFERENCE, REFERENCE, (useful, unrelated)
    )
    mixed = EvaluationCase(
        "mixed-reordered",
        QUESTION,
        "Apples grow in orchards. Rockets grow on trees.",
        REFERENCE,
        (unrelated, useful),
    )
    evasive = EvaluationCase(
        "evasive", QUESTION, "I do not know.", REFERENCE, (useful, unrelated)
    )
    plans = (
        (supported, (REFERENCE,), (1,), (1, 0), 0),
        (mixed, (REFERENCE, "Rockets grow on trees."), (1, 0), (0, 1), 0),
        (evasive, ("I do not know.",), (0,), (1, 0), 1),
    )
    results = []
    for case, statements, statement_verdicts, context_verdicts, noncommittal in plans:
        judge = build_replay_judge(
            case,
            statements=statements,
            statement_verdicts=statement_verdicts,
            context_verdicts=context_verdicts,
            generated_question=QUESTION,
            noncommittal=noncommittal,
        )
        results.append(await RagasEvaluator(judge, HashEmbedder()).evaluate(case))
    return tuple(results)


def main() -> None:
    """Print expected and actual scores with explicit offline evidence labels."""
    print("Story 7: genuine RAGAS execution; deterministic/offline evidence")
    print("Models: exact prompt replay + Module 4 local hash embeddings")
    print("No live/provider-backed verification; fixed judgments are test fixtures.")
    print("Expected (faithfulness/context precision/relevance):")
    print("  supported=1/1/1; mixed-reordered=0.5/0.5/1; evasive=0/1/0")
    for result in asyncio.run(run_demo()):
        scores = result.scores
        print(
            f"Actual {result.case.case_id}: "
            f"faithfulness={scores.faithfulness:.6f} "
            f"context_precision={scores.context_precision:.6f} "
            f"response_relevancy={scores.response_relevancy:.6f} "
            f"evidence={result.evidence_kind} ragas={result.ragas_version} "
            f"judge_calls={len(result.judge_calls)}"
        )
    print("Why: unsupported claims reduce faithfulness; context order affects")
    print("precision; evasiveness reduces relevance. Metrics remain separate.")


if __name__ == "__main__":
    main()
