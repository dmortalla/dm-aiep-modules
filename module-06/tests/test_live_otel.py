"""Offline Slice 3: actual private OTel SDK, no external/exporter activity."""

import asyncio
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from uuid import UUID, uuid4

import pytest
from multi_agent_orchestration import live_otel as projection
from multi_agent_orchestration.canonical_workflow import CanonicalWorkflowError
from multi_agent_orchestration.live_langsmith import (
    project_live_observation as langsmith_projection,
)
from multi_agent_orchestration.live_observation import LiveRuntimeFacts
from multi_agent_orchestration.observability import Observability
from multi_agent_orchestration.observability_adapters import LocalOpenTelemetry
from opentelemetry.context import get_current
from opentelemetry.trace import StatusCode, get_tracer_provider

from .test_canonical_workflow import calls, gateway, run
from .test_canonical_workflow import reaped as reaped
from .test_live_observation import begin, record

PRIVATE = "PRIVATE_prompt_reply_error_secret_ENV_endpoint_path_metadata"


@pytest.fixture
def otel(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")

    # Stronger than the module guard: no DNS or sockets, even loopback here.
    def forbidden(*args, **kwargs):
        pytest.fail("Projection must perform no network activity")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    adapter = LocalOpenTelemetry()
    yield adapter
    adapter.close()


def retained(terminal=None):
    terminal = record() if terminal is None else terminal
    observer = Observability()
    observer.finish_live(begin(observer, terminal), terminal)
    return observer, terminal


def project(otel, observer, terminal):
    return projection.project_live_observation(
        observer, terminal.trace_id, adapter=otel
    )


@pytest.mark.parametrize("start", [1, 1_792_000_000_000_000_000, (1 << 64) - 5])
@pytest.mark.parametrize("prefix", [0, 1, 2, 3])
@pytest.mark.parametrize("trace", [UUID(int=1), UUID(int=(1 << 128) - 1)])
def test_installed_sdk_exact_identity_topology_and_nanoseconds(
    otel, start, prefix, trace
):
    assert version("opentelemetry-sdk") == "1.42.1"
    full = record()
    terminal = record(
        trace_id=trace,
        started_ns=start,
        ended_ns=start + 4,
        roles=tuple(
            r.model_copy(update={"completed_ns": start + 1})
            for r in full.roles[:prefix]
        ),
        outcome="completed" if prefix == 3 else "failed",
        category=None if prefix == 3 else "malformed_output",
    )
    observer, terminal = retained(terminal)
    before = terminal.model_dump_json()
    identity = otel._identity.set((42, 43))
    global_provider, context = get_tracer_provider(), get_current()
    try:
        result = project(otel, observer, terminal)
        assert otel._identity.get() == (42, 43)
    finally:
        otel._identity.reset(identity)
    assert result.status == "recorded" and result.planned_spans == prefix + 1
    assert result.evidence_class == "local_sdk_collection"
    spans = tuple(otel._spans)
    root, *children = spans
    assert [s.name for s in spans] == [
        "module6.workflow",
        *projection.ROLE_NAMES[:prefix],
    ]
    assert root.context.trace_id == trace.int
    assert root.context.span_id == int(terminal.span_id, 16)
    assert root.parent is None
    assert (root.start_time, root.end_time) == (start, start + 4)
    assert root.status.status_code == (
        StatusCode.OK if prefix == 3 else StatusCode.ERROR
    )
    for child, role in zip(children, terminal.roles, strict=True):
        assert child.context.trace_id == trace.int
        assert child.context.span_id == int(role.span_id, 16)
        assert child.parent.trace_id == trace.int
        assert child.parent.span_id == root.context.span_id
        assert child.start_time == child.end_time == role.completed_ns
        assert child.attributes["sequence"] == role.sequence
    assert get_tracer_provider() is global_provider and get_current() is context
    assert observer.live_terminal_records[0].model_dump_json() == before
    # Projection never converts the live observation to deterministic accounting.
    assert observer.records == () and observer.metrics.started == 0
    assert otel.collect_metrics() is None


def test_minimized_closed_attributes_and_cross_slice_correlation(otel, monkeypatch):
    for name in (
        "OTEL_RESOURCE_ATTRIBUTES",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_HEADERS",
        "LANGSMITH_API_KEY",
    ):
        monkeypatch.setenv(name, PRIVATE)
    observer, terminal = retained()
    smith = langsmith_projection(terminal)
    assert project(otel, observer, terminal).trace_id == smith.trace_id
    root, *children = otel._spans
    assert set(root.attributes) == {
        "observation",
        "evidence_source",
        "runtime",
        "topology",
        "outcome",
        "cleanup",
        "duration_ms",
        "model_calls",
        "repair_attempts",
    }
    assert root.attributes["evidence_source"] == "synthetic_offline"
    for span in otel._spans:
        assert dict(span.resource.attributes) == {"service.name": "module6-offline"}
        assert not span.events and not span.links
        assert span.status.description is None
        assert span.dropped_attributes == 0
    for child in children:
        assert set(child.attributes) == {
            "observation",
            "role",
            "sequence",
            "model_calls",
            "repair_attempts",
        }
    raw = repr([dict(s.attributes) for s in otel._spans])
    for forbidden in (PRIVATE, "ollama", "qwen2.5", "tokens", "cost", "reason"):
        assert forbidden not in raw
    assert terminal.facts.usage.input_tokens is None
    assert terminal.facts.usage.output_tokens is None


@pytest.mark.parametrize(
    "outcome,category,cleanup,calls_count",
    [
        ("failed", "connection_failed", "unknown", None),
        ("timed_out", "timed_out", "reaped", 1),
        ("cancelled", None, "reaped", 1),
        ("denied", "authorization_refused", "not_started", 0),
    ],
)
def test_terminal_failures_and_unknown_accounting(
    otel, outcome, category, cleanup, calls_count
):
    observer, terminal = retained(
        record(
            outcome=outcome,
            category=category,
            roles=(),
            facts=LiveRuntimeFacts(
                model_calls=calls_count,
                repair_attempts=None if calls_count is None else 0,
                cleanup=cleanup,
            ),
        )
    )
    assert project(otel, observer, terminal).status == "recorded"
    (root,) = otel._spans
    assert root.status.status_code == StatusCode.ERROR
    assert root.attributes.get("category") == category
    if calls_count is None:
        assert "model_calls" not in root.attributes
        assert "repair_attempts" not in root.attributes
    else:
        assert root.attributes["model_calls"] == calls_count


@pytest.mark.parametrize("mutation", ["extra", "nested", "timestamp", "span"])
def test_forged_retained_data_refuses_without_sdk_or_sensitive_logs(
    otel, monkeypatch, caplog, mutation
):
    terminal = record()
    if mutation == "extra":
        terminal.__dict__["secret"] = PRIVATE
    elif mutation == "nested":
        terminal.facts.__dict__["model_calls"] = PRIVATE
    elif mutation == "timestamp":
        terminal.__dict__["ended_ns"] = 1 << 64
    else:
        terminal.roles[0].__dict__["span_id"] = terminal.span_id
    # Simulate an untrusted/forged snapshot crossing the retention boundary.
    monkeypatch.setattr(
        Observability, "live_terminal_records", property(lambda self: (terminal,))
    )
    result = project(otel, Observability(), terminal)
    assert result.failure == "invalid_observation"
    assert not otel._spans and not otel._live_attempted
    assert PRIVATE not in repr(result) + caplog.text


def test_only_retained_owned_finalized_observations_are_selected(otel):
    observer, terminal = retained()
    other = record()
    begin(observer, other)
    assert project(otel, observer, other).failure == "invalid_observation"
    assert (
        projection.project_live_observation(
            observer, str(terminal.trace_id), adapter=otel
        ).failure
        == "invalid_observation"
    )
    assert (
        projection.project_live_observation({}, terminal.trace_id, adapter=otel).failure
        == "invalid_observation"
    )
    assert not otel._spans


def test_replay_lifetime_capacity_retention_and_close(otel):
    for _ in range(32):
        observer, terminal = retained()
        assert project(otel, observer, terminal).status == "recorded"
        assert project(otel, observer, terminal).failure == "already_attempted"
    assert len(otel._spans) == 128 and len(otel._live_attempted) == 32
    observer, terminal = retained()
    assert project(otel, observer, terminal).failure == "capacity_spent"
    otel.close()
    otel.close()
    assert project(otel, observer, terminal).failure == "closed"


@pytest.mark.parametrize("target", ["adapter", "observer"])
def test_contention_refuses_without_waiting_or_creating_work(otel, target):
    observer, terminal = retained()
    lock = otel._lock if target == "adapter" else observer._lock
    acquired, release = threading.Event(), threading.Event()

    def hold():
        with lock:
            acquired.set()
            release.wait(5)

    worker = threading.Thread(target=hold)
    worker.start()
    try:
        assert acquired.wait(2)
        assert project(otel, observer, terminal).failure == "busy"
        assert not otel._spans and not otel._live_attempted
    finally:
        release.set()
        worker.join(2)
    assert not worker.is_alive()


def test_concurrent_replay_has_one_attempt_and_no_background_workers(otel):
    observer, terminal = retained()
    before = set(threading.enumerate())
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: project(otel, observer, terminal), range(40)))
    assert sum(r.status == "recorded" for r in results) == 1
    assert all(r.failure in (None, "busy", "already_attempted") for r in results)
    assert len(otel._spans) == 4 and len(otel._live_attempted) == 1
    assert set(threading.enumerate()) == before


