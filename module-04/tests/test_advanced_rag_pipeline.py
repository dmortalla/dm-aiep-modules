"""Deterministic tests for Story 10 end-to-end hybrid RAG orchestration."""

import ast
import dataclasses
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from advanced_rag_evaluation.advanced_rag_pipeline import (
    STAGES,
    HybridRagConfig,
    HybridRagResult,
    HybridRagStageFailure,
    run_hybrid_rag,
    to_evaluation_case,
)
from advanced_rag_evaluation.bm25 import BM25Index
from advanced_rag_evaluation.context_filtering import ContextFilterConfig
from advanced_rag_evaluation.corpus import build_corpus
from advanced_rag_evaluation.errors import (
    GenerationError,
    HybridConfigurationError,
    HybridRagError,
    RerankScorerError,
    SemanticProviderError,
)
from advanced_rag_evaluation.evaluation.ragas_adapter import (
    RagasEvaluator,
    build_replay_judge,
)
from advanced_rag_evaluation.generation import ABSTENTION_TEXT, GeneratorOutput
from advanced_rag_evaluation.observability.failure_analysis import Category, Stage
from advanced_rag_evaluation.observability.langsmith_adapter import (
    LangSmithTracer,
    OfflineTransport,
)
from advanced_rag_evaluation.reranking import DeterministicOverlapScorer
from advanced_rag_evaluation.retrieval_cache import InMemoryRetrievalCache
from advanced_rag_evaluation.semantic_retrieval import (
    ChromaSemanticIndex,
    HashEmbedder,
)
from advanced_rag_evaluation.telemetry.cost import PricingConfig, actual_usage
from advanced_rag_evaluation.telemetry.latency import FakeClock

PASSAGES = (
    "Apples ripen in the orchard every autumn. They are picked by hand at dawn.",
    "Pears grow on trees beside the apple rows and share the same harvest.",
    "Rockets launch from the coastal pad at dawn under tight safety checks.",
    "Satellites orbit the planet for decades, relaying data to ground stations.",
)
QUERY = "when are apples picked by hand"
SECRET = "sk-live-pipeline-secret"
PRICING = PricingConfig(
    provider="fixture-provider",
    model="fixture-model",
    pricing_version="fixture-2026-10",
    input_rate_usd_per_million_tokens=Decimal("3.00"),
    output_rate_usd_per_million_tokens=Decimal("15.00"),
)
NEW_FILES = (
    "src/advanced_rag_evaluation/generation.py",
    "src/advanced_rag_evaluation/advanced_rag_pipeline.py",
    "tests/test_generation.py",
    "tests/test_advanced_rag_pipeline.py",
    "examples/hybrid_rag_workflow.py",
)
MODULE_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {
    "ai_engineering_foundations",
    "prompt_engineering_systems",
    "rag_engineering_foundations",
}


@pytest.fixture(scope="module")
def chunks():
    return build_corpus("pipeline-test", PASSAGES)


@pytest.fixture(scope="module")
def semantic(chunks):
    with ChromaSemanticIndex(chunks, HashEmbedder(dimension=32)) as index:
        yield index


class CountingLexical:
    """Delegating BM25 spy that counts searches."""

    def __init__(self, chunks) -> None:
        self.index = BM25Index(chunks)
        self.calls = 0

    def search(self, query):
        self.calls += 1
        return self.index.search(query)


class FailingSemantic:
    def search(self, query):
        raise SemanticProviderError("The vector store returned an unknown id.")


class FailingScorer:
    def score(self, query, candidates):
        raise RuntimeError(SECRET)


class StubGenerator:
    generator_id = "stub-generator:v1"

    def __init__(self, output=None, error=None) -> None:
        self.output = output
        self.error = error

    def generate(self, request):
        if self.error is not None:
            raise self.error
        return self.output


def run(chunks, semantic, **kwargs) -> HybridRagResult:
    kwargs.setdefault("scorer", DeterministicOverlapScorer())
    return run_hybrid_rag(
        kwargs.pop("query", QUERY),
        lexical=kwargs.pop("lexical", BM25Index(chunks)),
        semantic=semantic,
        **kwargs,
    )


