"""Slice 1 contracts, owned retention and actual synthetic runtime integration."""

import asyncio
from uuid import UUID, uuid4

import pytest
from multi_agent_orchestration import canonical_workflow as service
from multi_agent_orchestration import live_execution as runtime
from multi_agent_orchestration.canonical_contracts import EvidenceSource
from multi_agent_orchestration.canonical_workflow import CanonicalWorkflowError
from multi_agent_orchestration.live_contracts import LIVE_ROLES, ModelUsage
from multi_agent_orchestration.live_errors import LiveValidationError
from multi_agent_orchestration.live_observation import (
    LiveObservationIdentity,
    LiveRoleCompletion,
    LiveRuntimeFacts,
    LiveTerminalObservation,
    checked_observation,
)
from multi_agent_orchestration.observability import Observability
from pydantic import ValidationError

from .test_canonical_workflow import authority, calls, gateway, run
from .test_canonical_workflow import reaped as reaped

CANARY = "SYNTHETIC_SLICE1_PRIVATE_93"


def identity():
    return LiveObservationIdentity(
        workflow_id=UUID(int=1),
        task_id=UUID(int=2),
        trace_id=uuid4(),
        span_id="0000000000000001",
        evidence_source="synthetic_offline",
        started_ns=1,
    )


def record(**changes):
    data = dict(
        **identity().model_dump(),
        outcome="completed",
        selection=authority().selection,
        roles=tuple(
            LiveRoleCompletion(
                role=role,
                sequence=i + 1,
                span_id=f"{i + 2:016x}",
                completed_ns=i + 2,
                model_calls=i + 1,
                repair_attempts=0,
            )
            for i, role in enumerate(LIVE_ROLES)
        ),
        facts=LiveRuntimeFacts(model_calls=3, repair_attempts=0, cleanup="reaped"),
        ended_ns=5,
        duration_ms=1.0,
    )
    data.update(changes)
    return checked_observation(LiveTerminalObservation, data)


def begin(observer, terminal):
    return observer.begin_live(
        LiveObservationIdentity(
            **{
                field: getattr(terminal, field)
                for field in LiveObservationIdentity.model_fields
            }
        )
    )


def test_frozen_closed_nested_and_unknown():
    terminal = record()
    for target, field, value in (
        (terminal, "outcome", "failed"),
        (terminal.facts, "model_calls", 4),
        (terminal.roles[0], "sequence", 2),
    ):
        with pytest.raises(ValidationError):
            setattr(target, field, value)
    assert terminal.facts.usage == ModelUsage()
    assert '"input_tokens":null' in terminal.model_dump_json()
    assert '"output_tokens":null' in terminal.model_dump_json()


@pytest.mark.parametrize(
    "field,value",
    [
        ("model_calls", 5),
        ("model_calls", True),
        ("model_calls", -1),
        ("repair_attempts", 2),
        ("repair_attempts", True),
        ("transport_retries", 1),
        ("cleanup", "assumed"),
        ("model_calls", None),
    ],
)
def test_impossible_facts_rejected(field, value):
    data = record().facts.model_dump()
    data[field] = value
    with pytest.raises(LiveValidationError):
        checked_observation(LiveRuntimeFacts, data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("trace_id", UUID(int=0)),
        ("span_id", "0000000000000000"),
        ("outcome", "approved"),
        ("category", "incomplete_prose"),
        ("runtime", "crewai"),
        ("topology", "parallel"),
        ("duration_ms", -1.0),
        ("ended_ns", 1),
        ("category", "malformed_output"),
    ],
)
def test_terminal_invariants(field, value):
    with pytest.raises(LiveValidationError):
        record(**{field: value})


@pytest.mark.parametrize("cleanup", ["not_started", "failed", "unknown"])
def test_success_requires_reaping(cleanup):
    with pytest.raises(LiveValidationError):
        record(facts=dict(model_calls=3, repair_attempts=0, cleanup=cleanup))


