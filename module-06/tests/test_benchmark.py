"""Bounded local scaling benchmark: plan authority, admission, evidence and cleanup.

Deterministic tests replace only the accepted distributed service behind the
observed execution boundary and inject a clock, so no assertion depends on real
time. One integration test runs real worker processes and asserts structure and
machine-independent invariants only; it never asserts that a higher cap is faster.
"""

import asyncio
import importlib.util
import json
import os
import re
from pathlib import Path
from uuid import uuid4

import pytest
from multi_agent_orchestration import _distributed_processes as transport
from multi_agent_orchestration import benchmark, observed_execution
from multi_agent_orchestration.benchmark import (
    CAPS,
    EXPECTED_OUTPUT,
    INSTRUCTION,
    BenchmarkError,
    BenchmarkPlan,
    BenchmarkReport,
    HostFacts,
    LevelResult,
    level_deadline_ms,
    run_benchmark,
)
from multi_agent_orchestration.contracts import (
    ExecutionLimits,
    GraphTopology,
    RuntimeId,
)
from multi_agent_orchestration.distributed import validate_request
from multi_agent_orchestration.distributed_contracts import (
    DistributedEvidence,
    DistributedResult,
    WorkerId,
    WorkerRecord,
    WorkerRole,
)
from multi_agent_orchestration.errors import (
    ExecutionFailureError,
    ExecutionTimeoutError,
    InvalidRuntimeOutputError,
    StepBudgetExceededError,
)
from pydantic import ValidationError

MODULE = Path(__file__).resolve().parents[1]
MODE = "local-distributed-scaling"
UUID_TEXT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def plan(**changes):
    return BenchmarkPlan(mode=MODE, **{"warmup": False, **changes})


def accepted(request, text=None):
    """A contract-valid result such as the accepted service returns."""
    checked = validate_request(request)
    count = len(checked.task.instruction if text is None else text)
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


class Service:
    """Stands in for the accepted distributed service; records what it was given."""

    def __init__(self, monkeypatch, behaviour=None):
        self.requests, self.active, self.peak, self.left = [], 0, 0, 0
        self.behaviour = behaviour
        monkeypatch.setattr(observed_execution, "execute_distributed_workflow", self)

    async def __call__(self, request):
        index = len(self.requests)
        self.requests.append(request)
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            value = None
            if self.behaviour is not None:
                value = await self.behaviour(index, request)
            return accepted(request) if value is None else value
        finally:
            self.active -= 1
            self.left += 1


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def waves(clock, chosen, steps):
    """Hold each level's workflows until a full wave is admitted, then add time.

    A wave can only fill if the benchmark really admits ``cap`` workflows at
    once, so completion proves the observed peak without any real timing.
    """
    state = {"waiting": 0, "event": asyncio.Event()}

    async def behaviour(index, request):
        level = index // chosen.workflows
        size = min(chosen.caps[level % len(chosen.caps)], chosen.workflows)
        state["waiting"] += 1
        event = state["event"]
        if state["waiting"] == size:
            clock.now += steps[level]
            state["waiting"], state["event"] = 0, asyncio.Event()
            event.set()
        else:
            await event.wait()

    return behaviour


async def measured(monkeypatch, steps=(2.0, 2.0, 2.0), adapters=(), **changes):
    chosen, clock = plan(**changes), Clock()
    service = Service(monkeypatch, waves(clock, chosen, steps))
    report = await asyncio.wait_for(
        run_benchmark(chosen, adapters=adapters, clock=clock), 20
    )
    return report, service


def test_plan_requires_explicit_mode_and_defaults_to_the_approved_workload():
    with pytest.raises(ValidationError):
        BenchmarkPlan()
    approved = BenchmarkPlan(mode=MODE)
    assert approved.caps == CAPS == (1, 2, 4)
    assert (approved.workflows, approved.repeats, approved.timeout_ms) == (8, 1, 30000)
    assert approved.warmup is True
    assert [level_deadline_ms(approved, cap) for cap in CAPS] == [
        270_000,
        150_000,
        90_000,
    ]
    with pytest.raises(ValidationError):
        approved.workflows = 16  # Frozen once validated.


