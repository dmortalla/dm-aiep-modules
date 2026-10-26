"""S6 reviewer guidance/polish and closeout regression tests.

Deterministic offline tests over the real Streamlit page and the accepted
application boundaries: complete per-tab guidance, a full Guide surface,
an evidence-bounded observability story, exact historical wording, the
reviewed S3/S4 non-blocker repairs (Grafana data-source total, dashboard
reference only after a real read, refused redirects, HTTP protocol failures,
documented exception chaining, complete clearing) and a whole-page input
inventory. Loopback test servers are test-owned; no Docker, Prometheus,
Grafana, LangSmith, model, credential or external network action occurs.
"""

import ast
import http.client
import http.server
import threading
from pathlib import Path

import pytest
from multi_agent_orchestration import cockpit_ops, cockpit_view
from multi_agent_orchestration.cockpit_langsmith import allowlisted_targets
from multi_agent_orchestration.cockpit_ops import (
    LocalStackObservation,
    query_local_stack,
)
from multi_agent_orchestration.cockpit_view import (
    CURATED_RUN_5,
    GUIDANCE_SECTIONS,
    OperationsState,
    age_in_seconds,
)
from multi_agent_orchestration.console import (
    ConsoleFaultError,
    ConsoleSession,
    age_seconds,
)
from streamlit.testing.v1 import AppTest

MODULE = Path(__file__).parents[1]
APP = MODULE / "app.py"
PACKAGE = MODULE / "src" / "multi_agent_orchestration"
UNSUPPORTED_RUN_4_ID = "27eaee5b-aa8f-4fc5-900a-ed07fe80f55e"
MARKER = "<script>raw-diagnostic-marker</script>"
KINDS = ("text", "markdown", "caption", "error", "warning", "success", "info",
         "subheader", "json")


def app():
    return AppTest.from_file(str(APP), default_timeout=45).run()


def rendered(node) -> str:
    return "\n".join(
        str(element.value) for kind in KINDS for element in node.get(kind)
    )


def valid_stack(url, body=None):
    """Test-owned replies in the accepted Prometheus/Grafana shapes."""
    if "/api/v1/query" in url:
        return {
            "status": "success",
            "data": {"resultType": "vector",
                     "result": [{"metric": {}, "value": [0, "14"]}]},
        }
    if "/api/v1/rules" in url:
        return {"data": {"groups": [{"rules": [
            {"name": name} for name in cockpit_ops.ALERT_RULE_NAMES
        ]}]}}
    if "/api/health" in url:
        return {"database": "ok"}
    if "/api/dashboards/uid/" in url:
        return {"dashboard": {"uid": "module6-operations"}}
    return {"results": {"A": {"status": 200, "frames": [{
        "schema": {"fields": [{"name": "Time"}, {"name": "Value"}]},
        "data": {"values": [[0], [14]]},
    }]}}}


# Reviewer experience -------------------------------------------------------


def test_every_tab_states_purpose_action_expected_result_and_proof():
    """Each workflow tab carries compact what/how/expect/proves guidance."""
    at = app()
    assert not at.exception
    demo, live, ops, tracing, guide = (rendered(tab) for tab in at.tabs)
    for text in (demo, live, ops, tracing):
        for label in ("Purpose", "Action", "Expected result"):
            assert label in text, label
        assert "prove" in text
    assert "does not prove" in demo and "does not prove" in live
    assert "Purpose:" in demo and "What it does not prove:" in demo  # scaling
    assert all(section.title in guide for section in GUIDANCE_SECTIONS)


def test_guide_is_complete_orientation_without_stale_story_wording():
    """The Guide renders every panel; no 'later story' placeholders remain."""
    at = app()
    guide = at.tabs[4]
    titles = [str(item.value) for item in guide.subheader]
    assert titles == [section.title for section in GUIDANCE_SECTIONS]
    text = rendered(at).lower()
    for required in (
        "start here", "coordinator-worker", "hierarchical", "crewai",
        "two independent local worker processes", "researcher -> analyst",
        "public live is intentionally fail-closed", "byok means",
        "how to test each capability", "fresh_execution",
        "recorded_historical", "local projections", "out_of_policy_observation",
    ):
        assert required in text, required
    for stale in ("later story", "(s6)", "story is pending", "candidate build",
                  "offered by a later"):
        assert stale not in text, stale


