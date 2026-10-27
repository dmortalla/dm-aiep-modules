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
import re
import textwrap
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
    Demonstration,
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
    """Accepted workflow tabs retain guidance; Guide and evidence remain distinct."""
    at = app()
    assert not at.exception
    assert len(at.tabs) == 6
    guide, demo, live, ops, tracing, implementation = (
        rendered(tab) for tab in at.tabs
    )
    for text in (demo, live, ops, tracing):
        for label in ("Purpose", "Action", "Expected result"):
            assert label in text, label
        assert "prove" in text
    assert "does not prove" in demo and "does not prove" in live
    assert "Purpose:" in demo and "What it does not prove:" in demo
    assert "Welcome to the Multi-Agent Orchestration System" in guide
    assert "What this module demonstrates" in guide
    assert "How to explore" in guide
    assert all(section.title in guide for section in GUIDANCE_SECTIONS)
    assert "Implementation Evidence" in implementation
    assert "What this proves" in implementation


def test_guide_is_complete_orientation_without_stale_story_wording():
    """Verify the accepted Guide is first, complete, and free of stale story text."""
    at = app()
    guide = at.tabs[0]
    guide_text = rendered(guide)
    text = rendered(at).lower()
    titles = [str(item.value) for item in guide.subheader]
    accepted_titles = [section.title for section in GUIDANCE_SECTIONS]
    assert titles[-len(accepted_titles):] == accepted_titles
    for required in (
        "Welcome to the Multi-Agent Orchestration System",
        "What this module demonstrates",
        "How to explore",
        "Deterministic Demo",
        "Live / BYOK",
        "Operations",
        "LangSmith Tracing",
        "Implementation Evidence",
        "credential presence alone never grants authority",
        "Public live execution is not enabled",
        "Recorded evidence",
        "OpenTelemetry",
        "Prometheus",
        "Grafana",
        "LangSmith",
    ):
        assert required in guide_text, required

    for required in (
        "coordinator-worker",
        "hierarchical",
        "crewai",
        "two independent local worker processes",
        "researcher -> analyst",
        "public live is intentionally fail-closed",
        "byok means",
        "how to test each capability",
        "fresh_execution",
        "recorded_historical",
        "local projections",
        "out_of_policy_observation",
    ):
        assert required in text, required
    lowered = rendered(at).lower()
    for stale in (
        "later story",
        "(s6)",
        "story is pending",
        "candidate build",
        "offered by a later",
    ):
        assert stale not in lowered, stale


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
    assert source.count("unsafe_allow_html=True") == 1
    assert "<style>" in source
    for banned in ("st.iframe", "<iframe", "components", "href="):
        assert banned not in source


def test_historical_wording_is_exact_and_run4_identifier_absent():
    """Run 3/4/5 accepted classes stay verbatim; the unsupported id is absent."""
    at = app()
    text = rendered(at)
    assert text.count(CURATED_RUN_5.accepted_classification) >= 2  # Live + tracing
    assert "Run 3 · Out-of-policy observation" in text
    assert "Run 4 · Authorized real-local verification" in text
    assert "out_of_policy_observation" in text
    assert "Authorized current-path real-local verification" in text
    assert "recorded reference: none recorded" in text
    assert UNSUPPORTED_RUN_4_ID not in text
    for path in (APP, *PACKAGE.glob("*.py")):
        assert UNSUPPORTED_RUN_4_ID not in path.read_text(encoding="utf-8"), path


def test_recorded_langsmith_trace_references_are_inert_text():
    """S4 non-blocker: recorded trace references are shown, never as links."""
    at = app()
    plain = "\n".join(str(item.value) for item in at.tabs[4].get("text"))
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


# Implementation Evidence provenance (N-4) ---------------------------------

EVIDENCE_SOURCES = {
    "LangGraph": ("_langgraph_topologies.py", {"compile_topology"}),
    "CrewAI": ("_crewai_adapter.py", {"build_crew", "run_crew"}),
    "Google ADK": ("_adk_adapter.py", {"build_workflow", "run_adk"}),
    "LangSmith": ("langsmith_delivery.py", {"LangSmithTraceDelivery._run"}),
    "OpenTelemetry": ("telemetry_delivery.py", {"OtlpMetricDelivery.__init__"}),
}


def implementation_tab(at):
    return next(tab for tab in at.tabs if tab.label == "Implementation Evidence")


def first_unmatched_line(excerpt: str, source: str):
    """Return the first excerpt line absent from the source in order, else None."""
    lines = [line.strip() for line in source.splitlines()]
    position = 0
    for raw in excerpt.splitlines():
        line = raw.strip()
        if not line or line == "...":
            continue
        try:
            position = lines.index(line, position) + 1
        except ValueError:
            return line
    return None


def defined_names(source: str) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef):
            names.add(node.name)
            names.update(
                f"{node.name}.{child.name}"
                for child in node.body
                if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
            )
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
    return names


