"""Offline native LangGraph/process acceptance of application runtime enforcement."""

import asyncio
import ctypes
import importlib.util
import json
import sys
import time
from pathlib import Path
from uuid import UUID

import pytest
from multi_agent_orchestration import live_execution as service
from multi_agent_orchestration.live_contracts import (
    LiveAuthorization,
    LiveBudget,
    LiveFailure,
    ModelSelection,
)
from multi_agent_orchestration.live_errors import (
    LiveFailureCategory,
    LiveValidationError,
)
from multi_agent_orchestration.live_execution import (
    LiveRuntimeError,
    execute_live_workflow,
)

CANARY = "SYNTHETIC_RUNTIME_SECRET_47391"


@pytest.fixture(autouse=True)
def reaped_children(monkeypatch):
    """Observe OS process ownership, not merely absence of log messages."""
    spawned = []
    original = asyncio.create_subprocess_exec

    async def observed(*args, **kwargs):
        process = await original(*args, **kwargs)
        spawned.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", observed)
    yield spawned
    assert all(process.returncode is not None for process in spawned)
    assert all(process.stdin.is_closing() for process in spawned)


def authority(**changes):
    budget = {
        "max_model_calls": 4,
        "max_repair_attempts": 1,
        "max_concurrency": 1,
        "deadline_ms": 15000,
        "call_timeout_ms": 3000,
        "max_input_chars": 4096,
        "max_output_tokens": 256,
        "max_reply_bytes": 4096,
    }
    budget.update(changes)
    return LiveAuthorization(
        mode="live-model",
        selection=ModelSelection(
            execution_class="local_model_inference",
            provider="offline_fixture",
            model="synthetic:1",
        ),
        budget=LiveBudget(**budget),
    )


