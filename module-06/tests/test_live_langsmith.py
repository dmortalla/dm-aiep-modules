"""Slice 2 synthetic projection/intercepted transport evidence; no vendor calls."""

import asyncio
import json
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4, uuid5

import pytest
from multi_agent_orchestration import live_langsmith as adapter
from multi_agent_orchestration.canonical_workflow import CanonicalWorkflowError
from multi_agent_orchestration.langsmith_delivery import LangSmithDeliveryConfig
from multi_agent_orchestration.live_errors import LiveValidationError
from multi_agent_orchestration.live_observation import LiveTerminalObservation
from multi_agent_orchestration.observability import Observability

from .test_canonical_workflow import calls, gateway, run
from .test_canonical_workflow import reaped as reaped
from .test_live_observation import begin, record

CANARIES = (
    "PRIVATE_TASK_PROMPT_RESPONSE",
    "RAW_EXCEPTION_incomplete_prose",
    "SYNTHETIC_CREDENTIAL",
    "PRIVATE_ENVIRONMENT",
    "https://private.invalid",
    "C:\\private\\file",
    "ARBITRARY_METADATA_TAG",
)


class Fake:
    def __init__(self, status=202, error=None):
        self.batches = []
        self.status, self.error = status, error

    def write(self, batch):
        self.batches.append(batch)
        if self.error:
            raise self.error
        return self.status


def retained(terminal=None, observer=None):
    terminal = record() if terminal is None else terminal
    observer = Observability() if observer is None else observer
    observer.finish_live(begin(observer, terminal), terminal)
    return observer, terminal


def delivery(fake, limit=1):
    return adapter.LiveLangSmithDelivery(
        LangSmithDeliveryConfig(mode="langsmith-live", max_traces=limit),
        transport=fake,
    )


def runs(terminal):
    return json.loads(adapter.project_live_observation(terminal).batch)["post"]


def test_exact_topology_payload_free_and_trusted_correlation(monkeypatch):
    for key in ("LANGSMITH_API_KEY", "LANGSMITH_ENDPOINT", "LANGSMITH_METADATA"):
        monkeypatch.setenv(key, " ".join(CANARIES))
    first, second = record(), record()
    a, b = runs(first), runs(second)
    assert len(a) == 4
    assert [r["name"] for r in a] == [
        "module6.workflow",
        "Researcher",
        "Analyst",
        "Critic",
    ]
    assert a[0]["id"] == a[0]["trace_id"] == str(first.trace_id)
    assert a[0]["id"] != b[0]["id"]
    assert "parent_run_id" not in a[0]
    assert len({r["id"] for r in a}) == 4
    assert [r["extra"]["metadata"]["role_sequence"] for r in a[1:]] == [1, 2, 3]
    for child in a[1:]:
        assert child["parent_run_id"] == child["trace_id"] == a[0]["id"]
        assert child["dotted_order"].startswith(a[0]["dotted_order"] + ".")
        assert child["start_time"] == child["end_time"]
        assert child["tags"] == []
    for item in a:
        assert item["inputs"] == item["outputs"] == {}
        assert item["events"] == [] and item["run_type"] == "chain"
    raw = json.dumps(a)
    for canary in (*CANARIES, "ollama", "qwen2.5", "provider", "model_name"):
        assert canary not in raw
    assert len(adapter.project_live_observation(first).batch) <= adapter.MAX_BATCH_BYTES
    assert runs(first) == a  # Stable projection, no new correlation tree.