@pytest.mark.parametrize(
    "field",
    [
        "task",
        "prompt",
        "response",
        "credential",
        "environment",
        "endpoint",
        "metadata",
        "tags",
        "incomplete_prose",
        "exception",
        "pid",
        "command",
        "provider_options",
        "langsmith",
        "otel",
        "grafana",
    ],
)
def test_forbidden_fields_and_sanitized_errors(field, caplog):
    with pytest.raises(LiveValidationError) as caught:
        record(**{field: CANARY})
    assert CANARY not in str(caught.value) + repr(caught.value.__dict__) + caplog.text
    assert caught.value.__context__ is None


def test_partial_failure_and_unknown_cleanup():
    full = record()
    partial = record(
        outcome="failed",
        category="malformed_output",
        roles=full.roles[:1],
        facts=dict(model_calls=3, repair_attempts=1, cleanup="reaped"),
    )
    assert len(partial.roles) == 1 and partial.facts.usage == ModelUsage()
    unknown = record(
        outcome="cancelled",
        roles=(),
        facts=dict(model_calls=None, repair_attempts=None, cleanup="unknown"),
    )
    assert unknown.facts.model_calls is None and unknown.facts.cleanup == "unknown"


@pytest.mark.parametrize("change", ["reorder", "duplicate", "name", "span", "counter"])
def test_role_forgery_rejected(change):
    data = record().model_dump()
    roles = list(data["roles"])
    if change == "reorder":
        roles.reverse()
    elif change == "duplicate":
        roles[1] = roles[0]
    elif change == "name":
        roles[0]["role"] = CANARY
    elif change == "span":
        roles[0]["span_id"] = data["span_id"]
    else:
        roles[1]["model_calls"] = 4
    data["roles"] = tuple(roles)
    with pytest.raises(LiveValidationError):
        checked_observation(LiveTerminalObservation, data)


@pytest.mark.parametrize(
    "field",
    ["trace_id", "workflow_id", "task_id", "span_id", "evidence_source", "started_ns"],
)
def test_owned_handle_rejects_substitution(field):
    observer = Observability()
    terminal = record()
    handle = begin(observer, terminal)
    changes = {
        "trace_id": uuid4(),
        "workflow_id": uuid4(),
        "task_id": uuid4(),
        "span_id": "0000000000000009",
        "evidence_source": "local_provider_execution",
        "started_ns": 2,
    }
    changed = record(**{**terminal.model_dump(), field: changes[field]})
    with pytest.raises(LiveValidationError):
        observer.finish_live(handle, changed)
    assert not observer.live_terminal_records
    observer.finish_live(handle, terminal)
    assert observer.live_terminal_records == (terminal,)


def test_handles_forgery_cross_run_replay_and_stale():
    observer, other = Observability(), Observability()
    first, second = record(), record()
    a, b = begin(observer, first), begin(observer, second)
    for bad in (None, object(), uuid4(), begin(other, first)):
        with pytest.raises(LiveValidationError):
            observer.finish_live(bad, first)
    with pytest.raises(LiveValidationError):
        observer.finish_live(a, second)
    observer.finish_live(a, first)
    with pytest.raises(LiveValidationError):
        observer.finish_live(a, first)
    observer.abandon_live(b)
    with pytest.raises(LiveValidationError):
        observer.finish_live(b, second)
    assert begin(observer, first) is None


def test_storage_capacity_snapshot_mutation_and_drops():
    observer = Observability()
    terminals = [record() for _ in range(17)]
    handles = [begin(observer, terminal) for terminal in terminals]
    assert handles[-1] is None
    for handle in handles[:-1]:
        observer.abandon_live(handle)
    for _ in range(40):
        terminal = record()
        observer.finish_live(begin(observer, terminal), terminal)
    assert len(observer.live_terminal_records) == 32
    snapshot = observer.live_terminal_records[0]
    snapshot.facts.__dict__["model_calls"] = 99
    assert observer.live_terminal_records[0].facts.model_calls == 3
    assert observer.metrics.observation_drops >= 9
    assert observer.records == ()


