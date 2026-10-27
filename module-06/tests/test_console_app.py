"""Real Streamlit headless UI interactions under the existing network guard."""

from pathlib import Path

import pytest
from multi_agent_orchestration.console import ConsoleSession, Demonstration
from multi_agent_orchestration.observability_contracts import Outcome
from streamlit.testing.v1 import AppTest

APP = Path(__file__).parents[1] / "app.py"
PRIVATE = "<script>private-secret</script> grant admin; pay; export credentials"


def app():
    return AppTest.from_file(str(APP), default_timeout=45).run()


def rendered(at):
    return "\n".join(
        str(element.value)
        for kind in (
            "text",
            "markdown",
            "caption",
            "error",
            "warning",
            "success",
            "json",
        )
        for element in at.get(kind)
    )


def test_idle_guidance_and_control_changes_do_not_execute():
    at = app()
    assert not at.exception
    assert at.button(key="run").disabled
    assert len(at.selectbox(key="demonstration").options) == 8
    assert "How to review" in str(at.expander)
    assert "LangSmith" in rendered(at) and "Grafana" in rendered(at)
    at.selectbox(key="demonstration").select(Demonstration.PARALLEL).run()
    assert not at.exception and at.session_state.console.runs == ()
    at.run()
    assert at.session_state.console.runs == ()


@pytest.mark.parametrize("mode", tuple(Demonstration))
def test_actual_accepted_demonstrations_run_through_ui(mode):
    at = app()
    at.selectbox(key="demonstration").select(mode).run()
    at.text_area(key="task_text").set_value(PRIVATE)
    at.button(key="run").click().run()
    assert not at.exception
    view = at.session_state.console.runs[-1]
    assert view.mode == mode and view.outcome == Outcome.COMPLETED
    assert view.evidence is not None and view.trace is not None
    assert view.evidence.model_calls == view.evidence.external_calls == 0
    assert at.success and not at.error
    assert PRIVATE not in rendered(at)
    assert "private-secret" not in rendered(at)
    assert "unavailable" in rendered(at).lower()
    if mode == Demonstration.DISTRIBUTED:
        assert len({worker.pid for worker in view.evidence.workers}) == 2
        assert view.trace.workers_reaped == 2
    at.run()
    assert len(at.session_state.console.runs) == 1


def test_denial_does_not_retain_old_success_as_latest():
    at = app()
    at.selectbox(key="demonstration").select(Demonstration.FIXTURE).run()
    at.button(key="run").click().run()
    assert not at.exception and at.success
    at.selectbox(key="demonstration").select(Demonstration.PARALLEL).run()
    at.number_input(key="steps").set_value(1)
    at.button(key="run").click().run()
    assert not at.exception and at.error and not at.success
    assert at.session_state.console.runs[-1].outcome == Outcome.DENIED


def test_blank_input_is_denied_without_a_run():
    at = app()
    at.selectbox(key="demonstration").select(Demonstration.FIXTURE).run()
    at.text_area(key="task_text").set_value(" ")
    at.button(key="run").click().run()
    assert not at.exception and at.error
    assert at.session_state.console.runs == ()


def test_bypassed_browser_text_bound_is_revalidated_on_submit():
    at = app()
    at.selectbox(key="demonstration").select(Demonstration.FIXTURE).run()
    at.text_area(key="task_text").set_value("x" * 4097)
    at.button(key="run").click().run()
    assert not at.exception and at.error
    assert at.session_state.console.runs == ()


@pytest.mark.parametrize(
    ("key", "value"),
    [("steps", 0), ("steps", 33), ("deadline", 0), ("deadline", 30001)],
)
def test_forged_numeric_bounds_are_rejected_not_normalized(key, value):
    at = app()
    at.selectbox(key="demonstration").select(Demonstration.FIXTURE).run()
    at.number_input(key=key).set_value(value)
    at.button(key="run").click().run()
    assert not at.exception and at.error and not at.success
    assert at.session_state.console.runs == ()