@pytest.mark.parametrize("base_ns", [0, 1_792_000_000_000_000_000])
@pytest.mark.parametrize("offsets", [(2, 3, 4), (2, 2, 2), (999, 1000, 1001)])
@pytest.mark.parametrize("prefix", [1, 2, 3])
def test_dotted_order_preserves_validated_prefix_at_precision_collisions(
    base_ns, offsets, prefix
):
    # Includes the reviewer's trace UUID and fresh namespaces: UUID suffixes
    # must never decide the sibling sequence, even when actual instants tie.
    for trace_id in (*[UUID(int=i) for i in range(1, 9)], *[uuid4() for _ in range(8)]):
        full = record()
        terminal = record(
            trace_id=trace_id,
            started_ns=base_ns + 1,
            ended_ns=base_ns + max(offsets) + 1,
            roles=tuple(
                role.model_copy(update={"completed_ns": base_ns + ns})
                for role, ns in zip(full.roles[:prefix], offsets, strict=False)
            ),
            outcome="completed" if prefix == 3 else "failed",
            category=None if prefix == 3 else "malformed_output",
        )
        observer, terminal = retained(terminal)
        before = observer.live_terminal_records[0].model_dump_json()
        projected = runs(terminal)
        ordered = sorted(projected, key=lambda run: run["dotted_order"])
        assert [run["name"] for run in ordered] == [
            "module6.workflow",
            *adapter.ROLE_NAMES[:prefix],
        ]
        assert ordered[0]["id"] == ordered[0]["trace_id"] == str(trace_id)
        assert len(ordered) == prefix + 1
        for child, ns in zip(ordered[1:], offsets[:prefix], strict=True):
            actual = (
                datetime(1970, 1, 1, tzinfo=UTC)
                + timedelta(microseconds=(base_ns + ns) // 1000)
            ).isoformat()
            assert child["start_time"] == child["end_time"] == actual
            assert child["inputs"] == child["outputs"] == {}
            assert child["parent_run_id"] == child["trace_id"] == str(trace_id)
            assert child["extra"]["metadata"]["dotted_order_semantics"] == (
                "observed_time_sequence_uuid"
            )
        if offsets in ((2, 3, 4), (2, 2, 2)):
            assert len({child["start_time"] for child in ordered[1:]}) == 1
        assert projected == runs(terminal)
        assert observer.live_terminal_records[0].model_dump_json() == before


@pytest.mark.parametrize("started_ns", [253402300799999999000, 1])
@pytest.mark.parametrize("prefix", [1, 2, 3])
def test_dotted_order_datetime_boundary_projects_and_delivers(started_ns, prefix):
    # Exact independent upper-bound reproduction plus the minimum admitted stamp.
    # All completion offsets are nanoseconds within one representable microsecond.
    expected_time = (
        "9999-12-31T23:59:59.999999+00:00"
        if started_ns == 253402300799999999000
        else "1970-01-01T00:00:00+00:00"
    )
    for trace_id in (UUID(int=1), UUID(int=2), uuid4(), uuid4()):
        full = record()
        terminal = record(
            trace_id=trace_id,
            started_ns=started_ns,
            ended_ns=started_ns + 4,
            roles=tuple(
                role.model_copy(update={"completed_ns": started_ns + role.sequence})
                for role in full.roles[:prefix]
            ),
            outcome="completed" if prefix == 3 else "failed",
            category=None if prefix == 3 else "malformed_output",
        )
        observer, terminal = retained(terminal)
        before = terminal.model_dump_json()
        projection = adapter.project_live_observation(terminal)
        ordered = sorted(
            json.loads(projection.batch)["post"], key=lambda run: run["dotted_order"]
        )
        assert [run["name"] for run in ordered] == [
            "module6.workflow",
            *("Researcher", "Analyst", "Critic")[:prefix],
        ]
        assert ordered[0]["id"] == ordered[0]["trace_id"] == str(trace_id)
        assert ordered[0]["extra"]["metadata"]["duration_ms"] == terminal.duration_ms
        root_component = ordered[0]["dotted_order"]
        assert datetime.strptime(root_component[:-36], "%Y%m%dT%H%M%S%fZ") == (
            datetime.fromisoformat(expected_time).replace(tzinfo=None)
        )
        assert UUID(root_component[-36:]) == trace_id
        for projected_run in ordered:
            assert (
                projected_run["start_time"]
                == projected_run["end_time"]
                == expected_time
            )
            assert projected_run["inputs"] == projected_run["outputs"] == {}
        for sequence, child in enumerate(ordered[1:], 1):
            component = child["dotted_order"].rsplit(".", 1)[1]
            parsed_time = datetime.strptime(component[:-36], "%Y%m%dT%H%M%S%fZ")
            assert parsed_time == datetime.fromisoformat(expected_time).replace(
                tzinfo=None
            )
            assert UUID(component[-36:]) == UUID(child["id"])
            assert UUID(child["id"]).bytes[0] == sequence
            assert child["parent_run_id"] == child["trace_id"] == str(trace_id)
        assert adapter.project_live_observation(terminal) == projection
        fake = Fake()
        sink = delivery(fake)
        result = sink.deliver(observer, trace_id)
        assert result.status == "accepted" and result.failure is None
        assert result.evidence_class == "synthetic_transport"
        assert result.planned_runs == prefix + 1 and result.write_attempts == 1
        assert fake.batches == [projection.batch]
        assert sink.deliver(observer, trace_id).failure == "already_attempted"
        assert len(fake.batches) == 1
        assert observer.live_terminal_records[0].model_dump_json() == before


@pytest.mark.parametrize("prefix", [0, 1, 2, 3])
@pytest.mark.parametrize(
    "started_ns",
    [
        1,
        int(datetime(2026, 10, 14, 17, 46, 40, tzinfo=UTC).timestamp()) * 1_000_000_000,
        int(datetime(2026, 10, 14, 17, 46, 40, tzinfo=UTC).timestamp()) * 1_000_000_000
        + 999,
        253402300799999999000,
    ],
)
def test_sdk_dotted_order_preserves_observed_trace_time_and_identity(
    started_ns, prefix
):
    from langsmith.run_trees import RunTree, _parse_dotted_order

    for trace_id in (UUID(int=1), UUID(int=2), UUID(int=32), uuid4()):
        full = record()
        terminal = record(
            trace_id=trace_id,
            started_ns=started_ns,
            ended_ns=started_ns + 4,
            roles=tuple(
                role.model_copy(update={"completed_ns": started_ns + role.sequence})
                for role in full.roles[:prefix]
            ),
            selection=full.selection if prefix else None,
            facts=full.facts
            if prefix
            else dict(model_calls=0, repair_attempts=0, cleanup="not_started"),
            outcome="completed" if prefix == 3 else "failed" if prefix else "denied",
            category=None
            if prefix == 3
            else ("malformed_output" if prefix else "authorization_refused"),
        )
        observer, terminal = retained(terminal)
        before = terminal.model_dump_json()
        projected = runs(terminal)
        root = projected[0]
        sdk_root = RunTree(**root, replicas=[], attachments={})
        expected_start = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
            microseconds=started_ns // 1000
        )
        assert sdk_root.start_time == sdk_root.trace_start_time == expected_start
        assert sdk_root.id == sdk_root.trace_id == trace_id
        assert sdk_root.parent_run_id is None and sdk_root.ls_client is None
        automatic_root = RunTree(
            id=trace_id,
            name=root["name"],
            start_time=expected_start,
            replicas=[],
            attachments={},
        )
        assert automatic_root.dotted_order == root["dotted_order"]
        ordered = sorted(projected, key=lambda item: item["dotted_order"])
        assert [item["name"] for item in ordered] == [
            "module6.workflow",
            *("Researcher", "Analyst", "Critic")[:prefix],
        ]
        for sequence, child in enumerate(ordered[1:], 1):
            role = terminal.roles[sequence - 1]
            expected_completion = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
                microseconds=role.completed_ns // 1000
            )
            parsed = _parse_dotted_order(child["dotted_order"])
            assert parsed == [
                (expected_start.replace(tzinfo=None), trace_id),
                (expected_completion.replace(tzinfo=None), UUID(child["id"])),
            ]
            seed = uuid5(trace_id, "role:" + role.span_id)
            assert UUID(child["id"]).bytes == bytes((sequence,)) + seed.bytes[1:]
            assert child["extra"]["metadata"]["span_id"] == role.span_id
            sdk_child = RunTree(
                **child, parent_run=sdk_root, replicas=[], attachments={}
            )
            automatic_child = RunTree(
                id=UUID(child["id"]),
                name=child["name"],
                start_time=expected_completion,
                end_time=expected_completion,
                parent_run=sdk_root,
                replicas=[],
                attachments={},
            )
            assert automatic_child.dotted_order == child["dotted_order"]
            assert sdk_child.trace_start_time == expected_start
            assert sdk_child.id == automatic_child.id == UUID(child["id"])
            assert sdk_child.trace_id == sdk_child.parent_run_id == trace_id
            assert sdk_child.start_time == sdk_child.end_time == expected_completion
            assert sdk_child.ls_client is None
        assert observer.live_terminal_records[0].model_dump_json() == before
        assert runs(terminal) == projected