def test_forged_nested_objects_rejected_without_logging(caplog):
    terminal = record()
    terminal.facts.__dict__[CANARY] = CANARY
    with pytest.raises(LiveValidationError) as caught:
        checked_observation(LiveTerminalObservation, terminal)
    assert CANARY not in str(caught.value) + caplog.text


@pytest.mark.parametrize(
    "scenario,expected,repairs,usage",
    [
        ("happy", 3, 0, (6, 9)),
        ("researcher_repair", 4, 1, (8, 12)),
        ("analyst_repair", 4, 1, (8, 12)),
        ("critic_repair", 4, 1, (8, 12)),
        ("usage_absent", 3, 0, (None, None)),
        ("mixed_usage", 3, 0, (6, None)),
        ("malform_incomplete", 4, 1, (8, 12)),
        ("malform_incomplete_analyst", 4, 1, (8, 12)),
        ("malform_incomplete_critic", 4, 1, (8, 12)),
    ],
)
async def test_real_synthetic_success(
    tmp_path, scenario, expected, repairs, usage, caplog
):
    factory, log = gateway(tmp_path, scenario)
    observer = Observability()
    receipt = await run(factory, observer=observer, text=CANARY)
    (terminal,) = observer.live_terminal_records
    evidence = receipt.result.evidence
    assert terminal.trace_id == evidence.trace_id and terminal.trace_id.int != 0
    assert terminal.workflow_id == evidence.workflow_id
    assert terminal.task_id == evidence.task_id
    assert terminal.selection == evidence.selection
    assert terminal.evidence_source == EvidenceSource.SYNTHETIC_OFFLINE
    assert terminal.outcome == "completed" and terminal.facts.cleanup == "reaped"
    assert tuple(r.role for r in terminal.roles) == LIVE_ROLES
    assert terminal.facts.model_calls == expected == len(calls(log))
    assert terminal.facts.repair_attempts == repairs
    assert terminal.facts.transport_retries == 0
    assert (
        terminal.facts.usage.input_tokens,
        terminal.facts.usage.output_tokens,
    ) == usage
    assert terminal.facts.usage == evidence.accounting.usage
    assert terminal.duration_ms >= 0 and terminal.ended_ns >= terminal.started_ns
    safe = terminal.model_dump_json() + repr(observer.live_records) + caplog.text
    for prohibited in (CANARY, "incomplete_prose", "payload", "pid", "11434"):
        assert prohibited not in safe
    assert len(observer.live_records) == 5 and observer.records == ()


@pytest.mark.parametrize(
    "scenario,roles,total,repairs,category",
    [
        ("failed_repair", 0, 2, 1, "malformed_output"),
        ("second_bad", 1, 3, 1, "malformed_output"),
        ("critic_failed_repair", 2, 4, 1, "malformed_output"),
        ("incomplete_twice", 0, 2, 1, "malformed_output"),
        ("incomplete_after_repair", 1, 3, 1, "malformed_output"),
        ("critic_incomplete_after_repair", 2, 4, 1, "malformed_output"),
        ("length_stop", 0, 1, 0, "output_too_large"),
        ("connection", 0, 1, 0, "connection_failed"),
        ("oversize", 0, 1, 0, "output_too_large"),
    ],
)
async def test_real_synthetic_failure(
    tmp_path, scenario, roles, total, repairs, category
):
    factory, log = gateway(tmp_path, scenario)
    observer = Observability()
    with pytest.raises(CanonicalWorkflowError) as caught:
        await run(factory, observer=observer)
    (terminal,) = observer.live_terminal_records
    assert terminal.outcome == "failed" and terminal.category == category
    assert terminal.facts.cleanup == "reaped"
    assert len(terminal.roles) == roles
    assert terminal.facts.model_calls == total == len(calls(log))
    assert terminal.facts.repair_attempts == repairs
    assert caught.value.failure.model_calls == total
    assert total <= 4 and terminal.facts.transport_retries == 0
    assert "incomplete_prose" not in terminal.model_dump_json()
    if scenario == "connection":
        assert terminal.facts.usage == ModelUsage()