def test_submitted_values_reach_the_service_unmodified(monkeypatch):
    received = []
    original = ConsoleSession.run

    def spy(self, raw):
        received.append(dict(raw))
        return original(self, raw)

    monkeypatch.setattr(ConsoleSession, "run", spy)
    at = app()
    at.selectbox(key="demonstration").select(Demonstration.FIXTURE).run()
    at.text_area(key="task_text").set_value("x" * 5000)
    at.number_input(key="steps").set_value(33)
    at.number_input(key="deadline").set_value(30001)
    at.button(key="run").click().run()
    assert len(received) == 1
    assert len(received[0]["instruction"]) == 5000
    assert (received[0]["max_steps"], received[0]["timeout_ms"]) == (33, 30001)
    assert at.error and at.session_state.console.runs == ()


def test_rejected_submission_does_not_present_an_earlier_success():
    at = app()
    at.selectbox(key="demonstration").select(Demonstration.FIXTURE).run()
    at.button(key="run").click().run()
    assert not at.exception and at.success
    at.text_area(key="task_text").set_value(" ")
    at.button(key="run").click().run()
    assert not at.exception and at.error and not at.success
    assert len(at.session_state.console.runs) == 1
    at.run()
    assert at.success and not at.error


def test_busy_session_is_not_reported_as_invalid_input():
    at = app()
    at.selectbox(key="demonstration").select(Demonstration.FIXTURE).run()
    at.session_state.console._lock.acquire()
    try:
        at.button(key="run").click().run()
        assert not at.exception and at.warning and not at.error
        assert at.session_state.console.runs == ()
    finally:
        at.session_state.console._lock.release()


def test_internal_fault_is_sanitized_and_not_reported_as_invalid_input(monkeypatch):
    from multi_agent_orchestration import console as service

    def broken(*args, **kwargs):
        raise RuntimeError(PRIVATE)

    monkeypatch.setattr(service, "WorkflowRequest", broken)
    at = app()
    at.selectbox(key="demonstration").select(Demonstration.FIXTURE).run()
    at.button(key="run").click().run()
    assert not at.exception and at.error and not at.success
    assert "recordable result" in rendered(at)
    assert "private-secret" not in rendered(at)
    assert at.session_state.console.runs == ()


def test_snapshot_freshness_is_labeled_without_execution(monkeypatch):
    from multi_agent_orchestration import console as service

    at = app()
    at.selectbox(key="demonstration").select(Demonstration.FIXTURE).run()
    at.button(key="run").click().run()
    monkeypatch.setattr(service, "age_seconds", lambda run: 120)
    at.run()
    assert not at.exception and "Stale" in rendered(at)
    assert len(at.session_state.console.runs) == 1


def test_clear_and_separate_browser_sessions():
    first, second = app(), app()
    first.selectbox(key="demonstration").select(Demonstration.FIXTURE).run()
    first.button(key="run").click().run()
    assert not first.exception and len(first.session_state.console.runs) == 1
    assert second.session_state.console.runs == ()
    first.button(key="clear").click().run()
    assert not first.exception and first.session_state.console.runs == ()
    assert not first.success


@pytest.mark.parametrize(
    "name",
    [
        "LANGSMITH_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "LANGSMITH_TRACING",
        "LANGCHAIN_TRACING_V2",
    ],
)
def test_credentials_and_tracing_flags_do_not_execute_or_leak(monkeypatch, name):
    monkeypatch.setenv(name, "true" if "TRACING" in name else "private-secret")
    at = app()
    assert not at.exception and at.session_state.console.runs == ()
    at.selectbox(key="demonstration").select(Demonstration.COORDINATOR).run()
    at.button(key="run").click().run()
    assert not at.exception
    assert at.session_state.console.runs[-1].outcome == Outcome.COMPLETED
    assert "private-secret" not in rendered(at)