@pytest.mark.parametrize(
    "error", [RuntimeError(PRIVATE), asyncio.CancelledError(PRIVATE)]
)
def test_collection_fault_is_sanitized_and_never_replayed(
    otel, monkeypatch, caplog, error
):
    observer, terminal = retained()
    before = observer.live_terminal_records[0].model_dump_json()

    def failed(batch):
        raise error

    monkeypatch.setattr(otel, "_retain_spans", failed)
    result = project(otel, observer, terminal)
    assert result.status == "failed" and result.failure == "collection_failed"
    assert project(otel, observer, terminal).failure == "already_attempted"
    assert observer.live_terminal_records[0].model_dump_json() == before
    assert PRIVATE not in repr(result) + caplog.text
    assert otel._collection_failures == 4


def test_disabled_sdk_never_claims_collection():
    adapter = LocalOpenTelemetry()  # autouse fixture disables the SDK
    try:
        observer, terminal = retained()
        assert project(adapter, observer, terminal).failure == "sdk_disabled"
        assert not adapter._spans
    finally:
        adapter.close()


def test_saturated_diagnostic_counter_cannot_hide_collection_failure(otel, monkeypatch):
    observer, terminal = retained()
    otel._collection_failures = 1_000_000_000

    def fail(batch):
        raise RuntimeError(PRIVATE)

    monkeypatch.setattr(otel, "_retain_spans", fail)
    assert project(otel, observer, terminal).failure == "collection_failed"
    assert otel._collection_failures == 1_000_000_000