async def test_fresh_trace_not_caller_workflow_or_task(tmp_path):
    factory, _ = gateway(tmp_path)
    observer = Observability()
    first = await run(factory, observer=observer, text=str(UUID(int=1)))
    second = await run(
        factory, observer=observer, text=str(first.result.evidence.trace_id)
    )
    ids = [r.trace_id for r in observer.live_terminal_records]
    assert ids[0] != ids[1] and all(i.int not in (0, 1, 2) for i in ids)
    assert second.result.evidence.trace_id == ids[1]


@pytest.mark.parametrize("auth", [None, object(), {"trace_id": str(uuid4())}])
async def test_observation_never_authorizes(auth):
    observer = Observability()
    with pytest.raises(CanonicalWorkflowError):
        await service.execute_canonical_workflow(
            CANARY,
            authorization=auth,
            observer=observer,
        )
    (terminal,) = observer.live_terminal_records
    assert terminal.outcome == "denied" and terminal.selection is None
    assert terminal.facts.model_calls == 0 and terminal.facts.cleanup == "not_started"


async def test_invalid_input_denied_without_worker(tmp_path):
    factory, log = gateway(tmp_path)
    observer = Observability()
    with pytest.raises(LiveValidationError):
        await run(factory, observer=observer, text="")
    (terminal,) = observer.live_terminal_records
    assert terminal.outcome == "denied" and terminal.facts.cleanup == "not_started"
    assert not calls(log)


async def test_timeout_and_cancel_facts_after_cleanup(tmp_path):
    factory, log = gateway(tmp_path, "timeout")
    observer = Observability()
    with pytest.raises(CanonicalWorkflowError):
        await run(factory, auth=authority(call_timeout_ms=500), observer=observer)
    (terminal,) = observer.live_terminal_records
    assert terminal.outcome == "timed_out" and terminal.facts.model_calls == 1
    assert terminal.facts.cleanup == "reaped" and terminal.facts.usage == ModelUsage()
    log.unlink()
    task = asyncio.create_task(run(factory, observer=observer))
    async with asyncio.timeout(10):
        while not calls(log):
            await asyncio.sleep(0.01)
    task.cancel(CANARY)
    with pytest.raises(asyncio.CancelledError):
        await task
    terminal = observer.live_terminal_records[-1]
    assert terminal.outcome == "cancelled" and terminal.facts.model_calls == 1
    assert terminal.facts.cleanup == "reaped"


async def test_cleanup_failure_is_not_success(tmp_path, monkeypatch):
    original = runtime._Run.stop

    async def broken(self):
        await original(self)
        raise RuntimeError(CANARY)

    monkeypatch.setattr(runtime._Run, "stop", broken)
    factory, log = gateway(tmp_path)
    observer = Observability()
    with pytest.raises(CanonicalWorkflowError):
        await run(factory, observer=observer)
    (terminal,) = observer.live_terminal_records
    assert terminal.outcome == "failed" and terminal.facts.cleanup == "failed"
    assert terminal.facts.model_calls == 3 == len(calls(log))
    assert CANARY not in terminal.model_dump_json()


