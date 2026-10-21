"""Slice 4 offline SDK metrics: exact vocabulary, semantics and authority bounds."""

import asyncio
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from multi_agent_orchestration import live_metrics as module
from multi_agent_orchestration.canonical_workflow import CanonicalWorkflowError
from multi_agent_orchestration.live_errors import LiveValidationError
from multi_agent_orchestration.live_observation import LiveRuntimeFacts
from multi_agent_orchestration.observability import Observability
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceRequest,
)

from .test_canonical_workflow import calls, gateway, run
from .test_canonical_workflow import reaped as reaped
from .test_live_observation import begin, record

PRIVATE = "PRIVATE_PROMPT_RESPONSE_SECRET_ENV_PATH_METADATA_REASON"
SYNTHETIC = "module6.live.synthetic"
LOCAL = "module6.live.local"


def retain(terminal):
    observer = Observability()
    observer.finish_live(begin(observer, terminal), terminal)
    return observer


def add(metrics, terminal):
    return metrics.record(retain(terminal), terminal.trace_id)


def decoded(metrics):
    packet = ExportMetricsServiceRequest()
    packet.ParseFromString(metrics._batch())
    return packet


def signals(packet):
    return {
        metric.name: metric
        for resource in packet.resource_metrics
        for scope in resource.scope_metrics
        for metric in scope.metrics
    }


def value(metric):
    (point,) = metric.sum.data_points
    return point.as_int