@pytest.mark.parametrize(
    "field",
    [
        "task",
        "prompt",
        "response",
        "content",
        "exception",
        "credential",
        "environment",
        "endpoint",
        "path",
        "metadata",
        "tags",
        "incomplete_prose",
    ],
)
@pytest.mark.parametrize("level", ["root", "facts", "role"])
def test_injection_fails_closed_without_diagnostics(field, level, caplog):
    terminal = record()
    target = {"root": terminal, "facts": terminal.facts, "role": terminal.roles[0]}[
        level
    ]
    target.__dict__[field] = " ".join(CANARIES)
    with pytest.raises(LiveValidationError) as caught:
        adapter.project_live_observation(terminal)
    assert caught.value.__context__ is None
    for canary in CANARIES:
        assert canary not in str(caught.value) + repr(vars(caught.value)) + caplog.text


@pytest.mark.parametrize(
    "change",
    ["zero", "malformed", "substitution", "reorder", "four_roles", "wrong_role"],
)
def test_forged_or_malformed_contract_rejected(change):
    terminal = record()
    if change == "zero":
        terminal.__dict__["trace_id"] = UUID(int=0)
    elif change == "malformed":
        terminal.__dict__["trace_id"] = " ".join(CANARIES)
    elif change == "substitution":
        terminal.roles[0].__dict__["span_id"] = terminal.span_id
    elif change == "reorder":
        terminal.__dict__["roles"] = terminal.roles[::-1]
    elif change == "four_roles":
        terminal.__dict__["roles"] += terminal.roles[:1]
    else:
        terminal.roles[0].__dict__["role"] = "Critic"
    with pytest.raises(LiveValidationError):
        adapter.project_live_observation(terminal)