def test_observability_story_is_prominent_and_evidence_bounded():
    """LangSmith + OTel -> Collector -> Prometheus -> Grafana, locally only."""
    at = app()
    header = "\n".join(str(item.value) for item in at.main.get("caption")[:3])
    assert "AI/agent tracing: LangSmith" in header
    assert "OpenTelemetry → Collector → Prometheus → Grafana" in header
    assert "verified end-to-end locally; not hosted" in header
    assert "Streamlit" in header
    text = rendered(at).lower()
    for overclaim in (
        "production-ready", "production ready", "deployed to production",
        "meets an sla", "hosted telemetry is", "publicly available grafana",
        "sla attained", "production telemetry is",
    ):
        assert overclaim not in text, overclaim
    source = APP.read_text(encoding="utf-8")
    for banned in ("st.iframe", "<iframe", "unsafe_allow_html", "components",
                   "href="):
        assert banned not in source


def test_historical_wording_is_exact_and_run4_identifier_absent():
    """Run 3/4/5 accepted classes stay verbatim; the unsupported id is absent."""
    at = app()
    text = rendered(at)
    assert text.count(CURATED_RUN_5.accepted_classification) >= 2  # Live + tracing
    assert "Recorded · out_of_policy_observation" in text
    assert "Recorded · Authorized current-path real-local verification" in text
    assert "recorded reference: none recorded" in text
    assert UNSUPPORTED_RUN_4_ID not in text
    for path in (APP, *PACKAGE.glob("*.py")):
        assert UNSUPPORTED_RUN_4_ID not in path.read_text(encoding="utf-8"), path


def test_recorded_langsmith_trace_references_are_inert_text():
    """S4 non-blocker: recorded trace references are shown, never as links."""
    at = app()
    plain = "\n".join(str(item.value) for item in at.tabs[3].get("text"))
    for trace_id, _ in allowlisted_targets():
        assert f"recorded trace: {trace_id}" in plain
    markdown = "\n".join(str(item.value) for item in at.get("markdown"))
    assert "](http" not in markdown and "smith.langchain.com" not in markdown


def test_whole_page_input_surface_is_the_accepted_inventory():
    """No endpoint, trace, model, provider, budget or secret control exists."""
    at = app()
    keys = {
        kind: sorted(widget.key for widget in at.get(kind))
        for kind in ("selectbox", "text_area", "number_input", "text_input",
                     "checkbox", "toggle", "radio", "slider", "multiselect",
                     "chat_input")
    }
    assert keys == {
        "selectbox": ["demonstration", "scaling_profile"],
        "text_area": ["live_text", "task_text"],
        "number_input": ["deadline", "steps"],
        "text_input": [], "checkbox": [], "toggle": [], "radio": [],
        "slider": [], "multiselect": [], "chat_input": [],
    }
    assert sorted(button.key for button in at.button) == sorted([
        "run", "clear", "run_live", "run_scaling", "local_live_run",
        "ops_query", "langsmith_read",
    ])


# Operations boundary (S3 non-blockers) -------------------------------------


def test_full_valid_stack_reports_grafana_datasource_total_and_reference():
    """S3 non-blocker: the Grafana data-source total is stored and shown."""
    observation = query_local_stack(reader=valid_stack)
    assert observation.query_state == OperationsState.RESULT
    assert observation.finished_total == 14.0
    assert observation.alert_rules_loaded == 3
    assert observation.grafana_healthy is True
    assert observation.dashboard_provisioned is True
    assert observation.grafana_datasource_total == 14.0
    assert observation.dashboard_reference == (
        "http://127.0.0.1:3000/d/module6-operations")


