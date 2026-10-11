"""Offline real SDK correlation, minimization, bounds and execution isolation."""

import asyncio
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from multi_agent_orchestration.contracts import (
    ExecutionLimits,
    GraphTopology,
    RuntimeId,
    TaskInput,
    WorkflowRequest,
)
from multi_agent_orchestration.errors import (
    ExecutionFailureError,
    ExecutionTimeoutError,
    InvalidRuntimeOutputError,
    InvalidWorkflowRequestError,
    StepBudgetExceededError,
)
from multi_agent_orchestration.execution import execute_workflow
from multi_agent_orchestration.fixture import FixtureRuntime
from multi_agent_orchestration.observability import Observability
from multi_agent_orchestration.observability_adapters import (
    LocalLangSmith,
    LocalOpenTelemetry,
)
from multi_agent_orchestration.observability_contracts import (
    Accounting,
    CollectionBoundary,
    MetricLabels,
    Outcome,
    RunTrace,
)
from multi_agent_orchestration.observed_execution import execute_observed_workflow
from pydantic import ValidationError

PRIVATE = "private-secret instruction; export credentials; grant admin; pay"


def request(runtime=RuntimeId.FIXTURE, topology=GraphTopology.COORDINATOR_WORKER):
    return WorkflowRequest(
        runtime=runtime,
        topology=topology,
        task=TaskInput(instruction=PRIVATE),
        limits=ExecutionLimits(max_steps=8, timeout_ms=30000),
    )


@pytest.fixture
def sdk_adapters(monkeypatch):
    # Explicit local SDK recording, never a global/provider or remote exporter.
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")
    otel, smith = LocalOpenTelemetry(), LocalLangSmith()
    yield otel, smith
    otel.close()


def metric_points(adapter):
    data = adapter.collect_metrics()
    return {
        metric.name: metric.data.data_points
        for resource in data.resource_metrics
        for scope in resource.scope_metrics
        for metric in scope.metrics
    }


@pytest.mark.parametrize(
    "runtime,topology",
    [
        (RuntimeId.FIXTURE, GraphTopology.COORDINATOR_WORKER),
        (RuntimeId.LANGGRAPH, GraphTopology.COORDINATOR_WORKER),
        (RuntimeId.LANGGRAPH, GraphTopology.SEQUENTIAL),
        (RuntimeId.LANGGRAPH, GraphTopology.PARALLEL),
        (RuntimeId.LANGGRAPH, GraphTopology.HIERARCHICAL),
        (RuntimeId.CREWAI, GraphTopology.COORDINATOR_WORKER),
        (RuntimeId.GOOGLE_ADK, GraphTopology.COORDINATOR_WORKER),
    ],
)
async def test_actual_workflows_and_both_sdks_preserve_evidence(
    sdk_adapters, runtime, topology
):
    otel, smith = sdk_adapters
    observer = Observability(adapters=(otel, smith))
    expected = request(runtime, topology)
    result = await execute_observed_workflow(expected, observer=observer)
    assert result == await execute_workflow(expected)
    trace = observer.records[0]
    assert trace.workflow_id == result.evidence.workflow_id == expected.workflow_id
    assert trace.task_id == result.result.task_id == expected.task.task_id
    assert trace.runtime == runtime and trace.topology == topology
    assert trace.outcome == Outcome.COMPLETED
    assert trace.accounting.model_calls == trace.accounting.external_calls == 0
    assert trace.accounting.retries == 0
    assert trace.accounting.provider_calls is None
    assert observer.metrics.active == 0 and observer.metrics.completed == 1
    spans = tuple(otel._spans)
    assert len(spans) == 1 + len(trace.steps)
    assert all(span.context.trace_id == trace.trace_id.int for span in spans)
    assert spans[0].context.span_id == int(trace.span_id, 16)
    assert [event.name for event in spans[0].events] == [
        "workflow.started",
        "workflow.completed",
    ]
    assert spans[0].start_time == trace.started_ns
    assert spans[0].end_time == trace.ended_ns
    for step, span in zip(trace.steps, spans[1:], strict=True):
        assert span.parent.span_id == int(trace.span_id, 16)
        assert span.context.span_id == int(step.span_id, 16)
        assert span.attributes["role"] == step.role.value
        assert span.start_time == span.end_time == trace.ended_ns
    tree = smith._trees[0]
    assert tree.trace_id == tree.id == trace.trace_id
    assert tree.extra["metadata"]["otel_span_id"] == trace.span_id
    assert tree.ls_client is None and tree.session_name == "module6-offline"
    assert len(tree.child_runs) == len(trace.steps)
    assert all(
        child.trace_id == trace.trace_id and child.parent_run_id == tree.id
        for child in tree.child_runs
    )
    serialized = trace.model_dump_json() + tree.model_dump_json() + str(spans)
    assert PRIVATE not in serialized
    assert "private-secret" not in serialized
    assert "instruction" not in trace.model_dump()
    points = metric_points(otel)
    assert points["module6.workflow.finished"][0].value == 1
    assert points["module6.model.calls"][0].value == 0
    assert points["module6.workflow.active"][0].value == 0
    assert points["module6.workflow.duration"][0].count == 1


