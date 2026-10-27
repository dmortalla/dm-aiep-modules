"""S5 A–AF: fake-only local execution, trust/authority and actual Streamlit UI."""

import copy
import subprocess
import sys
from collections import deque
from uuid import uuid4

import pytest
from multi_agent_orchestration import cockpit_local_live as local
from multi_agent_orchestration.canonical_contracts import CanonicalWorkflowReceipt
from multi_agent_orchestration.console import ConsoleSession, Demonstration
from multi_agent_orchestration.live_contracts import LiveWorkflowResult
from multi_agent_orchestration.live_policy import NORMAL_REAL_LOCAL_BUDGET

from .test_cockpit_demo import APP, app, rendered
from .test_live_contracts import result
from .test_live_observation import begin, record

PRIVATE = "PRIVATE_KEY_PROMPT_MODEL_RESPONSE_EXCEPTION_<script>do_bad()</script>"


class FakeExecution:
    """Accepted-boundary double only: no gateway, child, inference or network."""

    def __init__(self):
        self.calls = []
        self.error = None

    async def __call__(self, task, **kwargs):
        self.calls.append((task, kwargs["authorization"]))
        if self.error is not None:
            raise self.error(kwargs) if callable(self.error) else self.error
        auth = kwargs["authorization"]
        workflow, task_id = kwargs["workflow_id"], kwargs["task_id"]
        trace = uuid4()
        packet = result().model_dump()
        evidence = packet["evidence"]
        evidence.update(
            workflow_id=workflow,
            task_id=task_id,
            trace_id=trace,
            budget=auth.budget.model_dump(),
            selection=auth.selection.model_dump(),
        )
        evidence["contributions"] = tuple(
            {**r, "workflow_id": workflow, "task_id": task_id}
            for r in evidence["contributions"]
        )
        packet["research"]["findings"] = tuple(
            f"{PRIVATE} {index}."
            for index in range(len(packet["research"]["findings"]))
        )
        packet["analysis"]["assessment"] = PRIVATE + "."
        packet["critique"]["rationale"] = PRIVATE + "."
        terminal = record(
            workflow_id=workflow,
            task_id=task_id,
            trace_id=trace,
            evidence_source="local_provider_execution",
            selection=auth.selection,
            duration_ms=1500.0,
        )
        observer = kwargs["observer"]
        observer.finish_live(begin(observer, terminal), terminal)
        return CanonicalWorkflowReceipt(
            evidence_source="local_provider_execution",
            result=LiveWorkflowResult.model_validate(packet),
        )


@pytest.fixture
def enabled(monkeypatch):
    fake = FakeExecution()
    runtime = local.TrustedLocalRuntime(posture="trusted-private-local", executor=fake)
    # This is trusted test-code injection, never a visitor/session configuration.
    monkeypatch.setattr(local, "current_runtime", lambda: runtime)
    return runtime, fake


@pytest.fixture(autouse=True)
def no_external_actions(monkeypatch):
    import multi_agent_orchestration.canonical_workflow as canonical
    import multi_agent_orchestration.live_langsmith as smith
    import multi_agent_orchestration.live_metric_delivery as metric_delivery

    def forbidden(*args, **kwargs):
        pytest.fail("S5 tests may not execute a real provider or external delivery")

    monkeypatch.setattr(canonical, "execute_canonical_workflow", forbidden)
    monkeypatch.setattr(metric_delivery, "deliver_live_metrics", forbidden)
    monkeypatch.setattr(smith.LiveLangSmithDelivery, "deliver", forbidden)