@pytest.mark.parametrize("scenario", ["happy", "second_bad"])
async def test_post_workflow_failure_preserves_evidence_and_model_calls(
    monkeypatch, tmp_path, scenario, reaped
):
    # Child IPC is permitted by the module guard; the gateway remains synthetic.
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
    assert len(calls(log)) == 3
    assert reaped and all(p.returncode is not None for p in reaped)
    adapter = LocalOpenTelemetry()
    try:

        def fail(batch):
            raise RuntimeError(PRIVATE)

        monkeypatch.setattr(adapter, "_retain_spans", fail)
        assert project(adapter, observer, terminal).status == "failed"
        assert len(calls(log)) == 3
        assert observer.live_terminal_records[0].model_dump_json() == before
        assert (receipt.model_dump_json() if receipt else failure) == execution
    finally:
        adapter.close()


def test_repeat_projection_across_private_adapters_is_deterministic(otel):
    observer, terminal = retained(record(trace_id=uuid4()))
    assert project(otel, observer, terminal).status == "recorded"
    second = LocalOpenTelemetry()
    try:
        assert project(second, observer, terminal).status == "recorded"

        def signature(adapter):
            return [
                (
                    s.name,
                    s.context,
                    s.parent,
                    s.start_time,
                    s.end_time,
                    dict(s.attributes),
                )
                for s in adapter._spans
            ]

        assert signature(otel) == signature(second)
    finally:
        second.close()