def gateway(tmp_path, scenario):
    source = (
        Path(__file__).with_name("live_gateway_cases.py").read_text(encoding="utf-8")
    )
    log = tmp_path / "calls.jsonl"
    module_path = tmp_path / "offline_gateway_case.py"
    module_path.write_text(
        source + f"\nSCENARIO = {scenario!r}\nLOG = {str(log)!r}\n", encoding="utf-8"
    )
    spec = importlib.util.spec_from_file_location("offline_gateway_case", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.factory, log


def events(log):
    return (
        []
        if not log.exists()
        else [json.loads(x) for x in log.read_text().splitlines()]
    )


def calls(log):
    return [x for x in events(log) if x["event"] == "call"]


def sanitized(error):
    assert isinstance(error.failure, LiveFailure)
    assert error.__cause__ is None and error.__context__ is None
    for text in (
        str(error),
        repr(error),
        repr(error.args),
        repr(vars(error)),
        error.failure.model_dump_json(),
    ):
        assert CANARY not in text


async def run(factory, auth=None, **kwargs):
    return await execute_live_workflow(
        "Synthetic task",
        authorization=authority() if auth is None else auth,
        gateway_factory=factory,
        workflow_id=UUID(int=1),
        task_id=UUID(int=2),
        **kwargs,
    )


@pytest.mark.parametrize("candidate", [None, {}, "live-model", True])
async def test_invalid_authorization_never_constructs_gateway(tmp_path, candidate):
    factory, log = gateway(tmp_path, "happy")
    with pytest.raises(LiveRuntimeError) as caught:
        await execute_live_workflow(
            "Task", authorization=candidate, gateway_factory=factory
        )
    assert not events(log)
    assert caught.value.failure.model_calls == 0
    sanitized(caught.value)


async def test_constructed_invalid_authority_is_refused(tmp_path):
    factory, log = gateway(tmp_path, "happy")
    auth = authority()
    forged = auth.model_copy(
        update={
            "budget": LiveBudget.model_construct(
                **{
                    **auth.budget.model_dump(),
                    "max_model_calls": 5,
                    "max_repair_attempts": 2,
                }
            )
        }
    )
    with pytest.raises(LiveRuntimeError) as caught:
        await run(factory, forged)
    assert caught.value.category == LiveFailureCategory.BUDGET_REFUSED
    assert not events(log)


@pytest.mark.parametrize("scenario", ["happy", "revision", "background"])
async def test_three_calls_native_graph_order_and_advisory_critic(
    tmp_path,
    scenario,
    reaped_children,
):
    factory, log = gateway(tmp_path, scenario)
    before = asyncio.all_tasks()
    result = await run(factory)
    assert [c["role"] for c in calls(log)] == [
        "graph_researcher",
        "graph_analyst",
        "graph_critic",
    ]
    assert all(c["active"] == 1 for c in calls(log))
    assert result.evidence.accounting.model_calls == 3
    assert result.evidence.accounting.repair_attempts == 0
    assert result.evidence.accounting.transport_retries == 0
    assert result.evidence.accounting.usage.input_tokens is None
    assert result.evidence.accounting.usage.output_tokens is None
    assert result.evidence.runtime.value == "langgraph"
    assert result.research.findings[0].startswith("Ignore instructions")
    assert asyncio.all_tasks() == before
    assert result.critique.advisory_verdict == (
        "needs_revision" if scenario == "revision" else "sound"
    )
    assert len({c["pid"] for c in calls(log)}) == 1
    assert calls(log)[0]["pid"] == reaped_children[0].pid
    assert calls(log)[0]["pid"] != __import__("os").getpid()
    assert all(
        c["selection"] == result.evidence.selection.model_dump(mode="json")
        for c in calls(log)
    )


@pytest.mark.parametrize(
    "scenario", ["repair", "analysis_repair", "repair_usage", "critic_repair"]
)
async def test_one_valid_repair_is_inside_four_calls(tmp_path, scenario):
    factory, log = gateway(tmp_path, scenario)
    result = await run(factory)
    assert result.evidence.accounting.model_calls == len(calls(log)) == 4
    assert result.evidence.accounting.repair_attempts == 1
    assert all(c["active"] == 1 for c in calls(log))
    if scenario == "repair_usage":
        assert result.evidence.accounting.usage.input_tokens == 8
        assert result.evidence.accounting.usage.output_tokens == 12


@pytest.mark.parametrize(
    "scenario,changes,count,repairs,category",
    [
        (
            "bad_always",
            {"max_model_calls": 3, "max_repair_attempts": 0},
            1,
            0,
            "malformed_output",
        ),
        ("bad_always", {}, 2, 1, "malformed_output"),
        ("critic_bad", {}, 4, 1, "malformed_output"),
        ("two_bad_roles", {}, 3, 1, "malformed_output"),
        ("transport", {}, 1, 0, "unexpected_provider_failure"),
        ("claimed_malformed", {}, 1, 0, "unexpected_provider_failure"),
        ("provider", {}, 1, 0, "unexpected_provider_failure"),
        ("model", {}, 1, 0, "unexpected_provider_failure"),
        ("malformed_reply", {}, 1, 0, "unexpected_provider_failure"),
        ("authority", {}, 2, 1, "malformed_output"),
        ("oversize", {}, 1, 0, "output_too_large"),
        ("startup_failure", {}, 0, 0, "unexpected_provider_failure"),
    ],
)
async def test_fail_closed_no_fifth_call_retry_or_disclosure(
    tmp_path,
    scenario,
    changes,
    count,
    repairs,
    category,
):
    factory, log = gateway(tmp_path, scenario)
    before = asyncio.all_tasks()
    with pytest.raises(LiveRuntimeError) as caught:
        await run(factory, authority(**changes))
    assert len(calls(log)) == caught.value.failure.model_calls == count
    assert caught.value.failure.repair_attempts == repairs
    assert caught.value.category.value == category
    sanitized(caught.value)
    assert asyncio.all_tasks() == before


@pytest.mark.parametrize("scenario", ["hang", "blocking", "delayed"])
async def test_call_timeout_kills_noncooperative_or_late_gateway(tmp_path, scenario):
    factory, log = gateway(tmp_path, scenario)
    started = time.monotonic()
    with pytest.raises(LiveRuntimeError) as caught:
        await run(factory, authority(call_timeout_ms=50))
    assert caught.value.category == LiveFailureCategory.TIMED_OUT
    assert len(calls(log)) == caught.value.failure.model_calls == 1
    assert time.monotonic() - started < 10
    snapshot = events(log)
    await asyncio.sleep(0.25)
    assert events(log) == snapshot
    sanitized(caught.value)


async def test_overall_deadline_bounds_later_calls(tmp_path, monkeypatch):
    from types import SimpleNamespace

    clock = [100.0]
    monkeypatch.setattr(service, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    original = service._Run.call

    async def elapsed_call(self, *args):
        reply = await original(self, *args)
        clock[0] += 6
        return reply

    monkeypatch.setattr(service._Run, "call", elapsed_call)
    factory, log = gateway(tmp_path, "overall")
    with pytest.raises(LiveRuntimeError) as caught:
        await run(factory, authority(deadline_ms=10000, call_timeout_ms=10000))
    assert caught.value.category == LiveFailureCategory.TIMED_OUT
    assert 0 < caught.value.failure.model_calls == len(calls(log)) < 3
    assert all(c["timeout"] < 10000 for c in calls(log))
    assert calls(log)[-1]["timeout"] < calls(log)[0]["timeout"]


async def test_caller_cancellation_reaps_process_and_removes_tasks(tmp_path):
    factory, log = gateway(tmp_path, "hang")
    before = asyncio.all_tasks()
    task = asyncio.create_task(run(factory))
    async with asyncio.timeout(10):
        while not calls(log):
            await asyncio.sleep(0.01)
    task.cancel(CANARY)
    with pytest.raises(asyncio.CancelledError) as caught:
        await task
    assert CANARY not in str(caught.value)
    assert asyncio.all_tasks() == before
    snapshot = events(log)
    await asyncio.sleep(0.1)
    assert events(log) == snapshot


@pytest.mark.parametrize(
    "scenario,expected", [("usage", (6, 9)), ("mixed_usage", (6, None))]
)
async def test_usage_is_bounded_provider_reported_and_unavailable_is_not_zero(
    tmp_path, scenario, expected
):
    factory, _ = gateway(tmp_path, scenario)
    result = await run(factory)
    usage = result.evidence.accounting.usage
    assert (usage.input_tokens, usage.output_tokens) == expected
    assert "cost" not in type(usage).model_fields


@pytest.mark.parametrize("instruction", ["", " ", 42, "x" * 4097, "bad\ud800"])
async def test_bad_task_zero_gateway_calls(tmp_path, instruction):
    factory, log = gateway(tmp_path, "happy")
    with pytest.raises(LiveValidationError):
        await execute_live_workflow(
            instruction, authorization=authority(), gateway_factory=factory
        )
    assert not events(log)


async def test_repeated_cancellation_during_spawn_retains_process_ownership(
    tmp_path,
    monkeypatch,
):
    factory, _ = gateway(tmp_path, "hang")
    original = asyncio.create_subprocess_exec
    created = asyncio.Event()
    release = asyncio.Event()

    async def interrupted_spawn(*args, **kwargs):
        process = await original(*args, **kwargs)
        created.set()
        await release.wait()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", interrupted_spawn)
    before = asyncio.all_tasks()
    task = asyncio.create_task(run(factory))
    async with asyncio.timeout(10):
        await created.wait()
    task.cancel(CANARY)
    await asyncio.sleep(0)
    task.cancel(CANARY)
    await asyncio.sleep(0)
    release.set()
    with pytest.raises(asyncio.CancelledError) as caught:
        await task
    assert CANARY not in str(caught.value)
    assert asyncio.all_tasks() == before


async def test_cleanup_exception_is_sanitized_after_reaping(tmp_path, monkeypatch):
    factory, log = gateway(tmp_path, "happy")
    original = service._Run.stop

    async def failing_stop(self):
        await original(self)
        raise OSError(CANARY)

    monkeypatch.setattr(service._Run, "stop", failing_stop)
    with pytest.raises(LiveRuntimeError) as caught:
        await run(factory)
    assert len(calls(log)) == caught.value.failure.model_calls == 3
    sanitized(caught.value)


async def test_success_cannot_cross_deadline_during_cleanup(tmp_path, monkeypatch):
    from types import SimpleNamespace

    factory, log = gateway(tmp_path, "happy")
    original = service._Run.stop

    async def late_stop(self):
        await original(self)
        monkeypatch.setattr(
            service,
            "time",
            SimpleNamespace(
                monotonic=lambda: self.deadline + 1,
            ),
        )

    monkeypatch.setattr(service._Run, "stop", late_stop)
    with pytest.raises(LiveRuntimeError) as caught:
        await run(factory)
    assert caught.value.category == LiveFailureCategory.TIMED_OUT
    assert len(calls(log)) == caught.value.failure.model_calls == 3


async def test_insufficient_process_budget_has_zero_model_calls(tmp_path):
    factory, log = gateway(tmp_path, "happy")
    with pytest.raises(LiveRuntimeError) as caught:
        await run(factory, authority(deadline_ms=1, call_timeout_ms=1))
    assert caught.value.category == LiveFailureCategory.BUDGET_REFUSED
    assert caught.value.failure.model_calls == len(calls(log)) == 0


async def test_overall_deadline_includes_factory_startup(tmp_path, reaped_children):
    factory, log = gateway(tmp_path, "startup_hang")
    with pytest.raises(LiveRuntimeError) as caught:
        await run(factory, authority(deadline_ms=2000, call_timeout_ms=1000))
    assert caught.value.category == LiveFailureCategory.TIMED_OUT
    assert caught.value.failure.model_calls == len(calls(log)) == 0
    assert len(reaped_children) == 1
    sanitized(caught.value)


async def test_caller_mutation_cannot_change_the_authorized_snapshot(tmp_path):
    factory, log = gateway(tmp_path, "delayed")
    auth = authority()
    task = asyncio.create_task(run(factory, auth))
    async with asyncio.timeout(10):
        while not calls(log):
            await asyncio.sleep(0.01)
    auth.selection.__dict__["provider"] = "hijacked"
    auth.budget.__dict__["max_model_calls"] = 99
    auth.__dict__["mode"] = "not-authorized"
    result = await task
    assert len(calls(log)) == 3
    assert result.evidence.selection.provider == "offline_fixture"
    assert result.evidence.budget.max_model_calls == 4
    assert all(c["selection"]["provider"] == "offline_fixture" for c in calls(log))


async def test_runtime_preserves_canonical_identifiers_and_three_call_budget(tmp_path):
    class Identifier(UUID):
        def __str__(self):
            raise AssertionError("Caller UUID behavior invoked")

    factory, log = gateway(tmp_path, "happy")
    caller = Identifier(int=41)
    object.__setattr__(caller, "payload", CANARY)
    result = await execute_live_workflow(
        "Task",
        authorization=authority(max_model_calls=3, max_repair_attempts=0),
        gateway_factory=factory,
        workflow_id=caller,
        task_id=caller,
    )
    assert len(calls(log)) == 3
    assert type(result.evidence.workflow_id) is UUID
    assert type(result.evidence.task_id) is UUID
    assert result.evidence.workflow_id.int == result.evidence.task_id.int == 41
    assert CANARY not in result.evidence.model_dump_json()


async def test_maximum_task_and_role_content_fit_bounded_requests_including_repair(
    tmp_path,
):
    factory, log = gateway(tmp_path, "max_content")
    result = await execute_live_workflow(
        '"' * 4096,
        authorization=authority(),
        gateway_factory=factory,
    )
    assert result.evidence.accounting.model_calls == len(calls(log)) == 4
    assert len(result.research.findings) == 3
    assert all(len(c["prompt"]) <= 8192 for c in calls(log))


@pytest.mark.parametrize("scenario", ["no_authority", "transport"])
async def test_caller_exception_context_cannot_cross_runtime_boundary(
    tmp_path, scenario
):
    factory, _ = gateway(tmp_path, "transport")
    try:
        raise RuntimeError(CANARY)
    except RuntimeError:
        with pytest.raises(LiveRuntimeError) as caught:
            await execute_live_workflow(
                "Task",
                authorization=None if scenario == "no_authority" else authority(),
                gateway_factory=factory,
            )
    sanitized(caught.value)


async def test_caller_context_cannot_cross_input_validation_boundary(tmp_path):
    factory, log = gateway(tmp_path, "happy")
    try:
        raise RuntimeError(CANARY)
    except RuntimeError:
        with pytest.raises(LiveValidationError) as caught:
            await execute_live_workflow(
                "", authorization=authority(), gateway_factory=factory
            )
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert CANARY not in repr(vars(caught.value))
    assert not events(log)


async def test_gateway_environment_does_not_inherit_parent_secrets(
    tmp_path, monkeypatch
):
    factory, _ = gateway(tmp_path, "happy")
    monkeypatch.setenv("SYNTHETIC_RUNTIME_PARENT_SECRET", CANARY)
    original = asyncio.create_subprocess_exec
    environments = []

    async def observed(*args, **kwargs):
        environments.append(kwargs.get("env"))
        return await original(*args, **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", observed)
    result = await run(factory)
    assert result.evidence.accounting.model_calls == 3
    assert len(environments) == 1 and environments[0] is not None
    assert set(environments[0]) <= {
        "SYSTEMROOT",
        "WINDIR",
        "PYTHON_DOTENV_DISABLED",
        "OTEL_SDK_DISABLED",
        "LANGSMITH_TRACING",
        "LANGCHAIN_TRACING_V2",
        "DO_NOT_TRACK",
    }
    assert CANARY not in repr(environments[0])
    assert environments[0]["PYTHON_DOTENV_DISABLED"] == "1"
    assert environments[0]["LANGSMITH_TRACING"] == "false"


def assert_worker_exited(process):
    """Check the owned PID independently of asyncio's completed-wait state."""
    assert process.returncode is not None
    if sys.platform == "win32":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.GetExitCodeProcess.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x1000, False, process.pid)
        if handle:
            code = ctypes.c_ulong()
            try:
                assert kernel.GetExitCodeProcess(handle, ctypes.byref(code))
                assert code.value != 259  # STILL_ACTIVE
            finally:
                kernel.CloseHandle(handle)


@pytest.mark.parametrize("scenario", ["hang", "delayed"])
async def test_stalled_parent_repeatedly_reaps_before_timeout_propagates(
    tmp_path, scenario, monkeypatch, reaped_children
):
    # Warm imports/graph compilation outside the deliberately short test budget.
    warm_factory, _ = gateway(tmp_path, "happy")
    await run(warm_factory)
    original_stop = service._Run.stop
    deadlines = []

    async def observed_stop(self):
        deadlines.append((self.deadline - self.started, self.work_deadline))
        await original_stop(self)
        assert_worker_exited(self.process)

    monkeypatch.setattr(service._Run, "stop", observed_stop)
    for iteration in range(3):
        directory = tmp_path / str(iteration)
        directory.mkdir()
        factory, log = gateway(directory, scenario)
        before = asyncio.all_tasks()
        task = asyncio.create_task(
            run(factory, authority(deadline_ms=2000, call_timeout_ms=1500))
        )
        async with asyncio.timeout(10):
            while not calls(log):
                assert not task.done(), "Workflow ended before synchronized dispatch"
                await asyncio.sleep(0.005)
        # Real elapsed time, no replacement clock. A delayed child can produce
        # its reply while the parent is stalled; that result must be discarded.
        time.sleep(2.1)
        with pytest.raises(LiveRuntimeError) as caught:
            await task
        assert caught.value.category == LiveFailureCategory.TIMED_OUT
        assert caught.value.failure.model_calls == len(calls(log)) == 1
        assert caught.value.failure.repair_attempts == 0
        assert asyncio.all_tasks() == before
        assert len(reaped_children) == iteration + 2  # Warmup plus one per run.
        process = reaped_children[-1]
        assert_worker_exited(process)
        assert await process.wait() == process.returncode
        sanitized(caught.value)
    assert all(deadline == 2.0 for deadline, _ in deadlines)


async def test_reap_allowance_is_independent_and_bounded(monkeypatch):
    from types import SimpleNamespace

    killed = False
    waited = False
    allowances = []
    original_wait_for = asyncio.wait_for

    async def read(_size):
        assert killed
        return b""

    async def wait():
        nonlocal waited
        await asyncio.sleep(0.02)  # More than the rejected 1 ms fallback.
        waited = True

    async def observed_wait_for(awaitable, timeout):
        allowances.append(timeout)
        return await original_wait_for(awaitable, timeout)

    def kill():
        nonlocal killed
        killed = True

    process = SimpleNamespace(
        returncode=None,
        kill=kill,
        stdin=None,
        stdout=SimpleNamespace(read=read),
        wait=wait,
    )
    monkeypatch.setattr(asyncio, "wait_for", observed_wait_for)
    # Construct only the supervisor cleanup state, not authorization or a model.
    supervisor = object.__new__(service._Run)
    supervisor.process = process
    supervisor.deadline = time.monotonic() - 10
    await supervisor.stop()
    assert killed and waited
    assert allowances == [service.REAP_TIMEOUT_SECONDS]
    assert 0 < service.REAP_TIMEOUT_SECONDS <= 2.0

    interrupted = asyncio.Event()

    async def stuck_read(_size):
        try:
            await asyncio.Event().wait()
        finally:
            interrupted.set()

    process.stdout.read = stuck_read
    monkeypatch.setattr(service, "REAP_TIMEOUT_SECONDS", 0.03)
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        await supervisor.stop()
    assert interrupted.is_set()
    assert time.monotonic() - started < 1


@pytest.mark.parametrize("scenario", ["happy", "hang", "startup_failure", "transport"])
async def test_expired_cleanup_completes_wait_on_all_exit_paths(
    tmp_path, monkeypatch, scenario, reaped_children
):
    from types import SimpleNamespace

    factory, log = gateway(tmp_path, scenario)
    original = service._Run.stop

    async def expired_stop(self):
        monkeypatch.setattr(
            service, "time", SimpleNamespace(monotonic=lambda: self.deadline + 1)
        )
        await original(self)
        assert_worker_exited(self.process)

    monkeypatch.setattr(service._Run, "stop", expired_stop)
    with pytest.raises(LiveRuntimeError) as caught:
        await run(factory, authority(call_timeout_ms=50))
    assert caught.value.category == LiveFailureCategory.TIMED_OUT
    assert caught.value.failure.model_calls == len(calls(log))
    assert caught.value.failure.model_calls == {
        "happy": 3, "hang": 1, "startup_failure": 0, "transport": 1
    }[scenario]
    assert len(reaped_children) == 1
    sanitized(caught.value)


@pytest.mark.parametrize("terminal", ["success", "cancellation", "ipc", "child"])
async def test_repeated_cancellation_cannot_abandon_in_progress_wait(
    tmp_path, monkeypatch, terminal, reaped_children
):
    factory, log = gateway(tmp_path, "hang" if terminal == "cancellation" else "happy")
    original_spawn = asyncio.create_subprocess_exec
    original_packet = service._Run.packet
    waiting = asyncio.Event()
    release = asyncio.Event()
    completed_waits = []

    async def observed_spawn(*args, **kwargs):
        process = await original_spawn(*args, **kwargs)
        original_wait = process.wait

        async def delayed_wait():
            result = await original_wait()
            waiting.set()
            await release.wait()
            completed_waits.append(process.pid)
            return result

        process.wait = delayed_wait
        return process

    async def failing_packet(self):
        if self.calls and terminal == "ipc":
            raise OSError(CANARY)
        if self.calls and terminal == "child":
            self.process.kill()
        return await original_packet(self)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", observed_spawn)
    monkeypatch.setattr(service._Run, "packet", failing_packet)
    before = asyncio.all_tasks()
    task = asyncio.create_task(run(factory))
    if terminal == "cancellation":
        async with asyncio.timeout(10):
            while not calls(log):
                await asyncio.sleep(0.005)
        task.cancel(CANARY)
    try:
        async with asyncio.timeout(10):
            await waiting.wait()
        for _ in range(4):
            task.cancel(CANARY)
            await asyncio.sleep(0)
            assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await task
        assert CANARY not in repr(caught.value.args)
        assert caught.value.__context__ is None and caught.value.__cause__ is None
        assert len(reaped_children) == 1
        assert completed_waits == [reaped_children[0].pid]
        assert_worker_exited(reaped_children[0])
        assert asyncio.all_tasks() == before
    finally:
        release.set()
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