async def test_real_distributed_completion_and_reaping_correlate(sdk_adapters):
    from multi_agent_orchestration import _distributed_processes as transport

    otel, smith = sdk_adapters
    observer = Observability(adapters=(otel, smith))
    expected = request(RuntimeId.GOOGLE_ADK)
    # Real accepted IPC/native process service, no synthetic distribution.
    result = await execute_observed_workflow(
        expected, observer=observer, distributed=True
    )
    trace = observer.records[0]
    assert trace.distributed and trace.workers_at_barrier == trace.workers_reaped == 2
    assert tuple(step.worker_pid for step in trace.steps) == tuple(
        worker.pid for worker in result.evidence.workers
    )
    assert tuple(step.assignment_id for step in trace.steps) == tuple(
        worker.assignment_id for worker in result.evidence.workers
    )
    assert trace.accounting.provider_calls == 0
    assert metric_points(otel)["module6.worker.reaped"][0].value == 2
    assert transport.MAX_PACKET_BYTES == 16384
    assert len(smith._trees[0].child_runs) == 2


@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_observed_real_process_failure_finishes_after_reaping(
    monkeypatch, sdk_adapters, mode
):
    from multi_agent_orchestration import _distributed_processes as transport

    children, entered = [], set()
    ready = asyncio.Event()
    original = transport.spawn_worker

    async def tracked(assignment, directory):
        child = await original(assignment, directory)
        children.append((child, Path(directory)))
        return child

    async def hold(connection):
        entered.add(connection.assignment.worker)
        if len(entered) == 2:
            ready.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(transport, "spawn_worker", tracked)
    monkeypatch.setattr(
        transport, "release_worker" if mode == "cancel" else "receive_ready", hold
    )
    observer = Observability(adapters=sdk_adapters)
    expected = request(RuntimeId.GOOGLE_ADK)
    if mode == "timeout":
        expected = expected.model_copy(
            update={"limits": ExecutionLimits(max_steps=4, timeout_ms=1000)}
        )
    baseline = asyncio.all_tasks()
    task = asyncio.create_task(
        execute_observed_workflow(expected, observer=observer, distributed=True)
    )
    if mode == "cancel":
        await asyncio.wait_for(ready.wait(), 25)
        assert len(children) == 2 and all(p.returncode is None for p, _ in children)
        task.cancel()
    with pytest.raises(
        asyncio.CancelledError if mode == "cancel" else ExecutionTimeoutError
    ):
        await task
    assert len(children) == 2
    assert all(
        child.returncode is not None and not directory.exists()
        for child, directory in children
    )
    assert observer.metrics.active == 0
    trace = observer.records[0]
    assert trace.outcome == (
        Outcome.CANCELLED if mode == "cancel" else Outcome.TIMED_OUT
    )
    assert trace.steps == () and trace.workers_reaped is None
    await asyncio.sleep(0)
    assert not (asyncio.all_tasks() - baseline - {asyncio.current_task()})


