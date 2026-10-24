"""S3 operational aggregation tests: A-T coverage from the S3 task.

Deterministic, offline tests: the app imports/renders with zero probes, the
explicit check action invokes the read-only boundary exactly once, reruns
never re-query, untrusted/malformed responses fail closed and sanitized, and
recorded historical evidence stays separate from fresh current-host
observations. No Docker, Prometheus, Grafana, Collector, network,
credential, model or LangSmith action occurs; all service responses in this
suite are test-owned injected values probing nothing.
"""

from pathlib import Path

import pytest
from multi_agent_orchestration import cockpit_ops
from multi_agent_orchestration.cockpit_ops import (
    ALERT_RULE_NAMES,
    GRAFANA_PORT,
    HOST,
    MODULE6_FINISHED_QUERY,
    PROMETHEUS_PORT,
    QUERY_TIMEOUT_S,
    LocalStackObservation,
    StoredOperationsObservation,
    query_local_stack,
)
from multi_agent_orchestration.cockpit_view import (
    CURATED_OPERATIONAL_PIPELINE,
    OperationsState,
    ViewSource,
)
from multi_agent_orchestration.console import ConsoleSession
from streamlit.testing.v1 import AppTest

APP = Path(__file__).parents[1] / "app.py"
APP_SOURCE = APP.read_text(encoding="utf-8")
OPERATIONS_SOURCE = Path(cockpit_ops.__file__).read_text(encoding="utf-8")


def app():
    return AppTest.from_file(str(APP), default_timeout=45).run()


def rendered(at) -> str:
    return "\n".join(
        str(element.value)
        for kind in ("text", "markdown", "caption", "error", "warning",
                     "success", "info", "subheader")
        for element in at.get(kind)
    )


def test_a_app_render_makes_zero_operational_requests(monkeypatch):
    """Import/render performs zero operational probes."""
    checked = {"queries": 0}

    def sentinel(*args, **kwargs):
        checked["queries"] += 1
        raise AssertionError("S3 must not probe on render")

    monkeypatch.setattr(cockpit_ops, "query_local_stack", sentinel)
    at = app()
    assert not at.exception
    at.run()
    assert checked["queries"] == 0


def test_b_operations_render_is_probe_free(monkeypatch):
    """Rendering the Operations tab without action performs zero probes."""
    sentinel_recorded = {"n": 0}

    def sentinel(*a, **k):
        sentinel_recorded["n"] += 1
        raise AssertionError("zero probes on tab render")

    monkeypatch.setattr(cockpit_ops, "query_local_stack", sentinel)
    at = app()
    assert not at.exception
    # The Operations tab content renders (recorded evidence plus not-
    # activated note) but no probe happened.
    assert "Recorded verification" in rendered(at)
    assert "Not activated" in rendered(at)
    assert sentinel_recorded["n"] == 0


def test_c_explicit_action_invokes_the_boundary_exactly_once(monkeypatch):
    """The explicit button triggers exactly one bounded read-only check."""
    calls = {"n": 0}
    production_reader = cockpit_ops._production_reader

    def counting(reader=production_reader):
        calls["n"] += 1
        raise AssertionError("test must not reach the network")

    monkeypatch.setattr(cockpit_ops, "query_local_stack", counting)
    at = app()
    assert at.button(key="ops_query").click().run()
    assert calls["n"] == 1
    assert "could not produce a validated observation" in rendered(at)


def test_d_rerender_does_not_re_query(monkeypatch):
    """Session-stored results persist; no probe on re-render."""
    import time as time_module

    observation = LocalStackObservation(
        query_state=OperationsState.RESULT,
        finished_total=14.0,
        alert_rules_loaded=3,
        grafana_healthy=True,
        dashboard_provisioned=True,
    )

    def fresh_result(reader=None):
        return observation

    monkeypatch.setattr(cockpit_ops, "query_local_stack", fresh_result)
    monkeypatch.setattr(time_module, "time_ns", lambda: 1)
    at = app()
    assert at.button(key="ops_query").click().run()
    assert not at.exception
    stored = at.session_state.console.operations
    assert stored.observation is not None
    monkeypatch.setattr(
        cockpit_ops, "query_local_stack",
        lambda reader=None: pytest.fail("S3 rerun must not re-query"))
    at.run()
    at.run()
    assert stored.observation.finished_total == 14.0