@pytest.mark.parametrize("stage", ["begin_live", "finish_live", "emit_live"])
async def test_local_observation_failure_cannot_retry_or_change_authority(
    tmp_path,
    monkeypatch,
    stage,
):
    observer = Observability()

    def broken(*args):
        raise RuntimeError(CANARY)

    monkeypatch.setattr(observer, stage, broken)
    factory, log = gateway(tmp_path, "analyst_repair")
    receipt = await run(factory, observer=observer)
    evidence = receipt.result.evidence
    assert evidence.accounting.model_calls == 4 == len(calls(log))
    assert evidence.accounting.repair_attempts == 1
    assert evidence.accounting.transport_retries == 0
    assert (
        evidence.selection == authority().selection
        and evidence.budget == authority().budget
    )
    with pytest.raises(CanonicalWorkflowError):
        await service.execute_canonical_workflow(CANARY, observer=observer)


async def test_terminal_serialization_failure_isolated(tmp_path, monkeypatch):
    original = service.checked_observation

    def broken(schema, value):
        if schema is LiveTerminalObservation:
            raise RuntimeError(CANARY)
        return original(schema, value)

    monkeypatch.setattr(service, "checked_observation", broken)
    factory, log = gateway(tmp_path)
    observer = Observability()
    receipt = await run(factory, observer=observer)
    assert receipt.result.evidence.accounting.model_calls == len(calls(log)) == 3
    assert observer.live_terminal_records == () and not observer._live_active
    assert observer.metrics.observation_drops == 1


@pytest.mark.parametrize("field", ["trace_id", "workflow_id", "task_id"])
async def test_runtime_cannot_substitute_canonical_correlation(
    tmp_path, monkeypatch, field
):
    from multi_agent_orchestration.live_contracts import LiveWorkflowResult
    from multi_agent_orchestration.live_validation import validate_live_data

    factory, _ = gateway(tmp_path)
    seed = await run(factory)
    evidence = seed.result.evidence.model_dump()
    evidence["trace_id"] = None
    evidence[field] = uuid4()
    # Workflow/task substitutions need consistent nested contributions to remain
    # a valid runtime contract; the canonical boundary must still reject them.
    if field in ("workflow_id", "task_id"):
        evidence["contributions"] = tuple(
            {**r, field: evidence[field]} for r in evidence["contributions"]
        )
    forged = validate_live_data(
        LiveWorkflowResult,
        {
            **seed.result.model_dump(),
            "evidence": evidence,
        },
    )

    async def substitute(*args, **kwargs):
        return forged

    monkeypatch.setattr(service, "execute_live_workflow", substitute)
    observer = Observability()
    with pytest.raises(LiveValidationError):
        await run(factory, observer=observer)
    (terminal,) = observer.live_terminal_records
    assert terminal.outcome == "failed"
    assert terminal.facts.cleanup == "unknown"
    assert terminal.trace_id != evidence[field]


async def test_missing_supervisor_facts_stays_unknown_on_failure(tmp_path, monkeypatch):
    original = service.checked_observation

    def broken(schema, value):
        if schema is LiveRuntimeFacts:
            raise RuntimeError(CANARY)
        return original(schema, value)

    monkeypatch.setattr(service, "checked_observation", broken)
    factory, _ = gateway(tmp_path, "connection")
    observer = Observability()
    with pytest.raises(CanonicalWorkflowError):
        await run(factory, observer=observer)
    (terminal,) = observer.live_terminal_records
    assert terminal.facts.cleanup == "unknown"
    assert terminal.facts.model_calls == 1
    assert terminal.facts.usage == ModelUsage()


@pytest.mark.parametrize("scenario", ["failed_repair", "length_stop"])
async def test_broken_terminal_sink_never_changes_failed_execution(
    tmp_path,
    monkeypatch,
    scenario,
):
    observer = Observability()

    def broken(*args):
        raise RuntimeError(CANARY)

    monkeypatch.setattr(observer, "finish_live", broken)
    factory, log = gateway(tmp_path, scenario)
    with pytest.raises(CanonicalWorkflowError) as caught:
        await run(factory, observer=observer)
    expected = 2 if scenario == "failed_repair" else 1
    assert caught.value.failure.model_calls == len(calls(log)) == expected
    assert observer.live_terminal_records == () and not observer._live_active


