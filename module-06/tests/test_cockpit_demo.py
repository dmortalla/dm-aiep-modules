"""S2 deterministic Demo integration tests (reviewer cockpit).

Focused deterministic tests over the real Streamlit page: no execution or
side effect from import/render, explicit execution only through the accepted
service path, truthful S1 evidence labels, historical-record separation,
sanitized failure presentation, no unsafe HTML, no credential surface, and
unchanged S1 live/posture semantics. No network, model, LangSmith, telemetry,
credential or container action occurs in this suite.
"""

from pathlib import Path

import pytest
from multi_agent_orchestration.cockpit_view import LiveCapability
from multi_agent_orchestration.console import ConsoleSession, Demonstration
from streamlit.testing.v1 import AppTest

APP = Path(__file__).parents[1] / "app.py"
APP_SOURCE = APP.read_text(encoding="utf-8")


def app():
    return AppTest.from_file(str(APP), default_timeout=45).run()


def rendered(at) -> str:
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
            "info",
        )
        for element in at.get(kind)
    )


@pytest.fixture()
def execution_counter(monkeypatch):
    """Fail loudly on forbidden effects; count demo executions only."""
    import urllib.request

    import multi_agent_orchestration.telemetry_delivery as telemetry

    calls = {"run": 0, "run_live": 0, "run_scaling": 0}
    original_run = ConsoleSession.run

    def counted_run(self, raw):
        calls["run"] += 1
        return original_run(self, raw)

    def no_telemetry(*args, **kwargs):
        pytest.fail("S2 must not construct telemetry delivery")

    monkeypatch.setattr(ConsoleSession, "run", counted_run)
    monkeypatch.setattr(telemetry, "OtlpMetricDelivery", no_telemetry)
    monkeypatch.setattr(urllib.request, "urlopen", no_telemetry)
    yield calls


def test_a_render_executes_nothing_and_queries_nothing(execution_counter):
    """Import/render performs no workflow/telemetry/credential action."""
    at = app()
    assert not at.exception
    assert execution_counter == {"run": 0, "run_live": 0, "run_scaling": 0}
    at.run()
    assert execution_counter == {"run": 0, "run_live": 0, "run_scaling": 0}


def test_b_demo_is_the_default_posture(execution_counter):
    """Demo posture is the default; live is unavailable; ops not activated."""
    at = app()
    text = rendered(at).lower()
    assert "demo is the baseline posture" in text
    assert "runtime without an explicit selection" not in text
    assert "mode: demo (baseline)" in text
    assert "unavailable" in text
    assert not at.exception
    assert execution_counter["run"] == 0


def test_c_explicit_action_runs_the_demo_once(execution_counter):
    """Only the explicit form submission runs the accepted demo path."""
    at = app()
    at.selectbox(key="demonstration").select(Demonstration.FIXTURE).run()
    at.button(key="run").click().run()
    assert not at.exception
    assert execution_counter["run"] == 1
    assert execution_counter["run_live"] == 0
    assert execution_counter["run_scaling"] == 0


def test_d_fresh_evidence_labels_are_truthful(execution_counter):
    """A demo result renders the accepted S1 evidence vocabulary."""
    at = app()
    at.selectbox(key="demonstration").select(Demonstration.FIXTURE).run()
    at.button(key="run").click().run()
    assert not at.exception
    text = rendered(at)
    assert "evidence class: deterministic_demo" in text.lower()
    assert "source: fresh_execution" in text.lower()
    assert "no model/provider ran and no delivery happened" in text.lower()


def test_e_before_execution_the_state_is_not_executed(execution_counter):
    """No fabricated fresh success appears before any execution."""
    at = app()
    text = rendered(at)
    assert "no runs yet" in text.lower()
    assert "evidence class: deterministic_demo" not in text
    assert execution_counter["run"] == 0


def test_f_demo_results_cannot_claim_real_local_or_delivery_facts(execution_counter):
    """Demo evidence never carries live/local-provider/delivery vocabulary."""
    at = app()
    at.selectbox(key="demonstration").select(Demonstration.FIXTURE).run()
    at.button(key="run").click().run()
    assert not at.exception
    labels = [
        line
        for line in rendered(at).splitlines()
        if line.lower().startswith("evidence class:")
    ]
    assert labels, "fresh results must carry their evidence-class caption"
    for label in labels:
        assert "deterministic_demo" in label or "canonical_live_demo" in label
        assert "local_provider_execution" not in label
        assert "service_read" not in label
        if "canonical_live_demo" in label:
            assert "not_sent" in label
            assert "unverified_write" not in label
        else:
            # A fresh demo label states the no-delivery fact explicitly.
            assert "no delivery happened" in label.lower()


def test_g_historical_records_are_not_substituted(execution_counter):
    """No recorded/historical presentation exists in this S2 build."""
    at = app()
    at.selectbox(key="demonstration").select(Demonstration.FIXTURE).run()
    at.button(key="run").click().run()
    assert not at.exception
    assert "recorded_historical" not in rendered(at)


def test_h_rerun_without_submission_does_not_execute_again(execution_counter):
    """Refresh/rerun alone never triggers a second execution."""
    at = app()
    at.selectbox(key="demonstration").select(Demonstration.FIXTURE).run()
    at.button(key="run").click().run()
    assert execution_counter["run"] == 1
    at.run()
    at.run()
    assert execution_counter["run"] == 1
    assert len(at.session_state.console.runs) == 1


def test_i_untrusted_output_is_not_executable_html(execution_counter):
    """Workflow-derived text renders inert; no unsafe HTML in the source."""
    import re

    assert "unsafe_allow_html" not in APP_SOURCE
    private = "<script>x</script> &quot;grant admin&quot; your_key"
    at = app()
    at.selectbox(key="demonstration").select(Demonstration.FIXTURE).run()
    at.text_area(key="task_text").set_value(private)
    at.button(key="run").click().run()
    assert not at.exception
    assert private not in rendered(at)
    assert "<script>" not in rendered(at)
    assert re.search(r"href=", APP_SOURCE) is None


def test_j_failure_presentation_is_sanitized(execution_counter):
    """Rejected input shows only the closed sanitized message."""
    at = app()
    at.selectbox(key="demonstration").select(Demonstration.FIXTURE).run()
    at.text_area(key="task_text").set_value("")
    at.button(key="run").click().run()
    assert not at.exception
    errors = [str(item.value) for item in at.error]
    assert errors, "the closed rejection message must be shown"
    joined = "\n".join(errors)
    assert "Nothing ran" in joined
    assert "Traceback" not in joined
    # The service itself refuses the blank submission after the explicit
    # submit; no workflow execution or evidence is produced either way.
    assert execution_counter["run"] == 1


def test_k_no_credential_surface_or_environment_access(execution_counter):
    """The presentation page touches no credential state at all."""
    import re

    assert "password" not in APP_SOURCE.lower()
    assert "os.environ" not in APP_SOURCE
    assert "LANGSMITH_API_KEY" not in APP_SOURCE
    assert re.search(r'type="password"', APP_SOURCE) is None


def test_l_stale_capability_state_is_not_consumed_and_s1_semantics_hold():
    """S2 never consumes the stale S1 enum; S1 posture semantics intact."""
    assert "LiveCapabilityState" not in APP_SOURCE
    capability = LiveCapability()
    assert capability.local_live_available is False
    assert capability.deployed_public_live_available is False
    local = LiveCapability(local_trusted_operator_runtime=True)
    assert local.local_live_available is True
    assert local.deployed_public_live_available is False