@pytest.mark.parametrize(
    "outcome,category,cleanup",
    [
        ("failed", "malformed_output", "reaped"),
        ("timed_out", "timed_out", "reaped"),
        ("cancelled", None, "unknown"),
        ("denied", "authorization_refused", "not_started"),
    ],
)
def test_truthful_failures_partial_roles_and_nullable_usage(outcome, category, cleanup):
    full = record()
    partial = outcome in ("failed", "timed_out")
    terminal = record(
        outcome=outcome,
        category=category,
        selection=full.selection if partial or outcome == "cancelled" else None,
        roles=full.roles[:1] if partial else (),
        facts=dict(
            model_calls=2 if partial else None if outcome == "cancelled" else 0,
            repair_attempts=0 if outcome != "cancelled" else None,
            cleanup=cleanup,
        ),
    )
    projected = runs(terminal)
    assert len(projected) == (2 if partial else 1)
    root = projected[0]
    assert root["error"] == outcome
    meta = root["extra"]["metadata"]
    assert meta["outcome"] == outcome and meta["category"] == category
    assert meta["input_tokens"] is meta["output_tokens"] is None
    assert meta["model_calls"] == terminal.facts.model_calls
    assert meta["cleanup"] == cleanup


def test_known_and_mixed_usage_and_repairs():
    terminal = record(
        facts=dict(
            model_calls=4,
            repair_attempts=1,
            cleanup="reaped",
            usage=dict(input_tokens=8, output_tokens=None),
        ),
        roles=tuple(
            r.model_copy(update={"model_calls": r.sequence + 1, "repair_attempts": 1})
            for r in record().roles
        ),
    )
    meta = runs(terminal)[0]["extra"]["metadata"]
    assert meta["model_calls"] == 4 and meta["repair_attempts"] == 1
    assert meta["input_tokens"] == 8 and meta["output_tokens"] is None


