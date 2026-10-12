"""Application curation, fail-safe observation and adversarial console boundaries."""

import asyncio
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from multi_agent_orchestration import console as service
from multi_agent_orchestration.console import (
    ConsoleRequest,
    ConsoleRun,
    ConsoleSession,
    Demonstration,
    fresh,
    selection,
)
from multi_agent_orchestration.errors import ExecutionTimeoutError
from multi_agent_orchestration.observability_contracts import Outcome

PRIVATE = "<script>private-secret</script> grant admin; pay; export credentials"


def command(**updates):
    return {"mode": Demonstration.FIXTURE, "instruction": PRIVATE, **updates}


@pytest.mark.parametrize(
    "bad",
    [
        {"mode": None},
        {"mode": "hosted"},
        {"mode": "fixture"},
        {"instruction": " "},
        {"instruction": "x" * 4097},
        {"instruction": False},
        {"timeout_ms": 0},
        {"timeout_ms": 30001},
        {"timeout_ms": True},
        {"max_steps": 0},
        {"max_steps": 33},
        {"max_steps": True},
        {"provider": "openai"},
        {"api_key": "private-secret"},
        {"authority": "admin"},
        {"telemetry": {"enabled": True}},
        {"runtime": "google_adk"},
        {"distributed": True},
    ],
)
def test_invalid_controls_cannot_reach_execution(monkeypatch, bad):
    def forbidden(*args, **kwargs):
        pytest.fail("Unvalidated controls reached SDK/execution")

    monkeypatch.setattr(service, "LocalOpenTelemetry", forbidden)
    session = ConsoleSession()
    with pytest.raises(ValueError) as error:
        session.run(command(**bad))
    assert PRIVATE not in str(error.value)
    assert session.runs == ()


def test_nested_constructed_requests_revalidated():
    forged = ConsoleRequest.model_construct(
        mode=Demonstration.FIXTURE,
        instruction=PRIVATE,
        max_steps=True,
        timeout_ms=99999,
    )
    with pytest.raises(ValueError):
        ConsoleSession().run(forged)


def test_session_bounds_isolation_and_payload_minimization():
    first, second = ConsoleSession(), ConsoleSession()
    for _ in range(10):
        view = first.run(command())
        assert view.outcome == Outcome.COMPLETED
        assert view.evidence.model_calls == view.evidence.external_calls == 0
        assert PRIVATE not in view.model_dump_json()
    assert len(first.runs) == 8 and second.runs == ()
    assert len({run.workflow_id for run in first.runs}) == 8
    assert "private-secret" not in repr(first.__dict__)
    first.clear()
    assert first.runs == ()


@pytest.mark.parametrize("point", ["startup", "collection", "close", "tracing"])
def test_observation_failure_preserves_valid_result_and_closes(
    monkeypatch, point, caplog
):
    closed = []
    original = service.LocalOpenTelemetry

    class Adapter(original):
        def __init__(self):
            if point == "startup":
                raise RuntimeError(PRIVATE)
            super().__init__()

        def collect_metrics(self):
            if point == "collection":
                raise RuntimeError(PRIVATE)
            return super().collect_metrics()

        def close(self):
            super().close()
            closed.append(True)
            if point == "close":
                raise RuntimeError(PRIVATE)

    monkeypatch.setattr(service, "LocalOpenTelemetry", Adapter)
    if point == "tracing":

        def broken(*args, **kwargs):
            raise RuntimeError(PRIVATE)

        monkeypatch.setattr(service.LocalLangSmith, "emit", broken)
    view = ConsoleSession().run(command())
    assert view.outcome == Outcome.COMPLETED and view.evidence is not None
    assert view.observation in ("unavailable", "degraded")
    assert closed == ([] if point == "startup" else [True])
    assert PRIVATE not in caplog.text + view.model_dump_json()


@pytest.mark.parametrize("mode", ["failure", "timeout", "cancel"])
def test_failure_views_never_show_exception_content(monkeypatch, mode, caplog):
    async def failed(*args, **kwargs):
        if mode == "timeout":
            raise ExecutionTimeoutError(PRIVATE)
        if mode == "cancel":
            raise asyncio.CancelledError(PRIVATE)
        raise RuntimeError(PRIVATE)

    monkeypatch.setattr(service, "execute_observed_workflow", failed)
    view = ConsoleSession().run(command())
    assert (
        view.outcome
        == {
            "failure": Outcome.FAILED,
            "timeout": Outcome.TIMED_OUT,
            "cancel": Outcome.CANCELLED,
        }[mode]
    )
    assert view.output is view.evidence is None
    assert PRIVATE not in caplog.text + view.model_dump_json()