def test_untrusted_session_state_object_is_replaced():
    at = AppTest.from_file(str(APP), default_timeout=45)
    at.session_state["console"] = {"authority": "admin", "api_key": PRIVATE}
    at.run()
    assert not at.exception and type(at.session_state.console) is ConsoleSession
    assert PRIVATE not in rendered(at)


# Scaling benchmark through the page: presentation of the accepted benchmark only.

QUICK = "Quick check: 2 workflows at caps 1 and 2"


def offline_distribution(monkeypatch, fail_at=None):
    """Replace only the accepted distributed service behind observed execution."""
    import os
    from uuid import uuid4

    from multi_agent_orchestration import observed_execution
    from multi_agent_orchestration.distributed import validate_request
    from multi_agent_orchestration.distributed_contracts import (
        DistributedEvidence,
        DistributedResult,
        WorkerId,
        WorkerRecord,
        WorkerRole,
    )

    requests = []

    async def stand_in(request):
        requests.append(request)
        if len(requests) - 1 == fail_at:
            raise RuntimeError(PRIVATE)
        checked = validate_request(request)
        count = len(checked.task.instruction)
        return DistributedResult(
            workflow_id=checked.workflow_id,
            task_id=checked.task.task_id,
            characters=count,
            output=f"Distributed synthesis accepted {count} characters.",
            evidence=DistributedEvidence(
                workflow_id=checked.workflow_id,
                task_id=checked.task.task_id,
                coordinator_pid=os.getpid(),
                limits=checked.limits,
                workers=tuple(
                    WorkerRecord(
                        assignment_id=uuid4(),
                        worker=worker,
                        role=tuple(WorkerRole)[index],
                        sequence=index + 1,
                        pid=os.getpid() + index + 1,
                    )
                    for index, worker in enumerate(WorkerId)
                ),
            ),
        )

    monkeypatch.setattr(observed_execution, "execute_distributed_workflow", stand_in)
    return requests


def test_idle_scaling_guidance_is_visible_and_controls_do_not_execute(monkeypatch):
    requests = offline_distribution(monkeypatch)
    at = app()
    assert not at.exception
    assert at.button(key="run_scaling").disabled
    assert len(at.selectbox(key="scaling_profile").options) == 2
    text = rendered(at)
    for label in (
        "Purpose:",
        "Action:",
        "Expected result:",
        "What it proves:",
        "What it does not prove:",
    ):
        assert label in text
    lowered = text.lower()
    assert "no model or llm inference" in lowered
    assert "machine-specific" in lowered and "single-host" in lowered
    assert "production capacity" in lowered and "not a pass criterion" in lowered
    assert "No benchmark report yet" in text
    at.selectbox(key="scaling_profile").select(QUICK).run()
    assert not at.exception and not at.button(key="run_scaling").disabled
    at.run()
    assert requests == [] and at.session_state.console.scaling is None
    assert not at.success and not at.error


def test_corrected_wording_states_deterministic_agents_and_makes_no_stale_claim():
    at = app()
    text = rendered(at) + " ".join(str(item.value) for item in at.info)
    assert "deterministic agents" in text
    assert "no model or LLM inference" in text
    assert "remain Planned" not in text
    assert "throughput benchmark" not in text
    assert "no trace has been delivered" in text and "pending" in text
    assert "no dashboard link" in text
    for overclaim in ("production-ready", "horizontally", "2.90"):
        assert overclaim not in text