def test_implementation_excerpts_are_verbatim_current_source_with_durable_refs():
    """Each excerpt is copied, in order, from the file and symbol it cites."""
    at = app()
    expanders = implementation_tab(at).expander
    assert [e.label.split(" — ")[0].split(" →")[0] for e in expanders] == list(
        EVIDENCE_SOURCES
    )
    for expander in expanders:
        technology = next(k for k in EVIDENCE_SOURCES if expander.label.startswith(k))
        filename, symbols = EVIDENCE_SOURCES[technology]
        codes = expander.get("code")
        sources = [c for c in expander.caption if str(c.value).startswith("Source:")]
        assert len(codes) == 1 and len(sources) == 1, technology
        caption = str(sources[0].value)
        cited = re.findall(r"`([^`]+)`", caption)
        assert cited[0] == f"src/multi_agent_orchestration/{filename}", caption
        assert not re.search(r"\blines?\s+\d", caption), caption  # no brittle ranges
        source_text = (PACKAGE / filename).read_text(encoding="utf-8")
        assert set(cited[1:]) == symbols, (technology, cited)
        assert symbols <= defined_names(source_text), (technology, symbols)
        missing = first_unmatched_line(str(codes[0].value), source_text)
        assert missing is None, (technology, missing)
        assert codes[0].language == "python"


def test_implementation_tab_keeps_claims_evidence_bounded_and_classified():
    """Excerpts prove structure only; runtime and delivery stay separately labelled."""
    at = app()
    tab = implementation_tab(at)
    text = rendered(tab)
    lowered = text.lower()
    assert text.count("What this proves:") == len(EVIDENCE_SOURCES)
    for phrase in (
        "not claims of hosted production scale",
        "No code excerpt alone is treated as proof",
        "current external-service state",
        "separately labelled deterministic, local, recorded and externally verified",
    ):
        assert phrase.lower() in lowered, phrase
    for overclaim in ("is deployed", "currently running", "is available now",
                      "hosted production telemetry is", "verified in production",
                      "production-ready", "meets an sla"):
        assert overclaim not in lowered, overclaim
    langsmith = next(e for e in tab.expander if e.label.startswith("LangSmith"))
    langsmith_text = rendered(langsmith)
    assert "does not show that any delivery happened" in langsmith_text
    assert "service_read" in langsmith_text and "unverified_write" in langsmith_text
    otel = next(e for e in tab.expander if e.label.startswith("OpenTelemetry"))
    assert "does not show that run or the state of any service now" in rendered(otel)
    assert "recorded local verification" in rendered(otel)
    assert UNSUPPORTED_RUN_4_ID not in text
    assert "](http" not in text and "github.com" not in lowered


# Bounded static HTML/CSS contract (N-5) -------------------------------------


def app_tree() -> ast.Module:
    return ast.parse(APP.read_text(encoding="utf-8"))


def unsafe_html_calls(tree: ast.AST):
    return [
        (node, keyword)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "unsafe_allow_html"
    ]


def allowed_css(tree: ast.AST) -> str:
    (node, keyword), = unsafe_html_calls(tree)
    assert isinstance(keyword.value, ast.Constant) and keyword.value.value is True
    assert isinstance(node.func, ast.Attribute) and node.func.attr == "markdown"
    assert isinstance(node.func.value, ast.Name) and node.func.value.id == "st"
    # One positional literal: an f-string, name, call or concatenation is not a
    # Constant, so no dynamic value can ever flow into the allowed HTML block.
    assert len(node.args) == 1 and [k.arg for k in node.keywords] == [
        "unsafe_allow_html"
    ]
    assert isinstance(node.args[0], ast.Constant)
    assert isinstance(node.args[0].value, str)
    return node.args[0].value


def test_unsafe_html_surface_is_exactly_one_static_literal_css_block():
    """The invariant is a bounded static surface, not 'the flag never appears'."""
    tree = app_tree()
    css = allowed_css(tree)
    block = re.fullmatch(r"\s*<style>(.*)</style>\s*", css, re.S)
    assert block, "the allowed surface is a single <style> element and nothing else"
    body = block.group(1).lower()
    assert "<" not in body  # no nested tag or comment can open inside the block
    for banned in ("@import", "url(", "expression(", "javascript:", "behavior:",
                   "-moz-binding", "<script", "<iframe", "<a ", "href", "src="):
        assert banned not in css.lower(), banned
    # No other HTML, component or frame surface anywhere in the app or launchers.
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not {"html", "iframe", "components", "v1"} & (names | attrs)
    imported = {
        alias.name
        for n in ast.walk(tree)
        if isinstance(n, ast.Import | ast.ImportFrom)
        for alias in n.names
    } | {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not any("components" in str(name) for name in imported)
    for path in (
        MODULE / "private_local_app.py",
        MODULE / "private_local_runtime.py",
        MODULE / "run_local_live.py",
        *PACKAGE.glob("*.py"),
    ):
        assert "unsafe_allow_html" not in path.read_text(encoding="utf-8"), path.name


def test_hostile_workflow_text_never_reaches_the_allowed_html_surface():
    """Untrusted text stays inert; the one HTML element is the static literal."""
    static = textwrap.dedent(allowed_css(app_tree())).strip()
    hostile = (
        "<script>alert(1)</script><style>body{display:none}</style>"
        '<iframe src="x"></iframe>[go](javascript:alert(1))'
    )
    at = app()
    html = [m for m in at.markdown if m.allow_html]
    assert [m.value.strip() for m in html] == [static]
    at.selectbox(key="demonstration").select(Demonstration.FIXTURE).run()
    at.text_area(key="task_text").set_value(hostile)
    at.button(key="run").click().run()
    assert not at.exception
    assert at.session_state.console.runs[-1].outcome.value == "completed"
    html = [m for m in at.markdown if m.allow_html]
    assert [m.value.strip() for m in html] == [static]
    page = rendered(at)
    for fragment in ("<script", "<iframe", "alert(1)", "display:none", "javascript:"):
        assert fragment not in page, fragment
        assert all(fragment not in str(m.value) for m in at.markdown if m.allow_html)
