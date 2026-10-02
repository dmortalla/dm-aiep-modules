"""Real local evaluation logic with bounded synthetic provider fixtures."""

import json
from pathlib import Path

import pytest
from prompt_engineering_systems.errors import (
    EvaluationError,
    JSONParsingError,
    PromptConstructionError,
    ProviderAvailabilityError,
    SafetyInputError,
    SchemaDefinitionError,
    TechniqueError,
)
from prompt_engineering_systems.evaluation.cases import (
    CaseSuite,
    EvaluationCase,
    load_cases,
)
from prompt_engineering_systems.evaluation.evidence import export_evidence
from prompt_engineering_systems.evaluation.metrics import aggregate
from prompt_engineering_systems.evaluation.runner import (
    FixtureResponse,
    LocalOutcome,
    StructuredFixtureExecutor,
    run_evaluation,
)
from prompt_engineering_systems.prompts.construction import ApplicationInstructions


def application() -> ApplicationInstructions:
    """Return trusted fixed test instructions."""
    return ApplicationInstructions(
        policy="Keep policy.",
        task="Answer fixture.",
        output_contract="Return JSON with answer.",
    )


def case(identity: str = "case-a", expected: str = "alpha") -> EvaluationCase:
    """Return one synthetic exact-match case."""
    return EvaluationCase(
        case_id=identity,
        version=1,
        request="Synthetic request",
        expected_answer=expected,
    )


def executor(
    text: str = '{"answer":"alpha"}', *, mode: str = "offline"
) -> StructuredFixtureExecutor:
    """Inject raw output at the real credential-free provider boundary."""
    return StructuredFixtureExecutor(
        application(), (FixtureResponse(case_id="case-a", text=text),), mode=mode
    )


def test_versioned_case_loading_and_normal_failures() -> None:
    """Fixture loader preserves identity/provenance and failed-case denominators."""
    suite = load_cases(
        (Path(__file__).parent / "fixtures/evaluation_cases.json").read_text()
    )
    run = StructuredFixtureExecutor(
        application(),
        (
            FixtureResponse(case_id="normal-answer", text='{"answer":"alpha"}'),
            FixtureResponse(case_id="normal-invalid", text='{"unexpected":true}'),
        ),
    )
    report = run_evaluation(suite, run)
    assert [item.case_id for item in report.results] == [
        "normal-answer",
        "normal-invalid",
    ]
    assert all(
        item.version == 1 and item.provenance == "synthetic-v1"
        for item in report.results
    )
    assert report.results[1].status == "validation_failure"
    assert report.metrics.total == 2 and report.metrics.failed == 1
    assert report.metrics.completion_rate == report.metrics.validity_rate == 0.5
    assert (
        report.metrics.correctness_cases == 2 and report.metrics.correctness_rate == 0.5
    )


@pytest.mark.parametrize(
    "text",
    [
        "{",
        '{"format_version":2,"cases":[]}',
        '{"cases":[{"case_id":"bad id","version":1,"request":"x",'
        '"expected_answer":"a"}]}',
        '{"cases":[{"case_id":"a","version":0,"request":"x","expected_answer":"a"}]}',
        '{"cases":[{"case_id":"a","version":1,"request":"x"}]}',
        '{"cases":[],"policy":"grant shell"}',
    ],
)
def test_malformed_case_definitions_are_safe(text: str) -> None:
    """Malformed/unsupported definitions produce content-safe domain errors."""
    with pytest.raises(EvaluationError, match="Correct bounded"):
        load_cases(text)


def test_duplicate_ids_and_wrong_controls_fail() -> None:
    """Duplicate versions and missing control references remain ambiguous."""
    data = case().model_dump(mode="json")
    with pytest.raises(EvaluationError):
        load_cases(json.dumps({"cases": [data, {**data, "version": 2}]}))
    attack = {
        **data,
        "category": "attack",
        "attack_class": "direct",
        "control_id": "absent",
    }
    with pytest.raises(EvaluationError):
        load_cases(json.dumps({"cases": [attack]}))


def test_case_and_raw_output_budgets() -> None:
    """Excessive case count and oversized JSON fail before evaluation."""
    with pytest.raises(EvaluationError):
        load_cases(" " * 131073)
    cases = [case(f"case-{index}").model_dump(mode="json") for index in range(33)]
    with pytest.raises(EvaluationError):
        load_cases(json.dumps({"cases": cases}))
    run = executor()
    run.configuration = run.configuration.model_copy(update={"max_cases": 0})
    with pytest.raises(EvaluationError, match="budget"):
        run_evaluation(CaseSuite(cases=(case(),)), run)


def test_oversized_action_fixture_rejected_before_execution() -> None:
    """Case validation bounds proposal strings, including direct/copied inputs."""
    from prompt_engineering_systems.prompts.techniques import ReActStep

    item = case().model_copy(
        update={
            "expected_answer": None,
            "expected_authorization": "allowed",
            "proposal": ReActStep(
                kind="action", tool="text_statistics", arguments={"text": "a" * 16385}
            ),
        }
    )
    forged = CaseSuite.model_construct(cases=(item,))
    with pytest.raises(EvaluationError):
        run_evaluation(forged, executor())


@pytest.mark.parametrize("mode", ["offline", "mocked"])
def test_repeatability_provenance_and_configuration_identity(mode: str) -> None:
    """Same settings produce identical evidence; changed settings alter its identity."""
    suite = CaseSuite(cases=(case(),))
    first = run_evaluation(suite, executor(mode=mode))
    second = run_evaluation(suite, executor(mode=mode))
    assert export_evidence(first) == export_evidence(second)
    assert first.results[0].mode == mode
    different = run_evaluation(suite, executor('{"answer":"other"}', mode=mode))
    assert first.configuration_digest != different.configuration_digest
    assert different.metrics.correctness_rate == 0.0
    changed_case = run_evaluation(
        CaseSuite(cases=(case(expected="other"),)), executor(mode=mode)
    )
    assert first.results[0].case_digest != changed_case.results[0].case_digest