async def test_telemetry_failure_cannot_convert_failed_execution_to_success():
    class Runtime(FixtureRuntime):
        async def execute(self, expected):
            raise RuntimeError(PRIVATE)

    observer = Observability(adapters=(BrokenAdapter(),))
    with pytest.raises(ExecutionFailureError) as error:
        await execute_observed_workflow(request(), observer=observer, runtime=Runtime())
    assert type(error.value.__cause__) is RuntimeError
    assert observer.records[0].outcome == Outcome.FAILED
    assert observer.metrics.failed == 1 and observer.metrics.adapter_failures == 3


@pytest.mark.parametrize(
    "name",
    [
        "LANGSMITH_API_KEY",
        "LANGSMITH_TRACING",
        "LANGCHAIN_TRACING_V2",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_HEADERS",
        "LANGSMITH_PROJECT",
        "LANGSMITH_ENDPOINT",
    ],
)
async def test_ambient_flags_keys_and_destinations_never_authorize(
    monkeypatch, sdk_adapters, name
):
    from langsmith import Client
    from langsmith.run_trees import RunTree

    monkeypatch.setenv(name, "true" if "TRACING" in name else "private-secret")

    def forbidden(*args, **kwargs):
        pytest.fail("Network/client delivery must never be invoked")

    monkeypatch.setattr(Client, "__init__", forbidden)
    monkeypatch.setattr(RunTree, "post", forbidden)
    monkeypatch.setattr(RunTree, "patch", forbidden)
    otel, smith = sdk_adapters
    observer = Observability(adapters=(otel, smith))
    await execute_observed_workflow(request(RuntimeId.LANGGRAPH), observer=observer)
    assert observer.metrics.adapter_failures == 0
    tree = smith._trees[0]
    assert tree.session_name == "module6-offline" and tree.ls_client is None
    assert "private-secret" not in tree.model_dump_json()
    assert "private-secret" not in str(tuple(otel._spans))


class BrokenAdapter:
    def emit(self, trace):
        raise RuntimeError(PRIVATE)

    def state(self, snapshot):
        raise RuntimeError(PRIVATE)


async def test_adapter_failure_does_not_change_success_or_trusted_evidence(caplog):
    observer = Observability(adapters=(BrokenAdapter(),))
    expected = request()
    result = await execute_observed_workflow(expected, observer=observer)
    assert result == await execute_workflow(expected)
    assert observer.metrics.adapter_failures == 3
    assert observer.metrics.completed == 1 and observer.metrics.active == 0
    assert PRIVATE not in caplog.text + observer.records[0].model_dump_json()


@pytest.mark.parametrize("failed", [False, True])
async def test_adapter_cancellation_cannot_cancel_or_reclassify_execution(failed):
    class CancelAdapter:
        def emit(self, trace):
            raise asyncio.CancelledError

        def state(self, snapshot):
            raise asyncio.CancelledError

    class Runtime(FixtureRuntime):
        async def execute(self, expected):
            if failed:
                raise RuntimeError(PRIVATE)
            return await super().execute(expected)

    observer = Observability(adapters=(CancelAdapter(),))
    expected = request()
    if failed:
        with pytest.raises(ExecutionFailureError):
            await execute_observed_workflow(
                expected, observer=observer, runtime=Runtime()
            )
    else:
        assert await execute_observed_workflow(expected, observer=observer) == (
            await execute_workflow(expected)
        )
    assert observer.records[0].outcome == (
        Outcome.FAILED if failed else Outcome.COMPLETED
    )
    assert observer.metrics.active == 0 and observer.metrics.adapter_failures == 3