def test_default_render_and_credentials_never_enable_live(monkeypatch):
    """A–H,O,Q,AF: default/public Demo, no discovery, inputs or implicit execution."""
    for key in (
        "LANGSMITH_API_KEY",
        "OPENAI_API_KEY",
        "OLLAMA_HOST",
        "MODULE6_LIVE_ENABLED",
        "LOCALHOST",
    ):
        monkeypatch.setenv(key, PRIVATE)
    at = app()
    at.run()
    assert not at.exception
    assert at.button(key="local_live_run").disabled
    assert not at.session_state.console.current_local
    assert "demo is the baseline" in rendered(at).lower()
    assert "public/deployed live execution is unavailable" in rendered(at).lower()
    assert PRIVATE not in rendered(at)
    assert at.text_input == []
    # Live has no provider/budget/credential configuration controls.
    live = next(tab for tab in at.tabs if tab.label == "Live / BYOK")
    assert not live.get("text_area") and not live.get("number_input")
    assert ConsoleSession().run_authorized_local().failure == "unavailable"


def test_explicit_click_once_rerender_second_click_and_clear(enabled):
    """H–K,N,P,R–V,AC: one action, fresh authority, sanitized current-only state."""
    runtime, fake = enabled
    at = app()
    assert not at.exception and fake.calls == []
    assert not at.button(key="local_live_run").disabled
    at.button(key="local_live_run").click().run()
    assert not at.exception and len(fake.calls) == 1
    view = at.session_state.console.current_local
    assert view.outcome == "completed" and view.model_calls == 3
    assert view.validated_roles == 3 and view.cleanup == "reaped"
    assert view.evidence.execution_kind.value == "canonical_real_local"
    assert view.evidence.provenance.value == "local_provider_execution"
    assert view.evidence.source.value == "fresh_execution"
    assert view.evidence.delivery_confirmation.value == "not_sent"
    assert PRIVATE not in rendered(at) + repr(at.session_state.console.__dict__)
    assert runtime._pending is None
    at.run()
    assert len(fake.calls) == 1
    at.button(key="local_live_run").click().run()
    assert len(fake.calls) == 2
    assert fake.calls[0][1] is not fake.calls[1][1]
    for task, auth in fake.calls:
        assert task == local.TASK
        assert auth.budget == NORMAL_REAL_LOCAL_BUDGET
        assert auth.selection.provider == "ollama"
        assert auth.selection.model == "qwen2.5-coder:7b"
    assert isinstance(at.session_state.console._current_local, str)
    at.session_state.console.clear()
    at.run()
    assert at.session_state.console.current_local is None and len(fake.calls) == 2


@pytest.mark.parametrize("kind", ["stale", "replay", "copy", "foreign", "tampered"])
def test_stale_replayed_forged_authority_is_rejected(enabled, kind):
    """L,M,S,T: grant identity/freshness/policy checked before canonical execution."""
    runtime, fake = enabled
    grant = runtime.issue(explicit_action=local.ACTION)
    candidate = grant
    if kind == "stale":
        grant.issued -= 31
    elif kind == "replay":
        assert runtime.consume(grant).outcome == "completed"
    elif kind == "copy":
        candidate = copy.copy(grant)
    elif kind == "foreign":
        runtime = local.TrustedLocalRuntime(
            posture="trusted-private-local", executor=fake
        )
    else:
        grant.authorization = grant.authorization.model_copy(update={"budget": {}})
    before = len(fake.calls)
    assert runtime.consume(candidate).failure == "authorization_refused"
    assert len(fake.calls) == before


def test_intent_required_context_not_hostname_and_no_authority_at_construction():
    """D–G,H: only explicit trusted embedding supplies posture, never connectivity."""
    runtime = local.TrustedLocalRuntime(posture="trusted-private-local")
    assert runtime._pending is None and local.current_runtime() is None
    with pytest.raises(local.LocalIntentError):
        runtime.issue(explicit_action="available provider")
    with local.trusted_local_context(runtime):
        assert local.current_runtime() is runtime
    assert local.current_runtime() is None
    with pytest.raises(local.LocalIntentError):
        with local.trusted_local_context({"localhost": True}):
            pass


