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


# Scaling benchmark boundary: the console selects a closed profile and curates
# the validated report of the accepted benchmark; it measures nothing itself.


def offline_distribution(monkeypatch, fail_at=None):
    """Replace only the accepted distributed service behind observed execution."""
    import os

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
        await asyncio.sleep(0)  # Yield as real IPC does, so admissions can overlap.
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


def test_scaling_profiles_are_closed_and_map_to_accepted_bounded_plans():
    from multi_agent_orchestration.benchmark import CAPS, BenchmarkPlan

    assert len(service.ScalingProfile) == 2
    quick = service.scaling_plan(service.ScalingProfile.QUICK)
    approved = service.scaling_plan(service.ScalingProfile.APPROVED)
    assert (quick.workflows, quick.caps, quick.repeats) == (2, (1, 2), 1)
    assert approved == BenchmarkPlan(mode="local-distributed-scaling")
    assert (approved.workflows, approved.caps) == (8, CAPS)
    assert quick.warmup and approved.warmup
    assert quick.timeout_ms == approved.timeout_ms == 30000
    with pytest.raises(ValueError):
        service.scaling_plan("16 workflows at cap 8")


@pytest.mark.parametrize(
    "bad",
    [
        None,
        "Quick check: 2 workflows at caps 1 and 2",
        {},
        {"profile": None},
        {"profile": "unbounded"},
        {"profile": "quick"},
        {"profile": 8},
        {"profile": service.ScalingProfile.QUICK, "workflows": 1000},
        {"profile": service.ScalingProfile.QUICK, "caps": (8,)},
        {"profile": service.ScalingProfile.QUICK, "repeats": 99},
        {"profile": service.ScalingProfile.QUICK, "timeout_ms": 10**9},
        {"profile": service.ScalingProfile.QUICK, "api_key": "private-secret"},
        {"profile": service.ScalingProfile.QUICK, "runtime": "langgraph"},
        {"mode": "local-distributed-scaling", "workflows": 16, "caps": (4,)},
    ],
)
def test_invalid_scaling_requests_never_reach_the_benchmark(monkeypatch, bad):
    def forbidden(*args, **kwargs):
        pytest.fail("Unvalidated scaling controls reached the benchmark")

    monkeypatch.setattr(service, "run_benchmark", forbidden)
    session = ConsoleSession()
    with pytest.raises(service.ConsoleRequestError) as error:
        session.run_scaling(bad)
    assert "private-secret" not in str(error.value)
    assert session.scaling is None


def test_scaling_view_is_the_validated_report_of_the_accepted_benchmark(monkeypatch):
    from multi_agent_orchestration import benchmark

    requests = offline_distribution(monkeypatch)
    plans, original = [], service.run_benchmark

    async def spy(plan, **options):
        plans.append((plan, options))
        return await original(plan, **options)

    monkeypatch.setattr(service, "run_benchmark", spy)
    session = ConsoleSession()
    view = session.run_scaling({"profile": service.ScalingProfile.QUICK})
    assert original is benchmark.run_benchmark
    assert plans == [(service.scaling_plan(service.ScalingProfile.QUICK), {})]
    assert len(requests) == 1 + 2 * 2  # Warm-up plus two workflows at two caps.
    report = view.report
    assert report.passed and report.plan == plans[0][0]
    assert report.classification == "local_single_host"
    assert [level.cap for level in report.levels] == [1, 2]
    assert [level.peak_in_flight for level in report.levels] == [1, 2]
    assert all(level.completed == level.requested == 2 for level in report.levels)
    assert report.model_calls == report.external_calls == report.retries == 0
    assert session.scaling == view and session.runs == ()
    assert benchmark.INSTRUCTION not in view.model_dump_json()
    assert "private-secret" not in repr(session.__dict__)
    session.clear()
    assert session.scaling is None