@pytest.mark.parametrize(
    "changes",
    [
        {"mode": "anything-else"},
        {"caps": ()},
        {"caps": (0,)},
        {"caps": (3,)},
        {"caps": (8,)},
        {"caps": (16,)},
        {"caps": (2, 1)},
        {"caps": (1, 1)},
        {"caps": (1, 2, 4, 4)},
        {"caps": (True,)},
        {"caps": ("1",)},
        {"caps": (1.0,)},
        {"workflows": 1},
        {"workflows": 17},
        {"workflows": True},
        {"workflows": "8"},
        {"repeats": 0},
        {"repeats": 4},
        {"timeout_ms": 0},
        {"timeout_ms": 30_001},
        {"warmup": "yes"},
        {"endpoint": "http://127.0.0.1:4318"},
        {"runtime": "langgraph"},
    ],
)
def test_out_of_range_or_unknown_plan_values_are_rejected(changes):
    with pytest.raises(ValidationError):
        BenchmarkPlan(**{"mode": MODE, **changes})


@pytest.mark.parametrize(
    "kind", ["mapping", "text", "caps", "count", "subclass", "partial"]
)
async def test_forged_plans_execute_nothing(monkeypatch, kind):
    service = Service(monkeypatch)

    class Wider(BenchmarkPlan):
        pass

    forged = {
        "mapping": {"mode": MODE},
        "text": MODE,
        "caps": BenchmarkPlan.model_construct(
            mode=MODE, caps=(8,), workflows=8, repeats=1, timeout_ms=1, warmup=False
        ),
        "count": BenchmarkPlan.model_construct(
            mode=MODE, caps=CAPS, workflows=1000, repeats=1, timeout_ms=1, warmup=False
        ),
        "subclass": Wider(mode=MODE),
        "partial": BenchmarkPlan.model_construct(mode=MODE),
    }[kind]
    if kind == "partial":
        del forged.__dict__["caps"]
    with pytest.raises(BenchmarkError):
        await run_benchmark(forged)
    assert service.requests == []


async def test_caps_bound_admission_and_measurements_follow_the_clock(monkeypatch):
    report, service = await measured(monkeypatch)
    assert report.passed and len(service.requests) == 24
    assert [level.cap for level in report.levels] == [1, 2, 4]
    assert [level.peak_in_flight for level in report.levels] == [1, 2, 4]
    assert service.peak == 4 and service.active == 0
    assert [level.wall_seconds for level in report.levels] == [16.0, 8.0, 4.0]
    assert [level.throughput_per_second for level in report.levels] == [0.5, 1.0, 2.0]
    assert [level.overlap_factor for level in report.levels] == [1.0, 2.0, 4.0]
    assert [level.speedup_vs_cap_1 for level in report.levels] == [1.0, 2.0, 4.0]
    for level in report.levels:
        assert level.requested == level.completed == 8
        assert level.failed == level.timed_out == level.denied == level.cancelled == 0
        assert (
            level.duration_min_seconds
            == level.duration_median_seconds
            == level.duration_max_seconds
            == 2.0
        )
        assert level.integrity and not level.deadline_exceeded
        assert level.workers_reaped == 16
        assert level.observed_started == level.observed_completed == 8
        assert level.observation_drops == level.observation_adapter_failures == 0
        assert level.deadline_ms == level_deadline_ms(report.plan, level.cap)
    assert (
        report.model_calls
        == report.provider_calls
        == report.external_calls
        == report.retries
        == 0
    )


async def test_a_slower_higher_cap_is_reported_and_does_not_fail(monkeypatch):
    report, _ = await measured(monkeypatch, steps=(2.0, 6.0, 2.0))
    cap_two = report.levels[1]
    assert cap_two.wall_seconds == 24.0
    assert cap_two.speedup_vs_cap_1 == pytest.approx(16 / 24)
    assert cap_two.speedup_vs_cap_1 < 1
    assert cap_two.passed and report.passed


async def test_peak_is_limited_by_the_workload_when_the_cap_is_larger(monkeypatch):
    report, service = await measured(monkeypatch, caps=(4,), workflows=2)
    (level,) = report.levels
    assert level.peak_in_flight == service.peak == 2
    assert level.speedup_vs_cap_1 is None and level.passed