@pytest.mark.parametrize("error", [RuntimeError(PRIVATE), TimeoutError(PRIVATE)])
def test_failed_attempt_replaces_success_without_retry_and_demo_survives(
    enabled, error
):
    """T,W,X: current failure never replaced by previous/historical success."""
    runtime, fake = enabled
    at = app()
    at.button(key="local_live_run").click().run()
    assert at.session_state.console.current_local.outcome == "completed"
    fake.error = error
    at.button(key="local_live_run").click().run()
    assert not at.exception and len(fake.calls) == 2
    assert at.session_state.console.current_local.outcome != "completed"
    assert PRIVATE not in rendered(at) + repr(at.session_state.console.__dict__)
    assert runtime._pending is None
    at.run()
    assert len(fake.calls) == 2
    at.selectbox(key="demonstration").select(Demonstration.FIXTURE).run()
    at.button(key="run").click().run()
    assert (
        not at.exception
        and at.session_state.console.runs[-1].outcome.value == "completed"
    )


def test_profile_display_and_public_verified_flag_fail_closed():
    """E,R,Q: exact approved profile, no executable public flag or budget controls."""
    from multi_agent_orchestration.cockpit_view import LiveCapability

    assert not LiveCapability(
        deployment_compatible_authority_verified=True
    ).deployed_public_live_available
    for number in (200000, 45000, 4096, 16000):
        assert f"{number:,}" in local.PROFILE_TEXT
    assert "0 retries" in local.PROFILE_TEXT and "concurrency 1" in local.PROFILE_TEXT


def test_projection_failure_never_changes_workflow_or_claims_delivery(
    enabled, monkeypatch
):
    """U,V,AC: failed local projections cannot rewrite success or fabricate reads."""
    _, fake = enabled

    def failing(*args):
        raise OSError(PRIVATE)

    for name in ("_project_smith", "_project_otel", "_project_metrics"):
        monkeypatch.setattr(local, name, failing)
    view = ConsoleSession().run_authorized_local()
    assert view.outcome == "completed" and len(fake.calls) == 1
    assert view.langsmith == view.otel == view.metrics == "unavailable"
    assert view.evidence.delivery_confirmation.value == "not_sent"
    assert not view.evidence.service_read_confirmed
    assert PRIVATE not in view.model_dump_json()


@pytest.mark.parametrize(
    "category,expected",
    [
        ("timed_out", "timed_out"),
        ("budget_refused", "denied"),
        ("authorization_refused", "denied"),
        ("malformed_output", "failed"),
        ("provider_service_failed", "failed"),
        ("connection_failed", "failed"),
    ],
)
def test_canonical_failure_taxonomy_is_sanitized_and_never_retried(
    enabled, category, expected
):
    """W: accepted timeout/budget/provider/validation failures remain fail-closed."""
    from multi_agent_orchestration.canonical_contracts import EvidenceSource
    from multi_agent_orchestration.canonical_workflow import CanonicalWorkflowError
    from multi_agent_orchestration.live_contracts import LiveFailure

    _, fake = enabled
    fake.error = lambda fields: CanonicalWorkflowError(
        LiveFailure(
            workflow_id=fields["workflow_id"],
            task_id=fields["task_id"],
            category=category,
            selection=fields["authorization"].selection,
        ),
        EvidenceSource.LOCAL_PROVIDER_EXECUTION,
    )
    view = ConsoleSession().run_authorized_local()
    assert view.outcome == expected and view.failure
    assert view.model_calls is None and view.duration_ms is None
    assert len(fake.calls) == 1
    assert PRIVATE not in view.model_dump_json()


def test_default_runtime_reuses_canonical_service_without_gateway_override(monkeypatch):
    """I,S: production composition uses canonical default local gateway selection."""
    import multi_agent_orchestration.canonical_workflow as canonical

    fake = FakeExecution()
    seen = []

    async def accepted_boundary(task, **kwargs):
        seen.append(set(kwargs))
        return await fake(task, **kwargs)

    monkeypatch.setattr(canonical, "execute_canonical_workflow", accepted_boundary)
    runtime = local.TrustedLocalRuntime(posture="trusted-private-local")
    with local.trusted_local_context(runtime):
        view = ConsoleSession().run_authorized_local()
    assert view.outcome == "completed" and len(fake.calls) == 1
    assert seen == [{"authorization", "observer", "workflow_id", "task_id"}]
    assert local.current_runtime() is None