@pytest.mark.parametrize("where", ["span_collection", "metric", "langsmith"])
async def test_actual_sdk_collection_failure_is_sanitized_and_fail_safe(
    sdk_adapters, monkeypatch, where, caplog
):
    from langsmith.run_trees import RunTree

    otel, smith = sdk_adapters

    def broken(*args, **kwargs):
        raise RuntimeError(PRIVATE)

    if where == "span_collection":
        monkeypatch.setattr(otel, "_retain_spans", broken)
    elif where == "metric":
        monkeypatch.setattr(otel._duration, "record", broken)
    else:
        monkeypatch.setattr(RunTree, "end", broken)
    observer = Observability(adapters=sdk_adapters)
    expected = request()
    assert await execute_observed_workflow(expected, observer=observer) == (
        await execute_workflow(expected)
    )
    assert observer.metrics.adapter_failures == 1 and observer.metrics.active == 0
    assert len(observer.records) == 1
    assert PRIVATE not in caplog.text


@pytest.mark.parametrize("nested", ["accounting", "step", "volume"])
async def test_nested_bypasses_rejected_before_sdk_serialization(
    sdk_adapters, nested, caplog, recwarn
):
    observer = Observability()
    await execute_observed_workflow(request(), observer=observer)
    trace = observer.records[0]
    if nested == "accounting":
        forged = trace.model_copy(
            update={
                "accounting": trace.accounting.model_copy(update={"api_key": PRIVATE})
            }
        )
    elif nested == "step":
        forged = trace.model_copy(
            update={"steps": (trace.steps[0].model_copy(update={"prompt": PRIVATE}),)}
        )
    else:
        forged = trace.model_copy(update={"steps": trace.steps * 100})
    for adapter in sdk_adapters:
        with pytest.raises(ValueError):
            adapter.emit(forged)
    assert not recwarn and PRIVATE not in caplog.text


@pytest.mark.parametrize("where", ["begin", "finish", "abandon"])
async def test_observation_internal_failure_does_not_replace_execution(
    monkeypatch, where
):
    observer = Observability()

    def broken(*args, **kwargs):
        raise RuntimeError(PRIVATE)

    if where == "abandon":
        monkeypatch.setattr(observer, "finish", broken)
    monkeypatch.setattr(observer, where, broken)
    expected = request()
    assert await execute_observed_workflow(expected, observer=observer) == (
        await execute_workflow(expected)
    )


@pytest.mark.parametrize(
    "mode,outcome",
    [
        ("failure", Outcome.FAILED),
        ("timeout", Outcome.TIMED_OUT),
        ("forgery", Outcome.DENIED),
        ("budget", Outcome.DENIED),
    ],
)
async def test_execution_failure_timeout_and_denial_remain_fail_closed(
    sdk_adapters, mode, outcome, caplog
):
    class Runtime(FixtureRuntime):
        async def execute(self, expected):
            if mode == "failure":
                raise RuntimeError(PRIVATE)
            if mode == "timeout":
                await asyncio.sleep(300)
            if mode == "budget":
                raise StepBudgetExceededError("budget denied")
            candidate = await super().execute(expected)
            return candidate.model_copy(update={"workflow_id": uuid4()})

    observer = Observability(adapters=sdk_adapters)
    expected = request().model_copy(update={"limits": ExecutionLimits(timeout_ms=10)})
    error = {
        "failure": ExecutionFailureError,
        "timeout": ExecutionTimeoutError,
        "forgery": InvalidRuntimeOutputError,
        "budget": StepBudgetExceededError,
    }[mode]
    with pytest.raises(error):
        await execute_observed_workflow(expected, observer=observer, runtime=Runtime())
    trace = observer.records[0]
    assert trace.outcome == outcome and trace.steps == ()
    assert trace.accounting == Accounting()
    assert observer.metrics.active == 0
    assert PRIVATE not in trace.model_dump_json() + caplog.text
    assert sdk_adapters[0]._spans[0].events[-1].name == f"workflow.{outcome.value}"
    assert sdk_adapters[1]._trees[0].error == outcome.value
    assert "module6.model.calls" not in metric_points(sdk_adapters[0])