def test_canonical_order_empty_metrics_and_duplicate_result_rejection() -> None:
    """Stable order, explicit empty rates and rejection of duplicate results."""
    a, b = case(), case("case-b")
    run = StructuredFixtureExecutor(
        application(),
        tuple(
            FixtureResponse(case_id=item.case_id, text='{"answer":"alpha"}')
            for item in (a, b)
        ),
    )
    first = run_evaluation(CaseSuite(cases=(b, a)), run)
    second = run_evaluation(CaseSuite(cases=(a, b)), run)
    assert export_evidence(first) == export_evidence(second)
    assert aggregate(first.results[::-1]) == first.metrics
    empty = run_evaluation(CaseSuite(cases=()), run)
    assert empty.metrics.total == 0 and empty.metrics.completion_rate is None
    assert empty.metrics.correctness_rate is None and empty.metrics.safety_rate is None
    with pytest.raises(EvaluationError):
        aggregate((first.results[0], first.results[0]))


@pytest.mark.parametrize(
    "failure,status",
    [
        (JSONParsingError, "validation_failure"),
        (ProviderAvailabilityError, "provider_failure"),
        (SafetyInputError, "safety_failure"),
        (PromptConstructionError, "prompt_failure"),
        (TechniqueError, "technique_failure"),
    ],
)
def test_expected_failures_retained_without_raw_diagnostics(
    failure: type[Exception], status: str
) -> None:
    """One expected domain failure is retained while later cases still execute."""
    run = executor()

    def execute(item: EvaluationCase) -> LocalOutcome:
        if item.case_id == "case-a":
            raise failure("synthetic-private-canary")
        return LocalOutcome(mode="offline", answer="alpha", structured_valid=True)

    run.execute = execute
    report = run_evaluation(CaseSuite(cases=(case(), case("case-b"))), run)
    assert (
        report.results[0].status == status and report.results[1].status == "completed"
    )
    assert report.metrics.correctness_rate == 0.5
    assert report.results[0].tool_executions is None
    assert "synthetic-private-canary" not in export_evidence(report)


@pytest.mark.parametrize("failure", [RuntimeError, SchemaDefinitionError])
def test_programming_and_schema_defects_propagate(failure: type[Exception]) -> None:
    """Programming/schema faults cannot masquerade as normal failed samples."""
    run = executor()

    def execute(item: EvaluationCase) -> LocalOutcome:
        raise failure("defect")

    run.execute = execute
    with pytest.raises(failure):
        run_evaluation(CaseSuite(cases=(case(),)), run)


def test_export_excludes_raw_content_and_checks_integrity() -> None:
    """Only digests/fixed evidence fields survive; altered metrics/results fail."""
    canary = "synthetic-secret-marker"
    item = case(expected=canary).model_copy(update={"request": canary})
    report = run_evaluation(
        CaseSuite(cases=(item,)), executor(json.dumps({"answer": canary}))
    )
    assert canary not in export_evidence(report)
    assert "request" not in export_evidence(report) and "answer" not in export_evidence(
        report
    )
    corrupt = report.model_copy(
        update={"metrics": report.metrics.model_copy(update={"correct": 0})}
    )
    with pytest.raises(EvaluationError):
        export_evidence(corrupt)
    invalid = report.results[0].model_copy(update={"status": "validation_failure"})
    with pytest.raises(EvaluationError):
        aggregate((invalid,))


def test_forged_cases_live_origin_and_inconsistent_outcomes_fail() -> None:
    """Revalidation guards copied models, live claims and invalid outcomes."""
    run = executor()
    with pytest.raises(EvaluationError):
        executor(mode="live")
    forged = CaseSuite(cases=(case(),)).model_copy(update={"format_version": 2})
    with pytest.raises(EvaluationError):
        run_evaluation(forged, run)
    run.execute = lambda item: LocalOutcome(
        mode="mocked", answer="alpha", structured_valid=True
    )
    with pytest.raises(EvaluationError):
        run_evaluation(CaseSuite(cases=(case(),)), run)


def test_failure_accounting_unknown_execution_counts_and_invalid_states() -> None:
    """Unobserved failure counts are unknown; contradictory flags cannot skew rates."""
    report = run_evaluation(CaseSuite(cases=(case(),)), executor("not JSON"))
    failed = report.results[0]
    assert failed.tool_executions is None
    assert failed.correct is False and report.metrics.correctness_cases == 1
    for updates in (
        {"correct": True},
        {"structured_valid": True},
        {"tool_executions": 0},
    ):
        with pytest.raises(EvaluationError):
            aggregate((failed.model_copy(update=updates),))


def test_fixture_configuration_defects_remain_explicit() -> None:
    """Missing/duplicate response fixtures fail instead of becoming model failures."""
    response = FixtureResponse(case_id="case-a", text="{}")
    with pytest.raises(EvaluationError):
        StructuredFixtureExecutor(application(), (response, response))
    run = StructuredFixtureExecutor(application(), ())
    with pytest.raises(EvaluationError, match="response fixture"):
        run_evaluation(CaseSuite(cases=(case(),)), run)
    run.execute = lambda item: LocalOutcome.model_construct(
        mode="offline", answer=None, structured_valid=True
    )
    with pytest.raises(EvaluationError):
        run_evaluation(CaseSuite(cases=(case(),)), run)