def test_historical_exact_classes_and_no_unsupported_run4_identifier(enabled):
    """X–AB,AE: historical records stay immutable, full classification is shown."""
    from multi_agent_orchestration.cockpit_view import CURATED_RUN_4, CURATED_RUN_5

    before = CURATED_RUN_5.model_dump_json()
    at = app()
    at.button(key="local_live_run").click().run()
    assert CURATED_RUN_5.model_dump_json() == before
    assert CURATED_RUN_5.delivery_confirmation.value == "unverified_write"
    assert CURATED_RUN_4.reference_id is None
    assert CURATED_RUN_5.accepted_classification in rendered(at)
    assert at.button(key="ops_query") and at.button(key="langsmith_read")


@pytest.mark.parametrize("attack", ["delivery", "payload", "tokens", "accounting"])
def test_corrupted_current_state_cannot_create_delivery_or_keep_payload(
    enabled, attack
):
    """N,P,V,AC: retained state is closed and revalidated on every presentation."""
    session = ConsoleSession()
    session.run_authorized_local()
    import json

    packet = json.loads(session._current_local)
    if attack == "delivery":
        packet["evidence"]["delivery_confirmation"] = "service_read"
    elif attack == "tokens":
        packet["input_tokens"] = 1_000_001
    elif attack == "accounting":
        packet["model_calls"] = 0
    else:
        packet["secret"] = PRIVATE
    session._current_local = json.dumps(packet)
    assert session.current_local is None and session._current_local is None


def test_deployed_render_imports_without_live_dependencies():
    """A,AD,AF: isolated actual AppTest render blocks all live dependency imports."""
    script = f"""
import importlib.abc, sys, socket
class BlockLive(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {{'multi_agent_orchestration.live_contracts',
            'multi_agent_orchestration.canonical_workflow',
            'multi_agent_orchestration.local_model_gateway',
            'multi_agent_orchestration.live_execution'}}:
            raise AssertionError('Default render imported live dependency: ' + fullname)
sys.meta_path.insert(0, BlockLive())
def blocked(*a, **k):
    raise AssertionError('Render attempted networking')
socket.create_connection = blocked
from streamlit.testing.v1 import AppTest
at = AppTest.from_file({str(APP)!r}, default_timeout=45).run()
assert not at.exception, at.exception
print('isolated-default-render-ok')
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", script], capture_output=True, text=True, timeout=75
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "isolated-default-render-ok" in completed.stdout


def _reachable(root, depth=0, seen=None):
    """Yield every object reachable from retained state (bounded walk)."""
    seen = set() if seen is None else seen
    if id(root) in seen or depth > 8:
        return
    seen.add(id(root))
    yield root
    if isinstance(root, dict):
        children = [*root.keys(), *root.values()]
    elif isinstance(root, (list, tuple, set, frozenset, deque)):
        children = list(root)
    elif hasattr(root, "__dict__") and not isinstance(root, type):
        children = list(vars(root).values())
    else:
        children = []
    for child in children:
        yield from _reachable(child, depth + 1, seen)


def _assert_no_authority_retained(at):
    from multi_agent_orchestration.live_contracts import LiveAuthorization

    state = {key: at.session_state[key] for key in list(at.session_state)}
    assert state, "session state walk must cover the retained console"
    for item in _reachable(state):
        assert type(item) not in (
            LiveAuthorization,
            local._Permit,
            local.TrustedLocalRuntime,
        )
        assert not isinstance(item, str) or PRIVATE not in item


EMBEDDING = """
import runpy

import s5_trusted_embedding as trusted
from multi_agent_orchestration.cockpit_local_live import trusted_local_context

with trusted_local_context(trusted.runtime):
    runpy.run_path(trusted.APP, run_name="__main__")