def test_only_finalized_owned_retention_can_be_delivered():
    observer, terminal, fake = Observability(), record(), Fake()
    sink = delivery(fake)
    handle = begin(observer, terminal)
    assert sink.deliver(observer, terminal.trace_id).failure == "invalid_observation"
    observer.finish_live(handle, terminal)
    for bad in (uuid4(), str(terminal.trace_id), UUID(int=0), terminal):
        assert sink.deliver(observer, bad).failure == "invalid_observation"
    assert sink.deliver(observer, terminal.trace_id).status == "accepted"
    assert len(fake.batches) == 1


def test_no_authorization_no_transport_even_with_credential(monkeypatch):
    monkeypatch.setenv("LANGSMITH_API_KEY", CANARIES[2])
    observer, terminal = retained()
    fake = Fake()
    configs = [
        None,
        {"mode": "langsmith-live"},
        LangSmithDeliveryConfig.model_construct(mode="bad", max_traces=1),
    ]
    for config in configs:
        result = adapter.LiveLangSmithDelivery(config, transport=fake).deliver(
            observer, terminal.trace_id
        )
        assert result.failure == "refused" and result.write_attempts == 0
    assert fake.batches == []


@pytest.mark.parametrize(
    "status,category",
    [
        (401, "authentication_rejected"),
        (403, "authorization_rejected"),
        (429, "rate_limited"),
        (500, "service_failed"),
        (400, "request_rejected"),
        (302, "unexpected_response"),
        (True, "unexpected_response"),
    ],
)
def test_closed_statuses_no_retries(status, category):
    observer, terminal = retained()
    fake = Fake(status)
    sink = delivery(fake)
    before = terminal.model_dump_json()
    result = sink.deliver(observer, terminal.trace_id)
    assert result.status == "failed" and result.failure == category
    assert result.evidence_class == "synthetic_transport"
    assert result.write_attempts == 1 and len(fake.batches) == 1
    assert observer.live_terminal_records[0].model_dump_json() == before
    assert sink.deliver(observer, terminal.trace_id).failure == "already_attempted"
    assert len(fake.batches) == 1


@pytest.mark.parametrize(
    "error,category",
    [
        (RuntimeError(" ".join(CANARIES)), "transport_failed"),
        (TimeoutError(" ".join(CANARIES)), "timed_out"),
        (asyncio.CancelledError(" ".join(CANARIES)), "transport_failed"),
    ],
)
def test_safe_exception_classification(error, category, caplog):
    observer, terminal = retained()
    fake = Fake(error=error)
    result = delivery(fake).deliver(observer, terminal.trace_id)
    assert result.failure == category
    assert len(fake.batches) == 1
    for canary in CANARIES:
        assert canary not in repr(result) + caplog.text