async def test_cancellation_observed_after_accepted_cleanup(sdk_adapters):
    started, cleaned = asyncio.Event(), asyncio.Event()

    class Runtime(FixtureRuntime):
        async def execute(self, expected):
            started.set()
            try:
                await asyncio.sleep(300)
            finally:
                cleaned.set()

    observer = Observability(adapters=sdk_adapters)
    task = asyncio.create_task(
        execute_observed_workflow(request(), observer=observer, runtime=Runtime())
    )
    await asyncio.wait_for(started.wait(), 2)
    assert observer.metrics.active == 1
    assert metric_points(sdk_adapters[0])["module6.workflow.active"][0].value == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cleaned.is_set()
    assert observer.records[0].outcome == Outcome.CANCELLED
    assert observer.metrics.active == 0 and observer.metrics.cancelled == 1
    assert metric_points(sdk_adapters[0])["module6.workflow.active"][0].value == 0


async def test_concurrent_isolation_capacity_and_no_task_retention(sdk_adapters):
    release, entered = asyncio.Event(), asyncio.Queue()

    class Runtime(FixtureRuntime):
        async def execute(self, expected):
            entered.put_nowait(expected.workflow_id)
            await release.wait()
            return await super().execute(expected)

    observer = Observability(adapters=sdk_adapters)
    expected = [request() for _ in range(20)]
    tasks = [
        asyncio.create_task(
            execute_observed_workflow(item, observer=observer, runtime=Runtime())
        )
        for item in expected
    ]
    for _ in tasks:
        await asyncio.wait_for(entered.get(), 2)
    assert observer.metrics.active == 16 and observer.metrics.observation_drops == 4
    release.set()
    results = await asyncio.gather(*tasks)
    assert len(results) == 20 and observer.metrics.active == 0
    assert len(observer.records) == 16
    assert len({trace.trace_id for trace in observer.records}) == 16
    assert len({trace.span_id for trace in observer.records}) == 16
    identities = {item.evidence.workflow_id: item.result.task_id for item in results}
    assert all(
        identities[trace.workflow_id] == trace.task_id for trace in observer.records
    )
    assert all(task.done() for task in tasks)


async def test_retention_cardinality_and_sdk_resource_bounds(sdk_adapters):
    otel, smith = sdk_adapters
    observer = Observability(adapters=sdk_adapters)
    for _ in range(80):
        await execute_observed_workflow(request(), observer=observer)
    assert len(observer.records) == len(smith._trees) == 32
    assert len(otel._spans) == 128
    assert observer.metrics.observation_drops == 48
    points = metric_points(otel)
    allowed = {"runtime", "topology", "distributed", "outcome"}
    for samples in points.values():
        assert len(samples) == 1
        for point in samples:
            assert set(point.attributes) <= allowed
            assert not point.exemplars
    assert points["module6.workflow.finished"][0].value == 80
    assert len(points["module6.workflow.duration"][0].explicit_bounds) == 6
    assert all(
        len(span.attributes) <= 10 and len(span.events) <= 2 for span in otel._spans
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("prompt", PRIVATE),
        ("api_key", PRIVATE),
        ("exporter", "remote"),
        ("authority", "admin"),
        ("evidence", {}),
        ("span_id", "0000000000000000"),
        ("trace_id", UUID(int=0)),
        ("runtime", "remote"),
        ("started_ns", True),
        ("ended_ns", 1),
        ("duration_ms", float("nan")),
        ("outcome", "live_success"),
        ("steps", []),
        ("accounting", {"model_calls": True}),
        ("accounting", {"estimated_cost_usd": 0}),
        ("accounting", {"input_tokens": 0}),
        (
            "accounting",
            {"provider_calls": 0, "model_calls": 0, "external_calls": 0, "retries": 0},
        ),
    ],
)
async def test_forged_telemetry_rejected_by_both_sdk_boundaries(
    sdk_adapters, field, value
):
    observer = Observability()
    await execute_observed_workflow(request(), observer=observer)
    forged = observer.records[0].model_copy(update={field: value})
    # model_copy does not add unknown fields to model_dump; use raw schema as well.
    raw = observer.records[0].model_dump()
    raw[field] = value
    with pytest.raises(ValidationError):
        RunTrace.model_validate(raw)
    for adapter in sdk_adapters:
        with pytest.raises((ValueError, TypeError)):
            adapter.emit(forged)
    assert not sdk_adapters[0]._spans and not sdk_adapters[1]._trees