@pytest.fixture
def metrics(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")
    for name in (
        "OTEL_RESOURCE_ATTRIBUTES",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_HEADERS",
        "OTEL_METRICS_EXPORTER",
    ):
        monkeypatch.setenv(name, PRIVATE)

    def forbidden(*args, **kwargs):
        pytest.fail("Metric collection must perform no network activity")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    instance = module.LiveOperationalMetrics()
    yield instance
    instance.close()


@pytest.mark.parametrize("prefix", [0, 1, 2, 3])
@pytest.mark.parametrize(
    "source,namespace",
    [
        ("synthetic_offline", SYNTHETIC),
        ("local_provider_execution", LOCAL),
    ],
)
def test_exact_sdk_metrics_labels_and_role_prefixes(metrics, prefix, source, namespace):
    full = record()
    terminal = record(
        evidence_source=source,
        roles=full.roles[:prefix],
        outcome="completed" if prefix == 3 else "failed",
        category=None if prefix == 3 else "malformed_output",
    )
    observer = retain(terminal)
    before = terminal.model_dump_json()
    assert metrics.record(observer, terminal.trace_id).status == "recorded"
    packet = decoded(metrics)
    data = signals(packet)
    assert set(data) == {
        namespace + ".workflow.finished",
        namespace + ".workflow.duration",
        namespace + ".accounting.observed",
        namespace + ".model.calls",
        namespace + ".workflow.repair_attempts",
    }
    assert value(data[namespace + ".workflow.finished"]) == 1
    assert value(data[namespace + ".accounting.observed"]) == 1
    assert value(data[namespace + ".model.calls"]) == 3
    assert value(data[namespace + ".workflow.repair_attempts"]) == 0
    for metric in data.values():
        if metric.HasField("histogram"):
            (point,) = metric.histogram.data_points
            assert point.count == 1 and point.sum == terminal.duration_ms
            assert list(point.explicit_bounds) == [1, 10, 100, 1000, 10000, 30000]
            assert not point.HasField("min") and not point.HasField("max")
        else:
            (point,) = metric.sum.data_points
            assert metric.sum.is_monotonic
            assert metric.sum.aggregation_temporality == 2  # cumulative SDK wire enum
        labels = {a.key: a.value for a in point.attributes}
        assert set(labels) == {"runtime", "topology", "distributed", "outcome"}
        assert labels["runtime"].string_value == "langgraph"
        assert labels["topology"].string_value == "sequential"
        assert labels["distributed"].bool_value is False
        assert labels["outcome"].string_value == terminal.outcome.value
        assert not point.exemplars
    assert len(packet.resource_metrics) == 1
    resource = packet.resource_metrics[0].resource
    assert {a.key: a.value.string_value for a in resource.attributes} == {
        "service.name": "module6-live"
    }
    raw = packet.SerializeToString()
    for prohibited in (
        PRIVATE,
        str(terminal.trace_id),
        terminal.span_id,
        "ollama",
        "qwen2.5",
        "input_tokens",
        "output_tokens",
        "cost",
    ):
        assert prohibited.encode() not in raw
    assert observer.live_terminal_records[0].model_dump_json() == before
    assert observer.records == () and observer.metrics.started == 0


def unknown():
    return record(
        roles=(),
        outcome="failed",
        category="connection_failed",
        facts=LiveRuntimeFacts(
            model_calls=None, repair_attempts=None, cleanup="unknown"
        ),
    )


def test_unknown_is_absent_and_mixed_accounting_has_coverage_denominator(metrics):
    assert add(metrics, unknown()).status == "recorded"
    data = signals(decoded(metrics))
    assert set(data) == {
        SYNTHETIC + ".workflow.finished",
        SYNTHETIC + ".workflow.duration",
    }
    known = record(roles=(), outcome="failed", category="connection_failed")
    assert add(metrics, known).status == "recorded"
    data = signals(decoded(metrics))
    assert value(data[SYNTHETIC + ".workflow.finished"]) == 2
    assert value(data[SYNTHETIC + ".accounting.observed"]) == 1
    assert value(data[SYNTHETIC + ".model.calls"]) == 3
    assert value(data[SYNTHETIC + ".workflow.repair_attempts"]) == 0


@pytest.mark.parametrize(
    "outcome,category,count",
    [
        ("denied", "authorization_refused", 0),
        ("timed_out", "timed_out", 1),
        ("cancelled", None, 1),
    ],
)
def test_zero_and_nonzero_terminal_accounting(metrics, outcome, category, count):
    terminal = record(
        outcome=outcome,
        category=category,
        roles=(),
        facts=LiveRuntimeFacts(
            model_calls=count,
            repair_attempts=0,
            cleanup="not_started" if count == 0 else "reaped",
        ),
    )
    assert add(metrics, terminal).status == "recorded"
    data = signals(decoded(metrics))
    assert value(data[SYNTHETIC + ".model.calls"]) == count
    assert value(data[SYNTHETIC + ".accounting.observed"]) == 1


def test_repair_attempts_are_not_transport_retries(metrics):
    full = record()
    terminal = record(
        roles=tuple(
            r.model_copy(update={"model_calls": r.sequence + 1, "repair_attempts": 1})
            for r in full.roles
        ),
        facts=LiveRuntimeFacts(model_calls=4, repair_attempts=1, cleanup="reaped"),
    )
    assert add(metrics, terminal).status == "recorded"
    data = signals(decoded(metrics))
    assert value(data[SYNTHETIC + ".model.calls"]) == 4
    assert value(data[SYNTHETIC + ".workflow.repair_attempts"]) == 1
    assert not any(name.endswith("retries") for name in data)


def test_sources_never_merge_and_cardinality_is_closed(metrics):
    # Both source classes x all five outcomes. Run identities are deliberately unique.
    for source in ("synthetic_offline", "local_provider_execution"):
        for outcome, category in (
            ("completed", None),
            ("failed", "malformed_output"),
            ("cancelled", None),
            ("timed_out", "timed_out"),
            ("denied", "authorization_refused"),
        ):
            terminal = (
                record(evidence_source=source)
                if outcome == "completed"
                else record(
                    evidence_source=source,
                    outcome=outcome,
                    category=category,
                    roles=(),
                    facts=LiveRuntimeFacts(
                        model_calls=0, repair_attempts=0, cleanup="not_started"
                    ),
                )
            )
            assert add(metrics, terminal).status == "recorded"
    data = signals(decoded(metrics))
    assert len(data) == 10
    assert (
        sum(
            len(m.histogram.data_points)
            if m.HasField("histogram")
            else len(m.sum.data_points)
            for m in data.values()
        )
        == 50
    )
    assert len(metrics._batch()) < 65536


@pytest.mark.parametrize("kind", ["extra", "nested", "role", "dict"])
def test_forged_observations_never_reach_the_sdk(metrics, kind, caplog):
    terminal = record()
    if kind == "extra":
        terminal.__dict__[PRIVATE] = PRIVATE
    elif kind == "nested":
        terminal.facts.__dict__["model_calls"] = PRIVATE
    elif kind == "role":
        terminal.roles[0].__dict__["role"] = PRIVATE
    else:
        terminal = terminal.model_dump()
    with pytest.raises(LiveValidationError) as caught:
        module.project_metric_observation(terminal)
    assert PRIVATE not in str(caught.value) + caplog.text
    assert metrics._provider is None


def test_active_unretained_and_unowned_inputs_refuse_without_state(metrics):
    terminal = record()
    observer = Observability()
    begin(observer, terminal)
    assert metrics.record(observer, terminal.trace_id).failure == "invalid_observation"
    assert metrics.record({}, terminal.trace_id).failure == "invalid_observation"
    assert (
        metrics.record(observer, str(terminal.trace_id)).failure
        == "invalid_observation"
    )
    assert metrics._provider is None and metrics._attempted == set()


def test_replay_and_lifetime_bound_do_not_evict_deduplication(metrics):
    first = record()
    assert add(metrics, first).status == "recorded"
    for _ in range(31):
        assert add(metrics, record()).status == "recorded"
    assert add(metrics, first).failure == "already_attempted"
    assert add(metrics, record()).failure == "capacity_spent"
    assert len(metrics._attempted) == 32
    data = signals(decoded(metrics))
    assert value(data[SYNTHETIC + ".workflow.finished"]) == 32
    assert value(data[SYNTHETIC + ".model.calls"]) == 96
    assert metrics.close() and metrics.close()
    assert add(metrics, record()).failure == "closed"


def test_concurrent_replay_and_nonblocking_admission(metrics):
    terminal = record()
    observer = retain(terminal)
    before = set(threading.enumerate())
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(lambda _: metrics.record(observer, terminal.trace_id), range(40))
        )
    assert sum(r.status == "recorded" for r in results) == 1
    assert all(r.failure in (None, "busy", "already_attempted") for r in results)
    assert set(threading.enumerate()) == before
    assert value(signals(decoded(metrics))[SYNTHETIC + ".workflow.finished"]) == 1