class TestEndToEnd:
    def test_composes_every_stage_by_identity(self, chunks, semantic) -> None:
        result = run(chunks, semantic)
        assert result.reranked.hybrid is result.retrieval.hybrid
        assert result.context.reranked is result.reranked
        assert result.answer.request.context is result.context
        assert result.answer.request.query == result.reranked.query == QUERY
        assert result.decision.branch == "long_query"
        assert result.retrieval.hybrid.config.top_k == result.decision.top_k
        assert result.reranked.config.top_k == result.decision.top_k
        assert result.retrieval.from_cache is False
        assert result.cost is None
        assert tuple(t.stage for t in result.latency.stages) == STAGES

    def test_answer_is_grounded_in_retained_context(self, chunks, semantic) -> None:
        result = run(chunks, semantic)
        assert result.answer.text.startswith("They are picked by hand at dawn. [1]")
        retained = {id(item) for item in result.context.items}
        assert result.answer.citations
        assert all(id(c.item) in retained for c in result.answer.citations)
        assert result.answer.citations[0].source_id == "pipeline-test"

    def test_is_deterministic_with_fake_clock(self, chunks, semantic) -> None:
        stamps = tuple(float(n) for n in range(10))
        first = run(chunks, semantic, clock=FakeClock(stamps))
        second = run(chunks, semantic, clock=FakeClock(stamps))
        assert first.answer.text == second.answer.text
        assert [c.chunk_id for c in first.answer.citations] == [
            c.chunk_id for c in second.answer.citations
        ]
        assert [t.elapsed_seconds for t in first.latency.stages] == [1.0] * 5
        assert first.latency == second.latency

    def test_applies_configured_filter_policy(self, chunks, semantic) -> None:
        config = HybridRagConfig(
            context_filter=ContextFilterConfig(min_rerank_score=0.05, max_candidates=1)
        )
        result = run(chunks, semantic, config=config)
        assert len(result.context.items) == 1
        assert result.context.config is config.context_filter
        assert len(result.answer.citations) == 1

    def test_empty_filtered_context_abstains(self, chunks, semantic) -> None:
        config = HybridRagConfig(
            context_filter=ContextFilterConfig(min_rerank_score=2.0)
        )
        result = run(chunks, semantic, config=config)
        assert result.context.items == ()
        assert result.answer.abstained and result.answer.text == ABSTENTION_TEXT
        with pytest.raises(HybridRagError, match="abstained"):
            to_evaluation_case(result, case_id="c", reference="r")

    def test_repr_excludes_retrieved_content(self, chunks, semantic) -> None:
        text = repr(run(chunks, semantic))
        assert "orchard" not in text and "picked" not in text and QUERY not in text


class TestCachingAndCost:
    def test_cache_serves_repeated_query(self, chunks, semantic) -> None:
        cache = InMemoryRetrievalCache()
        lexical = CountingLexical(chunks)
        first = run(chunks, semantic, lexical=lexical, cache=cache)
        second = run(chunks, semantic, lexical=lexical, cache=cache)
        assert lexical.calls == 1
        assert first.retrieval.from_cache is False
        assert second.retrieval.from_cache is True
        assert second.retrieval.hybrid is first.retrieval.hybrid
        assert second.answer.text == first.answer.text

    def test_estimates_cost_when_generator_reports_none(
        self, chunks, semantic
    ) -> None:
        result = run(chunks, semantic, pricing=PRICING)
        assert result.cost is not None
        assert result.cost.usage.classification == "estimated"
        assert result.cost.usage.estimation_convention == "character-ratio-v1"
        assert result.cost.cost_usd > 0

    def test_uses_actual_generator_usage(self, chunks, semantic) -> None:
        def build_output(request):
            return GeneratorOutput(
                "Picked by hand [1].",
                (request.passages[0].chunk_id,),
                actual_usage(100, 10),
            )

        class UsageGenerator:
            generator_id = "usage-generator:v1"
            generate = staticmethod(build_output)

        result = run(chunks, semantic, generator=UsageGenerator(), pricing=PRICING)
        assert result.answer.evidence_kind == "injected"
        assert result.cost.is_actual
        assert result.cost.usage is result.answer.usage
        assert result.cost.cost_usd == Decimal("0.00045")