def test_page_presents_the_grafana_datasource_total(monkeypatch):
    observation = query_local_stack(reader=valid_stack)
    monkeypatch.setattr(cockpit_ops, "query_local_stack",
                        lambda reader=None: observation)
    at = app()
    at.button(key="ops_query").click().run()
    assert not at.exception
    metrics = {item.label: item.value for item in at.metric}
    assert metrics["Finished workflows (via Grafana data source)"] == "14"
    assert metrics["Finished workflows (local Prometheus)"] == "14"


def test_dashboard_reference_requires_a_real_dashboard_read():
    """No current-host reference is offered when Grafana was not read."""
    def prometheus_only(url, body=None):
        if ":3000" in url:
            raise ConnectionRefusedError(MARKER)
        return valid_stack(url, body)

    observation = query_local_stack(reader=prometheus_only)
    assert observation.query_state == OperationsState.RESULT
    assert observation.finished_total == 14.0
    assert observation.dashboard_provisioned is None
    assert observation.grafana_datasource_total is None
    assert observation.dashboard_reference is None


@pytest.mark.parametrize(
    "failure",
    [
        http.client.IncompleteRead(b"partial"),
        http.client.RemoteDisconnected(MARKER),
        http.client.BadStatusLine(MARKER),
        TimeoutError(MARKER),
    ],
)
def test_http_protocol_failures_are_unavailable_not_faults(failure):
    """Expected read failures yield the honest unavailable state."""
    def failing(url, body=None):
        raise failure

    observation = query_local_stack(reader=failing)
    assert observation == LocalStackObservation(
        query_state=OperationsState.UNAVAILABLE)
    assert MARKER not in observation.model_dump_json()


def test_unexpected_reader_failure_is_a_sanitized_chained_fault(monkeypatch):
    """Documented chaining: fixed message, chained cause, nothing stored."""
    def broken(url, body=None):
        raise RuntimeError(MARKER)

    original = query_local_stack
    monkeypatch.setattr(cockpit_ops, "query_local_stack",
                        lambda reader=None: original(reader=broken))
    session = ConsoleSession()
    with pytest.raises(ConsoleFaultError) as fault:
        session.check_operations()
    assert MARKER not in str(fault.value)
    assert isinstance(fault.value.__cause__, RuntimeError)
    assert session.operations is None