@pytest.mark.parametrize("owner", ["metrics", "observer"])
def test_busy_locks_never_queue_or_start_work(metrics, owner):
    terminal = record()
    observer = retain(terminal)
    lock = metrics._lock if owner == "metrics" else observer._lock
    ready, release = threading.Event(), threading.Event()

    def hold():
        with lock:
            ready.set()
            release.wait(5)

    worker = threading.Thread(target=hold)
    worker.start()
    try:
        assert ready.wait(2)
        assert metrics.record(observer, terminal.trace_id).failure == "busy"
        if owner == "metrics":
            assert metrics.close() is False
    finally:
        release.set()
        worker.join(2)
    assert metrics._provider is None


def test_sdk_disabled_and_unavailable_are_safe(monkeypatch):
    metrics = module.LiveOperationalMetrics()
    assert add(metrics, record()).failure == "sdk_disabled"
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")

    def unavailable():
        raise ImportError(PRIVATE)

    monkeypatch.setattr(metrics, "_initialize", unavailable)
    result = add(metrics, record())
    assert result.failure == "sdk_unavailable"
    assert PRIVATE not in repr(result)
    assert metrics._provider is None
    metrics.close()


def test_collection_failure_is_partial_sanitized_and_spent(
    metrics, monkeypatch, caplog
):
    first = record()
    assert add(metrics, first).status == "recorded"
    finished, duration, *rest = metrics._instruments[first.evidence_source]

    class FailingDuration:
        def record(self, *args):
            raise asyncio.CancelledError(PRIVATE)

    metrics._instruments[first.evidence_source] = (finished, FailingDuration(), *rest)
    terminal = record()
    result = add(metrics, terminal)
    assert result.failure == "collection_failed"
    assert add(metrics, terminal).failure == "already_attempted"
    assert add(metrics, record()).failure == "collection_failed"
    assert metrics._damaged
    data = signals(decoded(metrics))
    assert value(data[SYNTHETIC + ".workflow.finished"]) == 2  # explicit partial
    assert data[SYNTHETIC + ".workflow.duration"].histogram.data_points[0].count == 1
    assert PRIVATE not in repr(result) + caplog.text


def test_repeated_projection_values_are_deterministic(metrics):
    terminal = record(trace_id=uuid4())
    assert add(metrics, terminal).status == "recorded"
    other = module.LiveOperationalMetrics()
    try:
        assert add(other, terminal).status == "recorded"

        def normalized(packet):
            for metric in signals(packet).values():
                points = (
                    metric.histogram.data_points
                    if metric.HasField("histogram")
                    else metric.sum.data_points
                )
                for point in points:
                    point.start_time_unix_nano = point.time_unix_nano = 0
            return packet.SerializeToString(deterministic=True)

        assert normalized(decoded(metrics)) == normalized(decoded(other))
    finally:
        other.close()


@pytest.mark.parametrize("scenario", ["happy", "second_bad"])
async def test_actual_synthetic_execution_has_no_extra_calls_or_evidence_changes(
    monkeypatch, tmp_path, scenario, reaped
):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")
    factory, log = gateway(tmp_path, scenario)
    observer = Observability()
    receipt = failure = None
    try:
        receipt = await run(factory, observer=observer, text=PRIVATE)
    except CanonicalWorkflowError as error:
        failure = error.failure.model_dump_json()
    (terminal,) = observer.live_terminal_records
    before = terminal.model_dump_json()
    execution = receipt.model_dump_json() if receipt else failure
    assert len(calls(log)) == 3 and all(p.returncode is not None for p in reaped)
    metrics = module.LiveOperationalMetrics()
    try:
        assert metrics.record(observer, terminal.trace_id).status == "recorded"
        assert (
            metrics.record(observer, terminal.trace_id).failure == "already_attempted"
        )
        assert observer.live_terminal_records[0].model_dump_json() == before
        assert len(calls(log)) == 3
        assert (receipt.model_dump_json() if receipt else failure) == execution
    finally:
        metrics.close()
