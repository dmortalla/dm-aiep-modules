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