def test_production_reader_refuses_redirects_and_ignores_proxies(monkeypatch):
    """A loopback reply can never steer the read to another location."""
    hits = {"target": 0, "proxy": 0}

    class Target(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib handler name
            hits["target"] += 1
            body = b'{"ok": true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    class Redirector(Target):
        def do_GET(self):  # noqa: N802 - stdlib handler name
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{target_port}/hit")
            self.send_header("Content-Length", "0")
            self.end_headers()

    class Proxy(Target):
        def do_GET(self):  # noqa: N802 - stdlib handler name
            hits["proxy"] += 1
            super().do_GET()

    servers = [http.server.HTTPServer(("127.0.0.1", 0), handler)
               for handler in (Target, Redirector, Proxy)]
    target_port, redirect_port, proxy_port = (
        server.server_address[1] for server in servers)
    threads = [threading.Thread(target=server.serve_forever, daemon=True)
               for server in servers]
    for thread in threads:
        thread.start()
    try:
        monkeypatch.setenv("HTTP_PROXY", f"http://127.0.0.1:{proxy_port}")
        monkeypatch.setenv("http_proxy", f"http://127.0.0.1:{proxy_port}")
        monkeypatch.delenv("NO_PROXY", raising=False)
        monkeypatch.delenv("no_proxy", raising=False)
        assert cockpit_ops._production_reader(
            f"http://127.0.0.1:{target_port}/ok") == {"ok": True}
        assert hits == {"target": 1, "proxy": 0}
        with pytest.raises(OSError):
            cockpit_ops._production_reader(f"http://127.0.0.1:{redirect_port}/r")
        assert hits == {"target": 1, "proxy": 0}
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()


# Console boundary ----------------------------------------------------------


def test_unexpected_langsmith_provider_failure_is_a_sanitized_chained_fault():
    """Expected read errors are unavailable; unexpected ones are faults."""
    def expected(trace_id):
        raise ConnectionResetError(MARKER)

    def unexpected(trace_id):
        raise RuntimeError(MARKER)

    session = ConsoleSession()
    stored = session.inspect_langsmith(provider=expected)
    assert stored.observation.read_state == "unavailable"
    with pytest.raises(ConsoleFaultError) as fault:
        session.inspect_langsmith(provider=unexpected)
    assert MARKER not in str(fault.value)
    assert isinstance(fault.value.__cause__, RuntimeError)
    assert MARKER not in session.langsmith_read.model_dump_json()


def test_clear_removes_operations_and_langsmith_results():
    """S6 repair: Clear removes every retained presentation view."""
    session = ConsoleSession()
    session.inspect_langsmith(provider=None)
    session._operations = cockpit_ops.StoredOperationsObservation(
        happened_ns=1,
        observation=LocalStackObservation(query_state=OperationsState.UNAVAILABLE),
    )
    assert session.langsmith_read is not None and session.operations is not None
    session.clear()
    assert session.langsmith_read is None and session.operations is None


def test_clear_button_removes_a_retained_langsmith_inspection():
    at = app()
    at.button(key="langsmith_read").click().run()
    assert at.session_state.console.langsmith_read is not None
    at.button(key="clear").click().run()
    assert not at.exception
    assert at.session_state.console.langsmith_read is None
    assert "Not activated: no current LangSmith read" in rendered(at)


@pytest.mark.parametrize("delta_ns", [0, 999_999_999, 1_000_000_000,
                                      61_500_000_000, -5_000_000_000])
def test_one_staleness_helper_serves_every_tab(monkeypatch, delta_ns):
    """S3 non-blocker: console.age_seconds delegates to the S1 helper."""
    import time

    monkeypatch.setattr(time, "time_ns", lambda: 10**12)

    class Retained:
        finished_ns = 10**12 - delta_ns

    assert age_seconds(Retained()) == age_in_seconds(Retained.finished_ns)
    assert age_seconds(Retained()) == max(0, delta_ns // 1_000_000_000)


# Code-quality closeout guards ----------------------------------------------


COCKPIT_SURFACE = (
    "cockpit_view.py", "cockpit_ops.py", "cockpit_langsmith.py",
    "cockpit_local_live.py", "console.py", "console_live.py",
)


@pytest.mark.parametrize("name", COCKPIT_SURFACE)
def test_cockpit_surface_public_api_is_documented_and_typed(name):
    """B4: public classes/functions/methods carry docstrings and return types."""
    tree = ast.parse((PACKAGE / name).read_text(encoding="utf-8"))
    assert ast.get_docstring(tree), name
    gaps = []

    def visit(node, owner=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef) and not child.name.startswith("_"):
                if not ast.get_docstring(child):
                    gaps.append(f"{owner}{child.name}")
                visit(child, f"{child.name}.")
            elif isinstance(child, ast.FunctionDef) and (
                not child.name.startswith("_")
            ):
                if not ast.get_docstring(child):
                    gaps.append(f"{owner}{child.name}: docstring")
                if child.returns is None:
                    gaps.append(f"{owner}{child.name}: return type")

    visit(tree)
    assert gaps == [], gaps


def test_guidance_and_module_docs_drop_superseded_future_story_claims():
    """Docstrings no longer describe delivered S3/S5 behavior as future work."""
    text = cockpit_view.__doc__ + "".join(
        str(getattr(cockpit_view, name).__doc__)
        for name in ("OperationsState", "OperationsActivation", "LiveCapability",
                     "GuidanceSection")
    )
    for stale in ("later story", "rendering happens later",
                  "is available only when a"):
        assert stale not in text, stale