@pytest.mark.parametrize(
    "field",
    [
        "workflow_id",
        "task_id",
        "trace_id",
        "pid",
        "agent",
        "error",
        "prompt",
        "provider",
    ],
)
def test_metric_labels_reject_unbounded_or_sensitive_dimensions(field):
    with pytest.raises(ValidationError):
        MetricLabels(
            runtime=RuntimeId.FIXTURE,
            topology=GraphTopology.COORDINATOR_WORKER,
            distributed=False,
            outcome=Outcome.COMPLETED,
            **{field: PRIVATE},
        )


@pytest.mark.parametrize("change", ["foreign_handle", "workflow", "limits", "nested"])
async def test_unowned_handle_or_forged_evidence_never_enters_observation(change):
    observer = Observability()
    expected = request()
    handle = observer.begin(expected, False)
    result = await execute_workflow(expected)
    if change == "foreign_handle":
        handle = replace(handle, span_id="1234567890abcdef")
    elif change == "workflow":
        result = result.model_copy(
            update={
                "evidence": result.evidence.model_copy(update={"workflow_id": uuid4()})
            }
        )
    elif change == "limits":
        result = result.model_copy(
            update={
                "evidence": result.evidence.model_copy(
                    update={"limits": ExecutionLimits()}
                )
            }
        )
    else:
        result = result.model_copy(
            update={"evidence": result.evidence.model_copy(update={"model_calls": 7})}
        )
    with pytest.raises((ValueError, ValidationError)):
        observer.finish(handle, Outcome.COMPLETED, result)
    assert observer.records == ()


async def test_replay_mutation_and_counters_saturate():
    observer = Observability()
    expected = request()
    handle = observer.begin(expected, False)
    result = await execute_workflow(expected)
    trace = observer.finish(handle, Outcome.COMPLETED, result)
    with pytest.raises(ValueError):
        observer.finish(handle, Outcome.COMPLETED, result)
    with pytest.raises(ValidationError):
        trace.runtime = RuntimeId.GOOGLE_ADK
    with pytest.raises(ValidationError):
        trace.accounting.model_calls = 1
    observer._counts["started"] = 1_000_000_000
    observer.begin(request(), False)
    assert observer.metrics.started == 1_000_000_000


@pytest.mark.parametrize(
    "bad",
    [
        None,
        {},
        {"task": {"instruction": PRIVATE}},
        {
            "runtime": "fixture",
            "task": {"instruction": PRIVATE},
            "telemetry": {"endpoint": "remote", "enabled": True},
        },
    ],
)
async def test_invalid_or_implicit_selection_emits_no_untrusted_content(bad):
    observer = Observability()
    with pytest.raises(InvalidWorkflowRequestError) as error:
        await execute_observed_workflow(bad, observer=observer)
    assert PRIVATE not in str(error.value)
    assert observer.records == () and observer.metrics.started == 0


def test_delivery_boundary_cannot_be_enabled_by_data():
    assert not CollectionBoundary().delivery_enabled
    with pytest.raises(ValidationError):
        CollectionBoundary(delivery_enabled=True)
    with pytest.raises(ValidationError):
        CollectionBoundary(endpoint="remote")
    with pytest.raises(ValueError):
        Observability(adapters=(BrokenAdapter(),) * 3)


async def test_global_providers_disable_flags_and_ambient_context_unchanged(
    monkeypatch,
):
    from opentelemetry import metrics, trace

    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    tracer, meter = trace.get_tracer_provider(), metrics.get_meter_provider()
    otel = LocalOpenTelemetry()
    try:
        observer = Observability(adapters=(otel,))
        await execute_observed_workflow(request(), observer=observer)
        assert len(observer.records) == 1 and not otel._spans
        assert observer.metrics.adapter_failures == 0
        assert trace.get_tracer_provider() is tracer
        assert metrics.get_meter_provider() is meter
        assert otel.collect_metrics() is None
    finally:
        otel.close()