@pytest.mark.parametrize(
    "field,value",
    [
        ("provider", "another"),
        ("model", "another:1"),
    ],
)
async def test_wrong_selection_never_authorized_by_observation(field, value):
    from multi_agent_orchestration.live_contracts import LiveAuthorization

    data = authority().model_dump()
    data["selection"][field] = value
    observer = Observability()
    with pytest.raises(CanonicalWorkflowError):
        await service.execute_canonical_workflow(
            CANARY,
            authorization=LiveAuthorization.model_validate(data),
            observer=observer,
        )
    (terminal,) = observer.live_terminal_records
    assert terminal.outcome == "denied" and terminal.selection is None
    assert terminal.facts.model_calls == 0


@pytest.mark.parametrize(
    "field",
    [
        "prompt",
        "credential",
        "environment",
        "endpoint",
        "metadata",
        "exception",
        "incomplete_prose",
    ],
)
def test_nested_payload_and_usage_injection_refused(field, caplog):
    data = record().model_dump()
    data["facts"][field] = CANARY
    with pytest.raises(LiveValidationError) as caught:
        checked_observation(LiveTerminalObservation, data)
    assert CANARY not in str(caught.value) + caplog.text


def test_zero_calls_cannot_claim_zero_provider_usage():
    with pytest.raises(LiveValidationError):
        checked_observation(
            LiveRuntimeFacts,
            {
                "model_calls": 0,
                "repair_attempts": 0,
                "cleanup": "not_started",
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        )


async def test_child_environment_and_content_canaries_absent(
    tmp_path, monkeypatch, caplog
):
    # Synthetic values only. Never inspect real credential-variable presence.
    monkeypatch.setenv("SLICE1_PRIVATE_ENV", CANARY)
    monkeypatch.setenv("LANGSMITH_API_KEY", CANARY)
    factory, _ = gateway(tmp_path, "hostile_content")
    observer = Observability()
    receipt = await run(factory, observer=observer, text=CANARY)
    terminal = observer.live_terminal_records[0]
    serialized = terminal.model_dump_json() + repr(observer.live_records) + caplog.text
    for value in (
        CANARY,
        receipt.result.research.findings[0],
        receipt.result.analysis.assessment,
        receipt.result.critique.rationale,
        "http://127.0.0.1:11434",
        "incomplete_prose",
    ):
        assert value not in serialized
    assert all(e.trace_id == terminal.trace_id for e in observer.live_records)


def test_completed_total_cannot_invent_repair_after_last_role():
    with pytest.raises(LiveValidationError):
        record(facts=dict(model_calls=4, repair_attempts=1, cleanup="reaped"))


def test_refinalization_rejected_when_terminal_capacity_full():
    """A consumed handle stays invalid after bounded terminal eviction."""
    observer = Observability()
    consumed_handle = None
    consumed_terminal = None
    for index in range(32):
        terminal = record()
        handle = begin(observer, terminal)
        assert handle is not None
        observer.finish_live(handle, terminal)
        if index == 31:
            consumed_handle = handle
            consumed_terminal = terminal
    assert len(observer.live_terminal_records) == 32
    with pytest.raises(LiveValidationError):
        observer.finish_live(consumed_handle, consumed_terminal)
    assert len(observer.live_terminal_records) == 32


def test_role_completion_rejects_wrong_valid_role_name():
    """Sequence identity cannot be weakened to any otherwise valid role."""
    data = record().roles[0].model_dump()
    data["role"] = LIVE_ROLES[1]
    with pytest.raises(LiveValidationError):
        checked_observation(LiveRoleCompletion, data)


def test_runtime_facts_reject_five_calls_with_one_repair():
    """The canonical workflow cannot claim a fifth call after one repair."""
    data = record().facts.model_dump()
    data["model_calls"] = 5
    data["repair_attempts"] = 1
    with pytest.raises(LiveValidationError):
        checked_observation(LiveRuntimeFacts, data)