def test_lifetime_budget_and_concurrent_cross_run_isolation():
    observer = Observability()
    terminals = [retained(observer=observer)[1] for _ in range(4)]
    fake, sink = Fake(), None
    sink = delivery(fake, 3)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda t: sink.deliver(observer, t.trace_id),
                [terminals[0]] * 4 + terminals[1:],
            )
        )
    assert sum(r.status == "accepted" for r in results) == 3
    assert len(fake.batches) == len(sink._attempted) == 3
    assert {r.failure for r in results if r.status == "refused"} == {
        "already_attempted",
        "budget_spent",
    }
    roots = [json.loads(b)["post"][0]["id"] for b in fake.batches]
    assert len(set(roots)) == 3
    for batch in fake.batches:
        tree = json.loads(batch)["post"]
        assert all(r["trace_id"] == tree[0]["id"] for r in tree)
    for _ in range(33):
        retained(observer=observer)
    assert len(observer.live_terminal_records) == 32
    assert (
        delivery(Fake()).deliver(observer, terminals[0].trace_id).failure
        == "invalid_observation"
    )


def test_production_transport_intercepted_fixed_bounds(monkeypatch):
    import requests

    # Direct transport probe uses only a synthetic key and intercepted request.
    monkeypatch.setenv("LANGSMITH_API_KEY", CANARIES[2])
    seen = []

    class Reply:
        status_code = 202

        def close(self):
            seen.append("closed")

        @property
        def content(self):
            pytest.fail("Reply body must never be read")

    def intercepted(session, method, url, **kwargs):
        assert session.trust_env is False and session.max_redirects == 0
        assert all(a.max_retries.total == 0 for a in session.adapters.values())
        assert method == "POST" and url == adapter.WRITE_URL
        assert kwargs["timeout"] == (5.0, 10.0)
        assert kwargs["stream"] is True and kwargs["allow_redirects"] is False
        seen.append(kwargs["data"])
        return Reply()

    monkeypatch.setattr(requests.Session, "request", intercepted)
    batch = adapter.project_live_observation(record()).batch
    assert adapter._ProductionTransport().write(batch) == 202
    assert seen == [batch, "closed"]
    assert CANARIES[2].encode() not in batch


@pytest.mark.parametrize("scenario", ["happy", "second_bad"])
async def test_after_actual_synthetic_workflow_failure_cannot_change_execution(
    tmp_path, scenario, reaped
):
    factory, log = gateway(tmp_path, scenario)
    observer = Observability()
    receipt = failure = None
    try:
        receipt = await run(factory, observer=observer, text=CANARIES[0])
    except CanonicalWorkflowError as error:
        failure = error.failure.model_dump_json()
    (terminal,) = observer.live_terminal_records
    before = terminal.model_dump_json()
    execution = receipt.model_dump_json() if receipt else failure
    assert reaped and all(p.returncode is not None for p in reaped)
    original_calls = len(calls(log))
    result = delivery(Fake(error=RuntimeError(CANARIES[1]))).deliver(
        observer, terminal.trace_id
    )
    assert result.status == "failed"
    assert original_calls == len(calls(log)) == 3
    assert observer.live_terminal_records[0].model_dump_json() == before
    assert (receipt.model_dump_json() if receipt else failure) == execution
    root = runs(terminal)[0]
    assert root["id"] == str(terminal.trace_id)
    assert root["extra"]["metadata"]["evidence_source"] == "synthetic_offline"


def test_pure_projection_refuses_mappings_and_unbounded_timing():
    with pytest.raises(LiveValidationError):
        adapter.project_live_observation(record().model_dump())
    terminal = LiveTerminalObservation.model_construct(**record().__dict__)
    terminal.__dict__["ended_ns"] = 10**100
    with pytest.raises(LiveValidationError):
        adapter.project_live_observation(terminal)