async def test_speedup_is_absent_without_a_cap_one_baseline(monkeypatch):
    report, _ = await measured(monkeypatch, caps=(2, 4))
    assert report.passed
    assert [level.speedup_vs_cap_1 for level in report.levels] == [None, None]
    assert [level.throughput_per_second for level in report.levels] == [1.0, 2.0]


async def test_repeats_are_reported_separately_with_fresh_state(monkeypatch):
    report, service = await measured(
        monkeypatch, steps=(1.0, 1.0, 3.0, 1.0), caps=(1, 2), workflows=2, repeats=2
    )
    assert report.passed
    assert [(level.repeat, level.cap) for level in report.levels] == [
        (1, 1),
        (1, 2),
        (2, 1),
        (2, 2),
    ]
    assert [level.wall_seconds for level in report.levels] == [2.0, 1.0, 6.0, 1.0]
    assert [level.speedup_vs_cap_1 for level in report.levels] == [1.0, 2.0, 1.0, 6.0]
    assert all(level.observed_started == 2 for level in report.levels)
    assert len(service.requests) == 8


async def test_identical_work_uses_fresh_identities_and_fixed_authority(
    monkeypatch,
):
    for key in ("OPENAI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.setenv(key, "private-secret")
    service = Service(monkeypatch)
    report = await run_benchmark(BenchmarkPlan(mode=MODE))
    assert report.passed and report.warmup_completed is True
    assert len(service.requests) == 1 + 8 * 3
    assert len({item.workflow_id for item in service.requests}) == 25
    assert len({item.task.task_id for item in service.requests}) == 25
    for item in service.requests:
        assert item.task.instruction == INSTRUCTION
        assert item.runtime == RuntimeId.GOOGLE_ADK
        assert item.topology == GraphTopology.COORDINATOR_WORKER
        assert item.limits == ExecutionLimits(max_steps=4, timeout_ms=30000)
    # The discarded warm-up is not counted in any level.
    assert all(level.observed_started == 8 for level in report.levels)
    for level in report.levels:
        assert level.wall_seconds >= level.duration_max_seconds


async def test_failed_warm_up_stops_before_any_level(monkeypatch):
    async def broken(index, request):
        raise ExecutionFailureError("warm-up failure")

    service = Service(monkeypatch, broken)
    report = await run_benchmark(BenchmarkPlan(mode=MODE))
    assert report.warmup_completed is False and report.levels == ()
    assert not report.passed and len(service.requests) == 1
    assert report.model_calls is report.retries is None


@pytest.mark.parametrize(
    "error,field",
    [
        (ExecutionFailureError, "failed"),
        (RuntimeError, "failed"),
        (ExecutionTimeoutError, "timed_out"),
        (InvalidRuntimeOutputError, "denied"),
        (StepBudgetExceededError, "denied"),
    ],
)
async def test_one_failure_is_counted_and_closes_the_run(monkeypatch, error, field):
    async def behaviour(index, request):
        if index == 3:
            raise error("private-secret")

    service = Service(monkeypatch, behaviour)
    report = await run_benchmark(plan())
    (level,) = report.levels  # Later caps do not run after a failed level.
    assert len(service.requests) == 8  # Siblings of the failure still finished.
    assert level.completed == 7 and getattr(level, field) == 1
    assert level.completed + level.failed + level.timed_out + level.denied == 8
    assert not level.passed and not report.passed
    assert level.workers_reaped == 14
    for name in (
        "throughput_per_second",
        "duration_min_seconds",
        "duration_median_seconds",
        "duration_max_seconds",
        "overlap_factor",
        "speedup_vs_cap_1",
    ):
        assert getattr(level, name) is None
    assert report.model_calls is report.provider_calls is None
    assert report.external_calls is report.retries is None
    assert "private-secret" not in report.model_dump_json()


@pytest.mark.parametrize("kind", ["other_text", "foreign", "text", "mapping"])
async def test_untrusted_service_output_fails_integrity(monkeypatch, kind):
    async def behaviour(index, request):
        if index != 2:
            return None
        if kind == "other_text":
            return accepted(request, "a different amount of work")
        if kind == "foreign":
            other = request.model_copy(update={"workflow_id": uuid4()})
            return accepted(other)
        return EXPECTED_OUTPUT if kind == "text" else accepted(request).model_dump()

    Service(monkeypatch, behaviour)
    report = await run_benchmark(plan())
    (level,) = report.levels
    assert not level.integrity and not level.passed and not report.passed
    assert level.completed == 7 and level.failed == 1
    assert level.throughput_per_second is None


async def test_level_deadline_cancels_settles_and_reports(monkeypatch):
    monkeypatch.setattr(benchmark, "MARGIN_MS", 0)

    async def hang(index, request):
        await asyncio.Event().wait()

    service = Service(monkeypatch, hang)
    report = await asyncio.wait_for(
        run_benchmark(plan(caps=(1,), workflows=2, timeout_ms=30)), 20
    )
    (level,) = report.levels
    assert level.deadline_ms == 60 and level.deadline_exceeded
    assert level.cancelled == 2 and level.completed == 0
    assert level.peak_in_flight == 1 and level.observed_started == 1
    assert not level.passed and not report.passed
    assert service.active == 0 and service.left == 1  # Second was never admitted.
    assert asyncio.all_tasks() == {asyncio.current_task()}


async def test_caller_cancellation_waits_for_cleanup_and_leaves_no_tasks(
    monkeypatch,
):
    entered, cleaned = asyncio.Event(), []

    async def slow_cleanup(index, request):
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await asyncio.sleep(0.05)  # Stands in for kill-and-reap.
            cleaned.append(index)
            raise

    service = Service(monkeypatch, slow_cleanup)
    running = asyncio.create_task(run_benchmark(plan(caps=(2,), workflows=4)))
    await asyncio.wait_for(entered.wait(), 20)
    await asyncio.sleep(0)
    running.cancel()
    await asyncio.sleep(0)
    running.cancel()  # Repeated cancellation cannot abandon in-flight cleanup.
    with pytest.raises(asyncio.CancelledError):
        await running
    assert sorted(cleaned) == [0, 1]
    assert service.active == 0 and len(service.requests) == 2
    assert asyncio.all_tasks() == {asyncio.current_task()}


async def test_observation_adapter_failure_cannot_change_results(monkeypatch):
    class Broken:
        def emit(self, trace):
            raise RuntimeError("private-secret")

        def state(self, snapshot):
            raise RuntimeError("private-secret")

    clean, _ = await measured(monkeypatch)
    noisy, _ = await measured(monkeypatch, adapters=(Broken(),))
    assert noisy.passed
    assert all(level.observation_adapter_failures > 0 for level in noisy.levels)
    ignore = {"levels": {"__all__": {"observation_adapter_failures"}}}
    assert noisy.model_dump(exclude=ignore) == clean.model_dump(exclude=ignore)
    assert "private-secret" not in noisy.model_dump_json()


async def test_report_is_payload_free_and_claims_only_local_evidence(monkeypatch):
    report, _ = await measured(monkeypatch)
    text = report.model_dump_json()
    assert INSTRUCTION not in text and EXPECTED_OUTPUT not in text
    assert not UUID_TEXT.search(text) and "pid" not in text.lower()
    assert report.classification == "local_single_host"
    assert report.evidence_class == "deterministic_local_multi_process"
    assert report.host.logical_cpus == os.cpu_count()
    names = {
        name.lower()
        for model in (BenchmarkPlan, HostFacts, LevelResult, BenchmarkReport)
        for name in model.model_fields
    }
    for invented in ("queue", "utilis", "utiliz", "token", "cost", "price", "capacity"):
        assert not any(invented in name for name in names)
    assert BenchmarkReport.model_validate(json.loads(text)) == report


@pytest.mark.parametrize(
    "changes",
    [
        {"completed": 7},
        {"peak_in_flight": 2},
        {"workers_reaped": 15},
        {"observation_drops": 1},
        {"observed_started": 7},
        {"integrity": False},
        {"deadline_exceeded": True},
        {"duration_max_seconds": 99.0},
        {"passed": False},
        {"wall_seconds": float("inf")},
        {"throughput_per_second": 0.0},
        {"speedup_vs_cap_1": -1.0},
    ],
)
async def test_forged_level_and_report_evidence_is_rejected(monkeypatch, changes):
    report, _ = await measured(monkeypatch)
    level = report.levels[0].model_dump()
    with pytest.raises(ValidationError):
        LevelResult.model_validate({**level, **changes})
    whole = report.model_dump()
    for forged in (
        {"levels": whole["levels"][:2]},
        {"levels": whole["levels"][::-1]},
        {"passed": False},
        {"model_calls": None},
        {"warmup_completed": True},
        {"classification": "production"},
    ):
        with pytest.raises(ValidationError):
            BenchmarkReport.model_validate({**whole, **forged})


async def test_real_processes_respect_caps_integrity_and_cleanup(monkeypatch):
    for key in ("OPENAI_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setenv(key, "private-secret")
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    original, children = transport.spawn_worker, []

    async def observed(assignment, directory):
        process = await original(assignment, directory)
        children.append((process, directory))
        return process

    monkeypatch.setattr(transport, "spawn_worker", observed)
    report = await run_benchmark(plan(caps=(1, 2), workflows=2))
    assert report.passed
    assert len(children) == 8  # Two levels, two workflows, two workers each.
    assert all(process.returncode == 0 for process, _ in children)
    assert os.getpid() not in {process.pid for process, _ in children}
    assert all(not Path(directory).exists() for _, directory in children)
    assert [level.peak_in_flight for level in report.levels] == [1, 2]
    for level in report.levels:
        assert level.completed == level.requested == 2
        assert level.integrity and level.workers_reaped == 4
        assert level.observed_started == level.observed_completed == 2
        assert 0 < level.duration_max_seconds <= level.wall_seconds
        assert level.wall_seconds <= level.deadline_ms / 1000
        assert 0 < level.overlap_factor <= level.cap + 1e-6
        assert level.throughput_per_second > 0
    # Speedup is represented, never required to exceed one.
    assert report.levels[0].speedup_vs_cap_1 == 1.0
    assert report.levels[1].speedup_vs_cap_1 > 0
    assert report.model_calls == report.provider_calls == report.external_calls == 0
    text = report.model_dump_json()
    assert "private-secret" not in text and INSTRUCTION not in text
    assert asyncio.all_tasks() == {asyncio.current_task()}


def command():
    spec = importlib.util.spec_from_file_location(
        "module6_benchmark_command", MODULE / "run_benchmark.py"
    )
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_operator_command_does_nothing_without_explicit_run(monkeypatch, capsys):
    service = Service(monkeypatch)
    operator = command()
    assert operator.main([]) == 2
    assert operator.main(["--workflows", "4", "--json"]) == 2
    assert "opt-in" in capsys.readouterr().out
    assert service.requests == []
    for bad in (
        ["--run", "--workflows", "1"],
        ["--run", "--workflows", "17"],
        ["--run", "--repeats", "4"],
        ["--run", "--caps", "8"],
    ):
        with pytest.raises(SystemExit):
            operator.main(bad)
    assert service.requests == []


def test_operator_command_prints_a_validated_report(monkeypatch, capsys):
    service = Service(monkeypatch)
    operator = command()
    assert operator.main(["--run", "--workflows", "2", "--json"]) == 0
    report = BenchmarkReport.model_validate(json.loads(capsys.readouterr().out))
    assert report.passed and report.plan.caps == CAPS
    assert len(service.requests) == 1 + 2 * 3
    assert operator.main(["--run", "--workflows", "2"]) == 0
    text = capsys.readouterr().out
    assert "local_single_host" in text and "not an acceptance criterion" in text
    assert INSTRUCTION not in text and not UUID_TEXT.search(text)


def test_operator_command_reports_failure_without_inventing_values(monkeypatch, capsys):
    async def behaviour(index, request):
        if index == 2:
            raise ExecutionFailureError("private-secret")

    Service(monkeypatch, behaviour)
    assert command().main(["--run", "--workflows", "2"]) == 1
    text = capsys.readouterr().out
    assert "FAILED" in text and "n/a" in text and "not established" in text
    assert "private-secret" not in text