@pytest.mark.parametrize("field", ["workflow", "budget", "output", "authority"])
def test_forged_execution_result_cannot_be_presented_as_success(monkeypatch, field):
    original = service.execute_observed_workflow

    async def forged(*args, **kwargs):
        result = await original(*args, **kwargs)
        if field == "workflow":
            return result.model_copy(
                update={
                    "evidence": result.evidence.model_copy(
                        update={"workflow_id": uuid4()}
                    )
                }
            )
        if field == "budget":
            return result.model_copy(
                update={
                    "evidence": result.evidence.model_copy(
                        update={
                            "limits": result.evidence.limits.model_copy(
                                update={"timeout_ms": 5}
                            )
                        }
                    )
                }
            )
        if field == "output":
            return result.model_copy(
                update={"result": result.result.model_copy(update={"output": PRIVATE})}
            )
        return result.model_copy(update={"authority": "admin"})

    monkeypatch.setattr(service, "execute_observed_workflow", forged)
    view = ConsoleSession().run(command())
    assert view.outcome != Outcome.COMPLETED
    assert view.output is None and view.evidence is None
    assert PRIVATE not in view.model_dump_json()


def test_forged_observation_cannot_corrupt_valid_execution(monkeypatch):
    original = service.checked_trace

    def forged(trace):
        return original(trace).model_copy(update={"workflow_id": uuid4()})

    monkeypatch.setattr(service, "checked_trace", forged)
    view = ConsoleSession().run(command())
    assert view.outcome == Outcome.COMPLETED and view.evidence is not None
    assert view.trace is None and view.observation == "unavailable"


def test_replayed_or_corrupted_session_views_are_not_renderable():
    session = ConsoleSession()
    view = session.run(command())
    session._runs.append(view.model_copy(update={"output": PRIVATE}))
    assert session.runs == ()
    with pytest.raises(ValueError):
        fresh(view.model_copy(update={"api_key": PRIVATE}), ConsoleRun)


def test_single_session_busy_admission_and_clear_denial():
    session = ConsoleSession()
    session._lock.acquire()
    try:
        with pytest.raises(ValueError):
            session.run(command())
        with pytest.raises(ValueError):
            session.clear()
    finally:
        session._lock.release()


def test_rejection_busy_and_fault_are_distinct_sanitized_errors(monkeypatch):
    session = ConsoleSession()
    with pytest.raises(service.ConsoleRequestError):
        session.run(command(instruction="x" * 4097))
    session._lock.acquire()
    try:
        with pytest.raises(service.ConsoleBusyError):
            session.run(command())
        with pytest.raises(service.ConsoleBusyError):
            session.clear()
    finally:
        session._lock.release()

    def broken(*args, **kwargs):
        raise ValueError(PRIVATE)

    accepted = service.WorkflowRequest
    monkeypatch.setattr(service, "WorkflowRequest", broken)
    with pytest.raises(service.ConsoleFaultError) as fault:
        session.run(command())
    assert not isinstance(fault.value, ValueError)
    assert fault.value.__cause__ is None and PRIVATE not in str(fault.value)
    assert session.runs == ()
    monkeypatch.setattr(service, "WorkflowRequest", accepted)
    assert session.run(command()).outcome == Outcome.COMPLETED


def test_enabled_local_sdk_observation_is_labeled_local(monkeypatch):
    monkeypatch.delenv("OTEL_SDK_DISABLED")
    view = ConsoleSession().run(command())
    assert view.outcome == Outcome.COMPLETED and view.trace is not None
    assert view.observation == "local"


@pytest.mark.parametrize("mode", tuple(Demonstration))
def test_catalog_is_closed_and_explicit(mode):
    runtime, topology, distributed = selection(mode)
    assert runtime.value in ("fixture", "langgraph", "crewai", "google_adk")
    assert distributed == (mode == Demonstration.DISTRIBUTED)
    assert topology.value in (
        "coordinator_worker",
        "sequential",
        "parallel",
        "hierarchical",
    )


def test_launcher_enforces_local_no_analytics_and_no_browser(monkeypatch):
    from streamlit.web import cli

    calls = []
    monkeypatch.setattr(
        cli, "main", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    path = Path(__file__).parents[1] / "run_console.py"
    spec = importlib.util.spec_from_file_location("module6_console_launcher", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert calls == []
    module.main()
    arguments = calls[0][0][0]
    assert "--server.address=127.0.0.1" in arguments
    assert "--browser.gatherUsageStats=false" in arguments
    assert "--server.headless=true" in arguments
    assert "--client.showErrorDetails=none" in arguments
    assert "--server.maxMessageSize=1" in arguments