class TestStageFailures:
    def test_blank_query_fails_at_dynamic_retrieval(self, chunks, semantic) -> None:
        with pytest.raises(HybridRagStageFailure) as caught:
            run(chunks, semantic, query="   ")
        assert caught.value.stage == "dynamic_retrieval"
        assert caught.value.analysis.stage is Stage.RETRIEVAL
        assert caught.value.analysis.category is Category.RETRIEVAL

    def test_semantic_failure_fails_at_retrieval(self, chunks) -> None:
        with pytest.raises(HybridRagStageFailure) as caught:
            run(chunks, FailingSemantic())
        assert caught.value.stage == "retrieval"
        assert caught.value.analysis.category is Category.RETRIEVAL
        assert isinstance(caught.value.__cause__, SemanticProviderError)

    def test_scorer_failure_fails_at_reranking(self, chunks, semantic) -> None:
        with pytest.raises(HybridRagStageFailure) as caught:
            run(chunks, semantic, scorer=FailingScorer())
        assert caught.value.analysis.category is Category.RERANKING
        assert isinstance(caught.value.__cause__, RerankScorerError)
        assert SECRET not in str(caught.value)

    def test_generator_failure_is_sanitized(self, chunks, semantic) -> None:
        generator = StubGenerator(error=RuntimeError(SECRET))
        with pytest.raises(HybridRagStageFailure) as caught:
            run(chunks, semantic, generator=generator)
        failure = caught.value
        assert failure.stage == "generation"
        assert failure.analysis.category is Category.GENERATION
        assert failure.analysis.fatal and not failure.analysis.result_usable
        assert isinstance(failure.__cause__, GenerationError)
        assert failure.__cause__.__cause__ is None
        assert SECRET not in str(failure) and SECRET not in str(failure.__cause__)

    def test_fabricated_citation_fails_at_generation(self, chunks, semantic) -> None:
        generator = StubGenerator(GeneratorOutput("Made up [1].", ("forged-id",)))
        with pytest.raises(HybridRagStageFailure) as caught:
            run(chunks, semantic, generator=generator)
        assert caught.value.analysis.category is Category.GENERATION

    def test_invalid_generator_fails_at_generation(self, chunks, semantic) -> None:
        with pytest.raises(HybridRagStageFailure) as caught:
            run(chunks, semantic, generator=object())
        assert caught.value.stage == "generation"

    def test_exhausted_clock_is_classified_other(self, chunks, semantic) -> None:
        with pytest.raises(HybridRagStageFailure) as caught:
            run(chunks, semantic, clock=FakeClock((0.0, 1.0, 2.0)))
        assert caught.value.stage == "retrieval"
        assert caught.value.analysis.category is Category.OTHER


class TestConfiguration:
    @pytest.mark.parametrize(
        "kwargs",
        [
            {"dynamic_policy": None},
            {"context_filter": {"max_candidates": 1}},
        ],
        ids=["policy", "filter"],
    )
    def test_rejects_wrong_typed_settings(self, kwargs) -> None:
        with pytest.raises(HybridRagError):
            HybridRagConfig(**kwargs)

    def test_rejects_invalid_rrf_k(self) -> None:
        with pytest.raises(HybridConfigurationError):
            HybridRagConfig(rrf_k=-1.0)

    def test_rejects_wrong_config_and_pricing(self, chunks, semantic) -> None:
        with pytest.raises(HybridRagError, match="HybridRagConfig"):
            run(chunks, semantic, config=ContextFilterConfig())
        with pytest.raises(HybridRagError, match="PricingConfig"):
            run(chunks, semantic, pricing={"model": "x"})