"""


def test_real_trusted_embedding_seam_enables_only_explicit_once(
    monkeypatch, tmp_path
):
    """D,H–K,N,P,AF: actual injection path, no monkeypatched discovery."""
    import types

    from streamlit.testing.v1 import AppTest

    fake = FakeExecution()
    trusted = types.ModuleType("s5_trusted_embedding")
    trusted.APP = str(APP)
    trusted.runtime = local.TrustedLocalRuntime(
        posture="trusted-private-local", executor=fake
    )
    monkeypatch.setitem(sys.modules, "s5_trusted_embedding", trusted)
    script = tmp_path / "trusted_embedding.py"
    script.write_text(EMBEDDING, encoding="utf-8")
    at = AppTest.from_file(str(script), default_timeout=45).run()
    assert not at.exception and fake.calls == []
    assert "public/deployed live execution is unavailable" in rendered(at).lower()
    # The header posture is case-insensitive: restored from the accepted S5 pins.
    assert "local live/byok: available" in rendered(at).lower()
    assert "public live: unavailable" in rendered(at).lower()
    live = next(tab for tab in at.tabs if tab.label == "Live / BYOK")
    assert not live.button(key="local_live_run").disabled
    at.button(key="local_live_run").click().run()
    assert not at.exception and len(fake.calls) == 1
    assert at.session_state.console.current_local.outcome == "completed"
    _assert_no_authority_retained(at)
    at.run()
    at.run()
    assert len(fake.calls) == 1
    # The capability exists only inside the trusted embedding's render context.
    assert local.current_runtime() is None
    assert ConsoleSession().run_authorized_local().failure == "unavailable"


def test_private_wrapper_enables_only_explicit_once(monkeypatch):
    """Actual private wrapper exposes capability only for explicit execution."""
    import types

    from streamlit.testing.v1 import AppTest

    fake = FakeExecution()
    runtime = local.TrustedLocalRuntime(
        posture="trusted-private-local",
        executor=fake,
    )
    trusted = types.ModuleType("private_local_runtime")
    trusted.runtime = runtime
    monkeypatch.setitem(sys.modules, "private_local_runtime", trusted)

    wrapper = APP.with_name("private_local_app.py")
    at = AppTest.from_file(str(wrapper), default_timeout=45).run()

    assert not at.exception
    assert fake.calls == []
    live = next(tab for tab in at.tabs if tab.label == "Live / BYOK")
    assert not live.button(key="local_live_run").disabled

    at.button(key="local_live_run").click().run()

    assert not at.exception
    assert len(fake.calls) == 1
    assert at.session_state.console.current_local.outcome == "completed"
    assert runtime._pending is None
    _assert_no_authority_retained(at)

    at.run()
    at.run()

    assert len(fake.calls) == 1
    assert local.current_runtime() is None
    assert ConsoleSession().run_authorized_local().failure == "unavailable"

def test_session_state_never_holds_authority_after_success_or_failure(enabled):
    """N,P,V: no grant, authorization, runtime/client or payload is retained."""
    _, fake = enabled
    at = app()
    at.button(key="local_live_run").click().run()
    _assert_no_authority_retained(at)
    fake.error = RuntimeError(PRIVATE)
    at.button(key="local_live_run").click().run()
    assert at.session_state.console.current_local.failure == "runtime_failure"
    _assert_no_authority_retained(at)


def test_live_tab_offers_one_action_and_no_execution_configuration(enabled):
    """O,Q: no provider/model/budget/retry/endpoint/prompt/secret controls."""
    at = app()
    live = next(tab for tab in at.tabs if tab.label == "Live / BYOK")
    for kind in (
        "text_input",
        "text_area",
        "number_input",
        "slider",
        "select_slider",
        "selectbox",
        "multiselect",
        "radio",
        "checkbox",
        "toggle",
        "date_input",
        "time_input",
        "color_picker",
        "chat_input",
    ):
        assert not live.get(kind), kind
    assert [button.key for button in live.button] == ["local_live_run"]
    assert "password" not in APP.read_text(encoding="utf-8").lower()


def test_no_combination_of_capability_flags_enables_public_live():
    """E,F,G: verified/local flags never satisfy the public boundary."""
    from itertools import product

    from multi_agent_orchestration.cockpit_view import LiveCapability
    from multi_agent_orchestration.console import local_live_capability

    for local_flag, verified in product((False, True), repeat=2):
        capability = LiveCapability(
            local_trusted_operator_runtime=local_flag,
            deployment_compatible_authority_verified=verified,
        )
        assert capability.local_live_available is local_flag
        assert capability.deployed_public_live_available is False
    assert local_live_capability() == LiveCapability()


@pytest.mark.parametrize(
    "category,failure",
    [
        ("budget_exhausted", "budget_exhausted"),
        ("output_too_large", "validation_failure"),
        ("rate_limited", "provider_unavailable"),
        ("unexpected_provider_failure", "provider_unavailable"),
    ],
)
def test_failure_keeps_accepted_category_and_renders_fixed_guidance(
    enabled, category, failure
):
    """W,V: accepted closed category plus fixed actionable guidance only."""
    from multi_agent_orchestration.canonical_contracts import EvidenceSource
    from multi_agent_orchestration.canonical_workflow import CanonicalWorkflowError
    from multi_agent_orchestration.live_contracts import LiveFailure
    from multi_agent_orchestration.live_errors import failure_text

    _, fake = enabled
    fake.error = lambda fields: CanonicalWorkflowError(
        LiveFailure(
            workflow_id=fields["workflow_id"],
            task_id=fields["task_id"],
            category=category,
            selection=fields["authorization"].selection,
        ),
        EvidenceSource.LOCAL_PROVIDER_EXECUTION,
    )
    at = app()
    at.button(key="local_live_run").click().run()
    view = at.session_state.console.current_local
    assert view.failure == failure and view.category == category
    assert len(fake.calls) == 1
    text = rendered(at)
    assert failure_text(category) in text
    assert local.failure_guidance(failure) in text
    assert "No historical result replaces this failure." in text


def test_every_closed_failure_has_fixed_guidance():
    """W: each closed failure value maps to bounded application wording."""
    from typing import get_args

    for failure in get_args(local.Failure):
        guidance = local.failure_guidance(failure)
        assert 0 < len(guidance) <= 240
    with pytest.raises(KeyError):
        local.failure_guidance(PRIVATE)


def test_busy_runtime_refuses_concurrent_consumption(enabled):
    """I,T: one bounded execution at a time; a concurrent attempt runs nothing."""
    runtime, fake = enabled
    grant = runtime.issue(explicit_action=local.ACTION)
    assert runtime._lock.acquire(blocking=False)
    try:
        assert runtime.consume(grant).failure == "busy"
    finally:
        runtime._lock.release()
    assert fake.calls == []
    with pytest.raises(local.LocalIntentError):
        runtime.issue(explicit_action=local.ACTION)  # outstanding grant remains


def test_current_result_never_claims_service_read_or_operational_health(enabled):
    """AC,X,Z: current packet stays local-projection only beside history."""
    at = app()
    at.button(key="local_live_run").click().run()
    view = at.session_state.console.current_local
    assert view.evidence.delivery_confirmation.value == "not_sent"
    assert not view.evidence.service_read_confirmed
    assert "operational_classification" not in type(view.evidence).model_fields
    assert "operational" not in "".join(local.CurrentLocalRun.model_fields)
    # Local projection states only (the suite disables the OTel SDK globally).
    assert view.langsmith == "recorded"
    assert {view.otel, view.metrics} <= {"recorded", "refused", "failed"}
    text = rendered(at)
    assert "recorded reference: none recorded" in text  # Run 4
    assert "27eaee5b" not in text
    assert at.session_state.console.operations is None
    assert at.session_state.console.langsmith_read is None
