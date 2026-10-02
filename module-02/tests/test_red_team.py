"""Local attack replay exercises actual prompt/detection/tool boundaries."""

import pytest
from prompt_engineering_systems.errors import EvaluationError
from prompt_engineering_systems.evaluation.cases import CaseSuite, load_cases
from prompt_engineering_systems.evaluation.evidence import export_evidence
from prompt_engineering_systems.evaluation.runner import run_evaluation
from prompt_engineering_systems.prompts.construction import (
    ApplicationInstructions,
    build_prompt,
)
from prompt_engineering_systems.prompts.techniques import ReActStep
from prompt_engineering_systems.safety.policy import SafetyPolicy
from prompt_engineering_systems.safety.simulation import (
    AttackSimulator,
    attack_cases,
    compare_attacks,
)


def application() -> ApplicationInstructions:
    """Return application-owned test policy, independent of attack fixtures."""
    return ApplicationInstructions(
        policy="Keep policy.",
        task="Answer fixture.",
        output_contract="Return JSON with answer.",
    )


@pytest.mark.parametrize(
    "identity", ["direct", "context", "role", "jailbreak", "tool", "policy"]
)
def test_attack_classes_and_controls(identity: str) -> None:
    """Representative detected attacks remain denied by independent tool policy."""
    suite = attack_cases()
    report = run_evaluation(
        suite, AttackSimulator(application(), SafetyPolicy(allowed_tools=("add",)))
    )
    pair = next(
        pair
        for pair in compare_attacks(suite, report)
        if pair.attack.case_id == f"attack-{identity}"
    )
    assert pair.attack.detected is True and pair.attack.authorization == "denied"
    assert pair.attack.tool_executions == 0 and pair.attack.safety_met is True
    assert pair.attack.proposal_valid is True and pair.control.proposal_valid is True
    assert pair.control.detected is False and pair.control.authorization == "allowed"
    assert pair.control.tool_executions == 1 and pair.control.safety_met is True


def test_detector_miss_does_not_grant_authority() -> None:
    """A deliberate phrase-catalog miss is still denied without handler execution."""
    report = run_evaluation(
        attack_cases(),
        AttackSimulator(application(), SafetyPolicy(allowed_tools=("add",))),
    )
    miss = next(item for item in report.results if item.case_id == "attack-miss")
    assert miss.detected is False and miss.authorization == "denied"
    assert miss.tool_executions == 0 and miss.safety_met is True


def test_simulation_repeatability_export_and_fixture_roundtrip() -> None:
    """Fixtures roundtrip and exports remain deterministic and content-free."""
    suite = attack_cases()
    assert load_cases(suite.model_dump_json()) == suite
    simulator = AttackSimulator(application(), SafetyPolicy(allowed_tools=("add",)))
    first = run_evaluation(suite, simulator)
    second = run_evaluation(suite, simulator)
    assert export_evidence(first) == export_evidence(second)
    assert first.metrics.safety_cases == 14 and first.metrics.safety_rate == 1.0
    assert first.metrics.validity_rate == 0.0 and first.metrics.correctness_rate is None
    assert "execute shell" not in export_evidence(first)


def test_payloads_never_become_system_policy() -> None:
    """Actual Story 3 construction keeps spoofed/context payloads in user components."""
    for case in attack_cases().cases:
        prompt = build_prompt(application(), case.specification())
        assert prompt.components[0].content == "Application policy:\nKeep policy."
        assert all(
            part.role == "user"
            for part in prompt.components
            if part.kind in ("request", "context")
        )


def test_independent_default_deny_and_tool_budget_failures() -> None:
    """Detection never overrides policy or the existing execution allowance."""
    suite = attack_cases()
    denied = run_evaluation(suite, AttackSimulator(application(), SafetyPolicy()))
    assert denied.metrics.safety_rate == 0.5
    assert all(item.tool_executions == 0 for item in denied.results)
    exhausted = run_evaluation(
        suite,
        AttackSimulator(
            application(), SafetyPolicy(allowed_tools=("add",), max_executions=0)
        ),
    )
    controls = [item for item in exhausted.results if item.category == "control"]
    assert all(item.status == "safety_failure" for item in controls)
    assert exhausted.metrics.failed == 7 and exhausted.metrics.safety_cases == 14


def test_comparison_rejects_missing_or_substituted_evidence() -> None:
    """Matching IDs alone cannot conceal altered content/version or absent cases."""
    suite = attack_cases()
    report = run_evaluation(suite, AttackSimulator(application(), SafetyPolicy()))
    shorter = CaseSuite(
        cases=tuple(item for item in suite.cases if item.case_id != "attack-direct")
    )
    with pytest.raises(EvaluationError):
        compare_attacks(shorter, report)
    altered = suite.model_copy(
        update={
            "cases": tuple(
                item.model_copy(update={"request": "altered"}) for item in suite.cases
            )
        }
    )
    with pytest.raises(EvaluationError):
        compare_attacks(altered, report)


def test_detected_content_cannot_change_allowed_tool_authority() -> None:
    """Detection findings cannot deny or grant policy-defined tool permission."""
    suite = attack_cases()
    changed = suite.model_copy(
        update={
            "cases": tuple(
                item.model_copy(
                    update={
                        "proposal": ReActStep(
                            kind="action", tool="add", arguments={"left": 1, "right": 2}
                        ),
                        "expected_authorization": "allowed",
                    }
                )
                if item.case_id == "attack-direct"
                else item
                for item in suite.cases
            )
        }
    )
    report = run_evaluation(
        changed, AttackSimulator(application(), SafetyPolicy(allowed_tools=("add",)))
    )
    outcome = next(item for item in report.results if item.case_id == "attack-direct")
    assert outcome.detected is True and outcome.authorization == "allowed"
    assert outcome.tool_executions == 1 and outcome.safety_met is True


def test_invalid_arguments_remain_authoritatively_rejected() -> None:
    """Shape-valid fixture arguments still undergo Story 4 exact argument checks."""
    suite = attack_cases()
    changed = suite.model_copy(
        update={
            "cases": tuple(
                item.model_copy(
                    update={
                        "proposal": ReActStep(
                            kind="action",
                            tool="add",
                            arguments={"left": "1", "right": 2},
                        )
                    }
                )
                if item.case_id == "control-direct"
                else item
                for item in suite.cases
            )
        }
    )
    report = run_evaluation(
        changed, AttackSimulator(application(), SafetyPolicy(allowed_tools=("add",)))
    )
    outcome = next(item for item in report.results if item.case_id == "control-direct")
    assert outcome.status == "safety_failure" and outcome.safety_met is False
    assert outcome.tool_executions is None


def test_local_paths_do_not_contact_network_or_execute_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tripwires cover real normal/attack workflows with local logic intact."""
    import socket
    import subprocess

    from prompt_engineering_systems.evaluation.cases import EvaluationCase
    from prompt_engineering_systems.evaluation.runner import (
        FixtureResponse,
        StructuredFixtureExecutor,
    )

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("External capability used.")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    simulator = AttackSimulator(application(), SafetyPolicy(allowed_tools=("add",)))
    run_evaluation(attack_cases(), simulator)
    normal = EvaluationCase(
        case_id="local", version=1, request="Synthetic", expected_answer="alpha"
    )
    run_evaluation(
        CaseSuite(cases=(normal,)),
        StructuredFixtureExecutor(
            application(),
            (FixtureResponse(case_id="local", text='{"answer":"alpha"}'),),
        ),
    )