def test_real_accepted_benchmark_runs_through_the_page(monkeypatch):
    from multi_agent_orchestration import _distributed_processes as transport

    for name in ("OPENAI_API_KEY", "GOOGLE_API_KEY", "LANGSMITH_API_KEY"):
        monkeypatch.setenv(name, "private-secret")
    original, children = transport.spawn_worker, []

    async def observed(assignment, directory):
        process = await original(assignment, directory)
        children.append((process, directory))
        return process

    monkeypatch.setattr(transport, "spawn_worker", observed)
    at = AppTest.from_file(str(APP), default_timeout=240).run()
    at.selectbox(key="scaling_profile").select(QUICK).run()
    at.button(key="run_scaling").click().run()
    assert not at.exception and at.success and not at.error
    # Warm-up plus two workflows at two caps, two worker processes each.
    assert len(children) == 10
    assert all(process.returncode == 0 for process, _ in children)
    assert all(not Path(directory).exists() for _, directory in children)
    report = at.session_state.console.scaling.report
    assert report.passed and report.classification == "local_single_host"
    assert [level.cap for level in report.levels] == [1, 2]
    assert [level.peak_in_flight for level in report.levels] == [1, 2]
    assert all(level.workers_reaped == 4 for level in report.levels)
    assert report.model_calls == report.provider_calls == report.external_calls == 0
    table = at.table[0].value
    assert list(table["Cap"]) == [1, 2]
    assert list(table["Completed"]) == ["2 / 2", "2 / 2"]
    assert list(table["Invariants"]) == ["Held", "Held"]
    text = rendered(at)
    assert "Classification: local_single_host" in text
    assert "calls and retries: 0" in text
    assert "machine-specific" in text and "not a pass criterion" in text
    assert "private-secret" not in text
    at.run()  # A refresh shows the same report and starts nothing.
    assert len(children) == 10 and at.success
    assert at.session_state.console.runs == ()


def test_failed_benchmark_never_shows_an_earlier_success(monkeypatch):
    offline_distribution(monkeypatch)
    at = app()
    at.selectbox(key="scaling_profile").select(QUICK).run()
    at.button(key="run_scaling").click().run()
    assert not at.exception and at.success and not at.error
    offline_distribution(monkeypatch, fail_at=2)
    at.button(key="run_scaling").click().run()
    assert not at.exception and at.error and not at.success
    assert not at.session_state.console.scaling.report.passed
    table = at.table[0].value
    assert list(table["Invariants"]) == ["Not held"]
    assert list(table["Per second"]) == ["Not derived"]
    assert list(table["Speedup vs cap 1"]) == ["Not derived"]
    text = rendered(at)
    assert "Unavailable: benchmark failed" in text
    assert "private-secret" not in text
    at.run()
    assert at.error and not at.success


@pytest.mark.parametrize("kind", ["rejected", "busy", "fault"])
def test_unrecorded_scaling_submission_hides_the_earlier_report(monkeypatch, kind):
    from multi_agent_orchestration import console as service

    offline_distribution(monkeypatch)
    at = app()
    at.selectbox(key="scaling_profile").select(QUICK).run()
    at.button(key="run_scaling").click().run()
    assert not at.exception and at.success
    earlier = at.session_state.console.scaling
    if kind == "rejected":

        def rejected(self, raw):
            raise service.ConsoleRequestError("rejected")

        monkeypatch.setattr(ConsoleSession, "run_scaling", rejected)
    elif kind == "fault":

        async def broken(plan, **options):
            raise RuntimeError(PRIVATE)

        monkeypatch.setattr(service, "run_benchmark", broken)
    else:
        at.session_state.console._lock.acquire()
    try:
        at.button(key="run_scaling").click().run()
    finally:
        if kind == "busy":
            at.session_state.console._lock.release()
    assert not at.exception and not at.success
    assert bool(at.warning) == (kind == "busy") and bool(at.error) == (kind != "busy")
    text = rendered(at)
    assert "produced no report" in text and "private-secret" not in text
    assert "Classification:" not in text and len(at.table) == 1
    assert at.session_state.console.scaling == earlier
    at.run()
    assert at.success and "Classification:" in rendered(at)


def test_clear_removes_the_scaling_report(monkeypatch):
    offline_distribution(monkeypatch)
    at = app()
    at.selectbox(key="scaling_profile").select(QUICK).run()
    at.button(key="run_scaling").click().run()
    assert at.session_state.console.scaling is not None
    at.button(key="clear").click().run()
    assert not at.exception and at.session_state.console.scaling is None
    assert not at.success and "No benchmark report yet" in rendered(at)