def test_delivery_deadline_dns_stall_lock_isolation_and_late_result(monkeypatch):
    import requests

    monkeypatch.setenv("LANGSMITH_API_KEY", CANARIES[2])
    monkeypatch.setattr(adapter, "DELIVERY_DEADLINE_S", 0.25)
    entered, release = threading.Event(), threading.Event()
    workers = []

    def stalled_dns(*args, **kwargs):
        workers.append(threading.current_thread())
        entered.set()
        release.wait()
        raise OSError(CANARIES[1])

    # Requests really reaches urllib3's resolver, but no real DNS is performed.
    monkeypatch.setattr(socket, "getaddrinfo", stalled_dns)
    observer, first = retained()
    _, second = retained(observer=observer)
    before = tuple(t.model_dump_json() for t in observer.live_terminal_records)
    sink = adapter.LiveLangSmithDelivery(
        LangSmithDeliveryConfig(mode="langsmith-live", max_traces=3)
    )
    pool = ThreadPoolExecutor(max_workers=2)
    try:
        started = time.monotonic()
        future = pool.submit(sink.deliver, observer, first.trace_id)
        assert entered.wait(2)
        replay = pool.submit(sink.deliver, observer, first.trace_id).result(timeout=2)
        assert replay.failure == "already_attempted"
        result = future.result(timeout=2)
        assert time.monotonic() - started < 2
        assert result.failure == "timed_out" and result.status == "failed"
        assert result.evidence_class == "unverified_write"
        assert result.write_attempts == 1
        assert not release.is_set() and workers[0].is_alive()
        frozen = repr(result)

        class Reply:
            status_code = 202

            def close(self):
                pass

        def intercepted(*args, **kwargs):
            return Reply()

        # The first resolver is STILL stalled; an independent eligible trace on
        # the SAME sink makes progress without the first transport's lock.
        monkeypatch.setattr(requests.Session, "post", intercepted)
        assert sink.deliver(observer, second.trace_id).status == "accepted"
        assert sink.deliver(observer, first.trace_id) == replay
        assert (
            tuple(t.model_dump_json() for t in observer.live_terminal_records) == before
        )
        assert len(sink._attempted) == 2
        assert repr(result) == frozen
        assert all(c not in repr(result) for c in CANARIES)
    finally:
        release.set()
        pool.shutdown(wait=True)
        for worker in workers:
            worker.join(2)
            assert not worker.is_alive()
    assert repr(result) == frozen
    assert tuple(t.model_dump_json() for t in observer.live_terminal_records) == before
    assert sink.deliver(observer, first.trace_id) == replay


@pytest.mark.parametrize("late_status", [202, None])
def test_delivery_deadline_global_resource_cap_and_late_completion(
    monkeypatch, late_status
):
    monkeypatch.setattr(adapter, "DELIVERY_DEADLINE_S", 0.05)
    release = threading.Event()
    workers, results, snapshots = [], [], []

    class Stalled:
        def write(self, batch):
            workers.append(threading.current_thread())
            release.wait()
            if late_status is None:
                raise RuntimeError(CANARIES[1])
            return late_status

    try:
        for _ in range(3):
            observer, terminal = retained()
            before = terminal.model_dump_json()
            sink = delivery(Stalled())
            started = time.monotonic()
            result = sink.deliver(observer, terminal.trace_id)
            assert time.monotonic() - started < 1
            assert result.failure == "timed_out"
            results.append((result, repr(result), sink, observer, terminal.trace_id))
            snapshots.append(before)
        assert len(workers) == 3 and all(w.is_alive() for w in workers)
        # New instances and fresh traces cannot evade process-wide admission.
        for _ in range(20):
            observer, terminal = retained()
            result = delivery(Stalled()).deliver(observer, terminal.trace_id)
            assert result.failure == "transport_failed"
        assert len(workers) == 3
    finally:
        release.set()
        for worker in workers:
            worker.join(2)
            assert not worker.is_alive()
    for (result, frozen, sink, observer, trace_id), before in zip(
        results, snapshots, strict=True
    ):
        assert repr(result) == frozen and result.failure == "timed_out"
        assert observer.live_terminal_records[0].model_dump_json() == before
        assert sink.deliver(observer, trace_id).failure == "already_attempted"
        assert sink._attempted == {trace_id}
    # Capacity is reusable after actual worker exit, without a retained queue.
    observer, terminal = retained()
    assert delivery(Fake()).deliver(observer, terminal.trace_id).status == "accepted"