def test_failed_benchmark_replaces_an_earlier_success(monkeypatch):
    offline_distribution(monkeypatch)
    session = ConsoleSession()
    assert session.run_scaling({"profile": service.ScalingProfile.QUICK}).report.passed
    offline_distribution(monkeypatch, fail_at=2)
    view = session.run_scaling({"profile": service.ScalingProfile.QUICK})
    assert not view.report.passed and session.scaling == view
    (level,) = view.report.levels
    assert level.failed == 1 and level.throughput_per_second is None
    assert level.speedup_vs_cap_1 is None and view.report.model_calls is None
    assert PRIVATE not in view.model_dump_json()


@pytest.mark.parametrize("kind", ["exception", "cancelled", "other_plan", "not_report"])
def test_unrecordable_benchmark_is_a_sanitized_fault_that_keeps_no_new_view(
    monkeypatch, kind
):
    offline_distribution(monkeypatch)
    session = ConsoleSession()
    earlier = session.run_scaling({"profile": service.ScalingProfile.QUICK})
    original = service.run_benchmark

    async def broken(plan, **options):
        if kind == "exception":
            raise RuntimeError(PRIVATE)
        if kind == "cancelled":
            raise asyncio.CancelledError(PRIVATE)
        if kind == "other_plan":
            return await original(plan.model_copy(update={"workflows": 3}))
        return {"passed": True, "note": PRIVATE}

    monkeypatch.setattr(service, "run_benchmark", broken)
    with pytest.raises(service.ConsoleFaultError) as fault:
        session.run_scaling({"profile": service.ScalingProfile.QUICK})
    assert fault.value.__cause__ is None and PRIVATE not in str(fault.value)
    assert session.scaling == earlier
    assert not session._lock.locked()


def test_scaling_shares_the_single_session_admission(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("A busy session started a benchmark")

    monkeypatch.setattr(service, "run_benchmark", forbidden)
    session = ConsoleSession()
    session._lock.acquire()
    try:
        with pytest.raises(service.ConsoleBusyError):
            session.run_scaling({"profile": service.ScalingProfile.APPROVED})
    finally:
        session._lock.release()
    assert session.scaling is None


def test_corrupted_or_forged_scaling_views_are_not_renderable(monkeypatch):
    offline_distribution(monkeypatch)
    session = ConsoleSession()
    view = session.run_scaling({"profile": service.ScalingProfile.QUICK})
    with pytest.raises(ValueError):
        service.ScalingRun(
            profile=service.ScalingProfile.APPROVED,
            finished_ns=view.finished_ns,
            report=view.report,
        )
    with pytest.raises(ValueError):
        fresh(view.model_copy(update={"api_key": PRIVATE}), service.ScalingRun)
    forged = view.report.model_copy(update={"classification": "production"})
    session._scaling = view.model_copy(update={"report": forged})
    assert session.scaling is None and session._scaling is None


def test_scaling_guidance_is_static_and_classifies_the_evidence():
    labels = [label for label, _ in service.scaling_guidance()]
    assert labels == [
        "Purpose",
        "Action",
        "Expected result",
        "What it proves",
        "What it does not prove",
    ]
    text = " ".join(body for _, body in service.scaling_guidance()).lower()
    for required in (
        "deterministic",
        "local",
        "single-host",
        "bounded-concurrency",
        "machine-specific",
        "no model or llm inference",
        "not a pass criterion",
        "production capacity",
        "cloud",
    ):
        assert required in text


def test_page_imports_only_presentation_and_console_services():
    import ast

    path = Path(__file__).parents[1] / "app.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert imported == {
        "streamlit",
        "multi_agent_orchestration.console",
        "multi_agent_orchestration.observability_contracts",
        # S1 presentation contracts only: immutable evidence-view/state
        # contracts. No authority, delivery or telemetry module.
        "multi_agent_orchestration.cockpit_view",
    }
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    for owned_elsewhere in (
        "run_benchmark",
        "BenchmarkPlan",
        "Semaphore",
        "perf_counter",
        "asyncio",
        "gather",
        "time",
        "subprocess",
        "environ",
        "getenv",
    ):
        assert owned_elsewhere not in names