class TestResultValidation:
    def test_rejects_broken_stage_link(self, chunks, semantic) -> None:
        first = run(chunks, semantic)
        other = run(chunks, semantic)
        with pytest.raises(HybridRagError, match="exact input"):
            dataclasses.replace(first, context=other.context)

    def test_rejects_mismatched_query(self, chunks, semantic) -> None:
        result = run(chunks, semantic)
        with pytest.raises(HybridRagError, match="same query"):
            dataclasses.replace(result, query="a different query")

    def test_rejects_missing_stage_timing(self, chunks, semantic) -> None:
        result = run(chunks, semantic)
        partial = dataclasses.replace(
            result.latency, stages=result.latency.stages[:4]
        )
        with pytest.raises(HybridRagError, match="orchestrated stages"):
            dataclasses.replace(result, latency=partial)

    def test_rejects_wrong_stage_types(self, chunks, semantic) -> None:
        result = run(chunks, semantic)
        with pytest.raises(HybridRagError, match="every stage"):
            dataclasses.replace(result, answer=result.answer.text)
        with pytest.raises(HybridRagError, match="CostEvaluation"):
            dataclasses.replace(result, cost=Decimal("1"))


class TestDownstreamEvaluationAndTracing:
    async def test_genuine_ragas_scores_pipeline_answer(self, chunks, semantic) -> None:
        config = HybridRagConfig(
            context_filter=ContextFilterConfig(min_rerank_score=0.05, max_candidates=1)
        )
        result = run(chunks, semantic, config=config)
        reference = "Apples are picked by hand at dawn."
        case = to_evaluation_case(result, case_id="story-10", reference=reference)
        assert case.filtered_context is result.context
        assert case.contexts[0] is result.context.items[0].chunk
        assert case.response == result.answer.text
        judge = build_replay_judge(
            case,
            statements=(result.answer.text,),
            statement_verdicts=(1,),
            context_verdicts=(1,),
            generated_question=QUERY,
        )
        evaluation = await RagasEvaluator(judge, HashEmbedder()).evaluate(case)
        assert evaluation.case is case
        assert evaluation.evidence_kind == "deterministic_offline"
        assert evaluation.scores.faithfulness == pytest.approx(1.0)
        assert evaluation.scores.context_precision == pytest.approx(1.0)

    def test_latency_report_feeds_offline_langsmith_trace(
        self, chunks, semantic
    ) -> None:
        result = run(chunks, semantic)
        transport = OfflineTransport()
        evidence = LangSmithTracer(transport).trace(result.latency)
        assert evidence.success is True
        assert evidence.latency is result.latency
        assert len(evidence.child_ids) == len(STAGES)
        sent = json.dumps([record[2] for record in transport.records])
        assert "picked" not in sent and QUERY not in sent

    def test_rejects_wrong_result_type(self) -> None:
        with pytest.raises(HybridRagError, match="HybridRagResult"):
            to_evaluation_case(object(), case_id="c", reference="r")


def test_workflow_demo_runs_offline() -> None:
    path = MODULE_ROOT / "examples/hybrid_rag_workflow.py"
    script = (
        "import socket,runpy; "
        "socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw("
        "AssertionError('network')); "
        f"runpy.run_path({str(path)!r},run_name='__main__')"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    assert "retrieval from_cache=False" in result.stdout
    assert "retrieval from_cache=True" in result.stdout
    assert "They are picked by hand at dawn. [1]" in result.stdout
    assert "cost (estimated)" in result.stdout


class TestRule44Isolation:
    def test_story_10_files_import_no_earlier_module(self) -> None:
        for relative in NEW_FILES:
            tree = ast.parse((MODULE_ROOT / relative).read_text(encoding="utf-8"))
            names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names.update(a.name.split(".")[0] for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names.add((node.module or "").split(".")[0])
            assert not names & FORBIDDEN, relative

    def test_pipeline_import_loads_no_earlier_module(self) -> None:
        script = (
            "import json, sys\n"
            "import advanced_rag_evaluation.advanced_rag_pipeline\n"
            "import advanced_rag_evaluation.generation\n"
            "print(json.dumps(sorted({m.split('.')[0] for m in sys.modules} & "
            f"set({sorted(FORBIDDEN)!r}))))\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
            timeout=180,
        )
        assert json.loads(result.stdout.strip().splitlines()[-1]) == []