def test_f_fresh_query_labels_are_current_host_only(monkeypatch):
    """Successful fresh results are labelled fresh; not the recorded one."""
    import time as time_module

    observation = LocalStackObservation(
        query_state=OperationsState.RESULT,
        finished_total=5.0,
        alert_rules_loaded=3,
        grafana_healthy=True,
        dashboard_provisioned=True,
        dashboard_reference=f"http://{HOST}:{GRAFANA_PORT}/d/module6-operations",
    )

    def fresh_result(reader=None):
        return observation

    monkeypatch.setattr(cockpit_ops, "query_local_stack", fresh_result)
    monkeypatch.setattr(time_module, "time_ns", lambda: 1)
    at = app()
    assert at.button(key="ops_query").click().run()
    assert not at.exception
    text = rendered(at)
    # A successful fresh observation is labelled with its own freshness.
    assert "checked 0 s ago" in text.lower()
    assert "source: fresh_execution" in text.lower()
    # The accepted classification appears only in clearly recorded lines.
    for line in (
        ln
        for ln in text.splitlines()
        if "authorized deterministic local operational-telemetry" in ln
    ):
        assert "recorded_historical" in line or "recorded" in line.lower()
    # Fresh-marker lines never carry recorded material.
    for line in (ln for ln in text.splitlines() if "checked 0 s ago" in ln.lower()):
        assert "recorded_historical" not in line
        assert (
            "authorized deterministic local operational-telemetry" not in line
        )
    # The recorded block is still present and still labelled.
    assert any(
        "recorded_historical" in ln and "recorded" in ln.lower()
        for ln in text.splitlines()
    )


def test_e_default_state_is_not_activated(monkeypatch):
    session = ConsoleSession()
    assert session.operations is None
    at = app()
    assert "Not activated" in rendered(at)


def test_g_recorded_evidence_stays_recorded_with_exact_classification():
    """The curated operational record is untouched by fresh behavior."""
    record = CURATED_OPERATIONAL_PIPELINE
    assert record.source is ViewSource.RECORDED_HISTORICAL
    assert record.accepted_classification == (
        "authorized deterministic local operational-telemetry pipeline "
        "verification"
    )
    assert record.operational_classification == (
        "authorized deterministic local operational-telemetry pipeline "
        "verification"
    )
    assert record.execution_kind.value == "deterministic_demo"
    assert record.delivery_confirmation is None


def test_h_fresh_and_recorded_types_are_separate():
    """Data-model separation: observation vs curated history."""
    fresh = LocalStackObservation(query_state=OperationsState.RESULT)
    assert type(fresh) is not type(CURATED_OPERATIONAL_PIPELINE)
    fresh_contract = StoredOperationsObservation(happened_ns=1, observation=fresh)
    assert fresh_contract.observation is fresh
    assert fresh_contract.happened_ns == 1


def test_k_l_no_arbitrary_endpoint_or_query_input():
    """Fixed endpoints and fixed query; no caller URL/host/port surface."""
    import inspect

    signature = inspect.signature(query_local_stack)
    assert list(signature.parameters) == ["reader"]
    assert HOST == "127.0.0.1"
    assert PROMETHEUS_PORT == 9090 and GRAFANA_PORT == 3000
    assert MODULE6_FINISHED_QUERY == "sum(module6_workflow_finished_total)"
    assert tuple(ALERT_RULE_NAMES) == (
        "Module6CollectionBoundaryDown",
        "Module6ObservationLoss",
        "Module6WorkflowFailureRatioHigh",
    )
    for banned in ("iframe", "streamlit", "st.markdown"):
        assert banned not in OPERATIONS_SOURCE
    # Loopback-only transport: the opener ignores proxies by construction and
    # never trusts the ambient environment/proxy configuration.
    assert "ProxyHandler({})" in OPERATIONS_SOURCE


def test_n_query_timeout_is_bounded():
    """The production read timeout is a small fixed constant."""
    assert QUERY_TIMEOUT_S == 5
    assert "timeout=QUERY_TIMEOUT_S" in OPERATIONS_SOURCE
    assert "time.sleep" not in OPERATIONS_SOURCE
    assert "while " not in OPERATIONS_SOURCE


def test_o_malformed_responses_fail_safely():
    """Hostile or malformed payloads yield None fields, never exceptions."""
    payloads = [None, [], 42, {"status": "x"}, {"status": "success"}]
    calls = {"n": 0}

    def hostile(url, body=None):
        calls["n"] += 1
        return payloads[calls["n"] - 1]

    observation = query_local_stack(reader=hostile)
    assert observation.query_state == OperationsState.UNAVAILABLE
    assert observation.finished_total is None
    assert observation.alert_rules_loaded is None
    assert observation.grafana_healthy is None
    assert observation.dashboard_provisioned is None
    assert observation.dashboard_reference is None


def test_p_sanitized_results_never_include_raw_bodies(monkeypatch):
    """Untrusted response content never reaches the observation contract."""
    marker = "<script raw-body-marker</script>"

    def hostile(url, body=None):
        if "rules" in url:
            return {"data": {"groups": marker}}  # hostile shape
        if "health" in url:
            return {"database": marker}
        if "dashboards" in url:
            return {"dashboard": {"uid": marker}}
        if "ds/query" in url:
            return {"results": {"A": {"frames": [marker]}}}
        return {"status": "success", "data": {"resultType": "vector",
                "result": [{"metric": {"z": 1}, "value": [0, "3"]}]}}

    observation = query_local_stack(reader=hostile)
    assert observation.query_state in (
        OperationsState.RESULT, OperationsState.UNAVAILABLE)
    assert marker not in observation.model_dump_json()
    assert observation.finished_total is None
    assert observation.alert_rules_loaded is None
