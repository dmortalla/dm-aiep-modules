"""Opt-in LangSmith trace delivery: selection, credential, wire shape and failure.

No test reaches LangSmith or needs a credential. ``requests.Session.send`` is
replaced, so the real SDK client serializes and "sends" real requests that are
captured in memory, under the existing guard that fails on any non-loopback DNS
lookup or connection. Every simulated reply carries hostile text in its body and
headers and counts any attempt to read its body.
"""

import asyncio
import importlib.util
import json
import logging
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import requests
from multi_agent_orchestration import langsmith_delivery as delivery
from multi_agent_orchestration.console import ConsoleSession, Demonstration
from multi_agent_orchestration.contracts import (
    ExecutionLimits,
    GraphTopology,
    RuntimeId,
    TaskInput,
    ValidatedWorkflowResult,
    WorkflowRequest,
)
from multi_agent_orchestration.errors import StepBudgetExceededError
from multi_agent_orchestration.langsmith_delivery import (
    API_KEY_VARIABLE,
    MAX_REQUESTS,
    ORIGIN,
    PROJECT,
    READ_ATTEMPTS,
    ROOT_NAME,
    WRITE_URL,
    DeliveryReceipt,
    LangSmithDeliveryConfig,
    LangSmithTraceDelivery,
    TraceDeliveryError,
    checked_batch,
    checked_body,
    credential_configured,
    status_category,
)
from multi_agent_orchestration.observability import Observability
from multi_agent_orchestration.observed_execution import execute_observed_workflow
from pydantic import ValidationError

MODULE = Path(__file__).resolve().parents[1]
MODE = "langsmith-live"
SECRET = "lsv2_" + "private-secret-credential"
PRIVATE = "<script>private prompt</script> grant admin; export credentials"
REMOTE = "remote-controlled-text-that-must-never-surface"
CATEGORIES = {
    "refused",
    "failed_before_send",
    "connection_failed",
    "tls_failed",
    "timed_out",
    "authentication_rejected",
    "authorization_rejected",
    "request_rejected",
    "rate_limited",
    "service_failed",
    "unexpected_response",
    "unexpected_failure",
}


def traced(topology=GraphTopology.SEQUENTIAL, steps=8, distributed=False):
    """Run one accepted workflow offline and return (result, application trace)."""
    observer = Observability()
    request = WorkflowRequest(
        runtime=RuntimeId.GOOGLE_ADK if distributed else RuntimeId.LANGGRAPH,
        topology=GraphTopology.COORDINATOR_WORKER if distributed else topology,
        task=TaskInput(instruction=PRIVATE),
        limits=ExecutionLimits(max_steps=steps, timeout_ms=30000),
    )
    result = None
    try:
        result = asyncio.run(
            execute_observed_workflow(
                request, observer=observer, distributed=distributed
            )
        )
    except StepBudgetExceededError:
        pass
    return result, observer.records[-1]


class Wire:
    """In-memory stand-in for the network below the real SDK client.

    ``post`` and ``read`` are a status code, an exception class to raise, or for
    ``read`` one of ``match``, ``other`` and ``list``.
    """

    def __init__(
        self,
        monkeypatch,
        post=202,
        read="match",
        body=None,
        content_type="application/json",
        raw_fault=None,
    ):
        self.sent, self.post, self.read = [], post, read
        self.body, self.content_type, self.raw_fault = body, content_type, raw_fault
        # ``body_reads`` counts unbounded reads of a failed reply; ``raw_reads``
        # records every bounded read as (method, status, asked, returned).
        self.body_reads, self.raw_reads = [], []
        monkeypatch.setattr(requests.Session, "send", self.send)

    def reply(self, prepared, status, payload, readable=False):
        wire = self
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()

        class Raw:
            def read(self, amt=None, decode_content=False):
                if wire.raw_fault is not None:
                    raise wire.raw_fault(f"{SECRET} {REMOTE}")
                chunk = data if amt is None else data[:amt]
                wire.raw_reads.append((prepared.method, status, amt, len(chunk)))
                return chunk

            def close(self):
                pass

        class Reply(requests.Response):
            @property
            def content(self):
                if not readable:
                    wire.body_reads.append(prepared.url)
                return data

        response = Reply()
        response.raw = Raw()
        response.request, response.url = prepared, prepared.url
        response.status_code = status
        # Everything remote is hostile: none of it may reach a public diagnostic.
        response.headers["x-remote-header"] = REMOTE
        response.headers["x-api-key"] = SECRET
        response.headers["retry-after"] = "100000"
        if self.content_type is not None:
            response.headers["content-type"] = self.content_type
        return response

    def send(self, prepared, **options):
        self.sent.append((prepared, options))
        hostile = {"detail": REMOTE, "error": SECRET, "trace": "Traceback " + REMOTE}
        plan = self.post if prepared.method == "POST" else self.read
        if isinstance(plan, list):
            reads = sum(item.method == "GET" for item, _ in self.sent)
            plan = plan[min(reads, len(plan)) - 1]
        if isinstance(plan, type):
            raise plan(f"{SECRET} {REMOTE} {prepared.url}")
        if isinstance(plan, int):
            payload = hostile if self.body is None else self.body
            return self.reply(prepared, plan, payload)
        if plan == "list":
            return self.reply(prepared, 200, ["unexpected"], readable=True)
        root = self.runs()[0]
        stored = {key: root[key] for key in ("id", "trace_id", "name", "run_type")}
        stored["note"] = SECRET
        if plan == "other":
            stored["id"] = str(uuid4())
        return self.reply(prepared, 200, stored, readable=True)

    def writes(self):
        return [item for item, _ in self.sent if item.method == "POST"]

    def runs(self):
        return json.loads(self.writes()[-1].body)["post"]


def adapter(**changes):
    return LangSmithTraceDelivery(LangSmithDeliveryConfig(mode=MODE, **changes))


def public_surface(error):
    """Everything a caller could read from a failure, including its traceback."""
    return " ".join(
        [
            str(error),
            repr(error),
            repr(error.args),
            repr(vars(error)),
            repr(error.__cause__),
            repr(error.__context__),
            "".join(traceback.format_exception(error)),
        ]
    )


def assert_nothing_remote_or_secret(text, *, origin_allowed=False):
    """The fixed destination may appear in receipts and command output only."""
    for hidden in (
        SECRET,
        SECRET[:5],
        REMOTE,
        "Traceback remote",
        "x-api-key",
        "x-remote-header",
        "retry-after",
        "dummy",
        PRIVATE,
    ):
        assert hidden not in text
    assert origin_allowed or "smith.langchain.com" not in text


@pytest.fixture
def key(monkeypatch, caplog):
    monkeypatch.setenv(API_KEY_VARIABLE, SECRET)
    monkeypatch.setattr(delivery, "READ_INTERVAL_S", 0)
    caplog.set_level(logging.DEBUG)


def test_delivery_requires_an_explicit_mode_with_no_default():
    with pytest.raises(ValidationError):
        LangSmithDeliveryConfig()
    config = LangSmithDeliveryConfig(mode=MODE)
    assert config.max_traces == 1
    assert set(LangSmithDeliveryConfig.model_fields) == {"mode", "max_traces"}


@pytest.mark.parametrize(
    "changes",
    [
        {"mode": "enabled"},
        {"mode": True},
        {"max_traces": 0},
        {"max_traces": 4},
        {"max_traces": True},
        {"api_key": SECRET},
        {"endpoint": "https://example.com"},
        {"api_url": "https://example.com"},
        {"write_path": "/runs"},
        {"project": "other"},
        {"region": "eu"},
        {"inputs": {"prompt": PRIVATE}},
    ],
)
def test_invalid_configuration_is_rejected_without_echo(changes):
    with pytest.raises(ValidationError) as error:
        LangSmithDeliveryConfig(**{"mode": MODE, **changes})
    assert SECRET not in str(error.value) and "example.com" not in str(error.value)


@pytest.mark.parametrize("kind", ["mapping", "text", "constructed", "subclass"])
def test_forged_configuration_objects_cannot_select_delivery(monkeypatch, kind):
    wire = Wire(monkeypatch)

    class Wider(LangSmithDeliveryConfig):
        pass

    forged = {
        "mapping": {"mode": MODE},
        "text": MODE,
        "constructed": LangSmithDeliveryConfig.model_construct(
            mode="anything", max_traces=1000
        ),
        "subclass": Wider(mode=MODE),
    }[kind]
    with pytest.raises(TraceDeliveryError):
        LangSmithTraceDelivery(forged)
    assert wire.sent == []


def test_application_and_default_paths_load_no_delivery_or_provider():
    code = (
        "import sys, multi_agent_orchestration.console, "
        "multi_agent_orchestration.benchmark, "
        "multi_agent_orchestration.observed_execution\n"
        "from multi_agent_orchestration.console import ConsoleSession\n"
        "run = ConsoleSession().run({'mode': 'Deterministic fixture', "
        "'instruction': 'offline'})\n"
        "assert run.trace is not None\n"
        "assert 'multi_agent_orchestration.langsmith_delivery' not in sys.modules\n"
        "import multi_agent_orchestration.langsmith_delivery\n"
        "for name in ('openai', 'anthropic', 'google.genai'):\n"
        "    assert name not in sys.modules, name\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        env={
            **os.environ,
            "PYTHONPATH": str(MODULE / "src"),
            API_KEY_VARIABLE: SECRET,
            "LANGSMITH_TRACING": "true",
        },
        capture_output=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr[-600:]


def test_credential_presence_alone_delivers_nothing(monkeypatch, key):
    import langsmith

    def forbidden(*args, **kwargs):
        pytest.fail("A LangSmith client was constructed without explicit delivery")

    wire = Wire(monkeypatch)
    monkeypatch.setattr(langsmith.Client, "__init__", forbidden)
    for name in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"):
        monkeypatch.setenv(name, "true")
    result, trace = traced()
    assert result is not None and trace.outcome.value == "completed"
    view = ConsoleSession().run(
        {"mode": Demonstration.SEQUENTIAL, "instruction": PRIVATE}
    )
    assert view.trace is not None
    adapter()  # Even a constructed adapter sends nothing until deliver is called.
    assert wire.sent == [] and credential_configured()


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_credential_fails_closed_before_any_request(monkeypatch, value):
    wire = Wire(monkeypatch)
    monkeypatch.delenv(API_KEY_VARIABLE, raising=False)
    if value is not None:
        monkeypatch.setenv(API_KEY_VARIABLE, value)
    # The legacy variable name is deliberately not a credential source.
    monkeypatch.setenv("LANGCHAIN_API_KEY", SECRET)
    _, trace = traced()
    sender = adapter()
    with pytest.raises(TraceDeliveryError) as error:
        sender.deliver(trace)
    assert error.value.category == "refused"
    assert API_KEY_VARIABLE in str(error.value) and SECRET not in str(error.value)
    assert wire.sent == [] and not credential_configured()
    monkeypatch.setenv(API_KEY_VARIABLE, SECRET)
    monkeypatch.setattr(delivery, "READ_INTERVAL_S", 0)
    # A refused attempt for a missing credential did not spend the budget.
    assert sender.deliver(trace).confirmation == "service_read"


def test_delivery_uses_the_sdk_batch_method_and_no_other_write_api(monkeypatch, key):
    import langsmith
    from langsmith.run_trees import RunTree

    Wire(monkeypatch)
    calls, original = [], langsmith.Client.batch_ingest_runs

    def spy(self, create=None, update=None):
        calls.append((len(create or ()), update))
        return original(self, create=create, update=update)

    def forbidden(*args, **kwargs):
        pytest.fail("A write API other than batch_ingest_runs was used")

    monkeypatch.setattr(langsmith.Client, "batch_ingest_runs", spy)
    for name in ("create_run", "update_run", "multipart_ingest", "flush"):
        monkeypatch.setattr(langsmith.Client, name, forbidden)
    monkeypatch.setattr(RunTree, "post", forbidden)
    monkeypatch.setattr(RunTree, "patch", forbidden)
    _, trace = traced()
    assert adapter().deliver(trace).runs_accepted == 4
    assert calls == [(4, None)]


def test_delivery_posts_one_batch_holding_only_the_closed_trace(monkeypatch, key):
    wire = Wire(monkeypatch)
    result, trace = traced()
    receipt = adapter().deliver(trace)
    runs = wire.runs()
    root = runs[0]
    assert [(item.method, item.url) for item, _ in wire.sent] == [
        ("POST", f"{ORIGIN}/runs/batch"),
        ("GET", f"{ORIGIN}/runs/{root['id']}"),
    ]
    assert WRITE_URL == f"{ORIGIN}/runs/batch"
    write = wire.writes()[0]
    assert set(json.loads(write.body)) == {"post"}
    assert checked_batch(write.body) == runs and len(write.body) < 4096
    assert [run["name"] for run in runs] == [
        ROOT_NAME,
        "graph_researcher",
        "graph_analyst",
        "graph_critic",
    ]
    for prepared, options in wire.sent:
        assert prepared.headers["x-api-key"] == SECRET
        assert SECRET not in prepared.url and SECRET not in str(prepared.body)
        assert options["allow_redirects"] is False and options["stream"] is True
        assert options["timeout"] == (5.0, 10.0)
        assert not options["proxies"]
    for run in runs:
        assert checked_body(json.dumps(run)) == run
        assert run["inputs"] == run["outputs"] == {} and run["events"] == []
        assert set(run["extra"]) == {"metadata"}
        assert run["session_name"] == PROJECT and run["run_type"] == "chain"
        assert run["extra"]["metadata"]["inference"] == "none"
        assert run["extra"]["metadata"]["model_calls"] == 0
        assert run["trace_id"] == root["id"]
        assert "attachments" not in run
    assert root["tags"] == ["module6", "deterministic", "no-llm-inference"]
    assert root["extra"]["metadata"]["workflow_id"] == str(trace.workflow_id)
    everything = str(write.body) + write.url
    for absent in (
        PRIVATE,
        "private prompt",
        result.result.output,
        str(trace.task_id),
        str(trace.trace_id),
        trace.span_id,
        "runtime_environment",
        "platform",
        "sdk_version",
        "dangerously_allow_filesystem",
        os.getcwd(),
    ):
        assert absent not in everything
    assert receipt == DeliveryReceipt(
        trace_id=UUID(root["id"]),
        runs_accepted=4,
        write_status=202,
        confirmation="service_read",
        read_attempts=1,
        requests=2,
    )
    assert receipt.write_path == "/runs/batch" and receipt.destination == ORIGIN
    assert wire.body_reads == []  # The write reply body was never read.
    assert SECRET not in receipt.model_dump_json()


def test_batch_sends_no_more_than_the_previously_approved_run_fields():
    _, trace = traced()
    approved = {
        "dotted_order",
        "end_time",
        "events",
        "extra",
        "id",
        "inputs",
        "name",
        "outputs",
        "run_type",
        "session_name",
        "start_time",
        "tags",
        "trace_id",
    }
    root, *children = adapter().preview(trace)
    assert set(root) == approved
    assert all(set(child) == approved | {"parent_run_id"} for child in children)
    assert set(root["extra"]["metadata"]) == {
        "module",
        "verification",
        "inference",
        "evidence_class",
        "runtime",
        "topology",
        "distributed",
        "outcome",
        "workflow_id",
        "model_calls",
    }


def test_delivery_cannot_change_the_workflow_result(monkeypatch, key):
    Wire(monkeypatch, post=requests.ConnectionError)
    result, trace = traced()
    before, record = result.model_dump(), trace.model_dump()
    with pytest.raises(TraceDeliveryError):
        adapter().deliver(trace)
    assert result.model_dump() == before and trace.model_dump() == record
    assert ValidatedWorkflowResult.model_validate(before) == result


@pytest.mark.parametrize(
    "status,category",
    [
        (400, "request_rejected"),
        (401, "authentication_rejected"),
        (403, "authorization_rejected"),
        (404, "request_rejected"),
        (405, "request_rejected"),
        (409, "request_rejected"),
        (413, "request_rejected"),
        (422, "request_rejected"),
        (429, "rate_limited"),
        (500, "service_failed"),
        (502, "service_failed"),
        (503, "service_failed"),
        (302, "unexpected_response"),
        (307, "unexpected_response"),
    ],
)
def test_rejected_batch_is_classified_from_its_status_and_never_retried(
    monkeypatch, key, caplog, status, category
):
    wire = Wire(monkeypatch, post=status)
    _, trace = traced()
    sender = adapter()
    started = time.monotonic()
    with pytest.raises(TraceDeliveryError) as raised:
        sender.deliver(trace)
    error = raised.value
    assert error.category == category and category in CATEGORIES
    assert error.http_status == status and f"(HTTP {status})" in str(error)
    # One batch carries every run: a rejected write accepted none of them.
    assert (error.accepted_runs, error.planned_runs) == (0, 4)
    assert "0 of 4 runs were accepted" in str(error)
    assert "Partial" not in str(error)
    # Exactly one external write. The SDK would retry 429 and 5xx, and would
    # wait for the hostile retry-after value; it never learns of the failure.
    assert len(wire.sent) == 1 and wire.sent[0][0].method == "POST"
    assert time.monotonic() - started < 5
    # No unbounded read ever. A 4xx reply gets exactly one read of at most 2048
    # bytes for classification; every other status is not read at all.
    assert wire.body_reads == []
    expected_reads = [("POST", status, 2048, 133)] if 400 <= status <= 499 else []
    assert [(m, s, a, min(n, 133)) for m, s, a, n in wire.raw_reads] == [
        (m, s, a, min(n, 133)) for m, s, a, n in expected_reads
    ]
    assert (error.reply_hint is not None) == (400 <= status <= 499)
    assert error.__cause__ is None and error.__context__ is None
    assert_nothing_remote_or_secret(public_surface(error))
    assert_nothing_remote_or_secret(caplog.text, origin_allowed=True)
    with pytest.raises(TraceDeliveryError) as spent:
        sender.deliver(trace)
    assert spent.value.category == "refused" and len(wire.sent) == 1


@pytest.mark.parametrize(
    "fault,category",
    [
        (requests.ConnectionError, "connection_failed"),
        (requests.exceptions.ProxyError, "connection_failed"),
        (requests.exceptions.SSLError, "tls_failed"),
        (requests.ConnectTimeout, "timed_out"),
        (requests.ReadTimeout, "timed_out"),
        (RuntimeError, "unexpected_failure"),
        (OSError, "unexpected_failure"),
    ],
)
def test_batch_without_a_response_is_classified_by_exception_type(
    monkeypatch, key, caplog, fault, category
):
    wire = Wire(monkeypatch, post=fault)
    _, trace = traced()
    started = time.monotonic()
    with pytest.raises(TraceDeliveryError) as raised:
        adapter().deliver(trace)
    error = raised.value
    assert error.category == category and error.http_status is None
    assert "HTTP" not in str(error)
    assert (error.accepted_runs, error.planned_runs) == (0, 4)
    # The SDK retries connection failures by itself; only one write was made.
    assert len(wire.sent) == 1 and time.monotonic() - started < 5
    assert error.__cause__ is None and error.__context__ is None
    assert_nothing_remote_or_secret(public_surface(error))
    assert_nothing_remote_or_secret(caplog.text, origin_allowed=True)


def pinned_client(session):
    import langsmith
    from langsmith import schemas
    from urllib3.util import Retry

    return langsmith.Client(
        api_url=ORIGIN,
        api_key=SECRET,
        auto_batch_tracing=False,
        session=session,
        retry_config=Retry(total=0),
        omit_traced_runtime_info=True,
        info=schemas.LangSmithInfo(),
        tracing_mode="langsmith",
        disable_prompt_cache=True,
    )


def test_sdk_initiated_second_write_is_refused_at_the_transport(monkeypatch, key):
    wire = Wire(monkeypatch)
    _, trace = traced()
    session = delivery._session(False, time.monotonic())
    client = pinned_client(session)
    client.batch_ingest_runs(create=delivery._runs(trace))
    assert len(wire.sent) == 1 and session.refusal is None
    # Whatever the SDK does next, a second write never leaves the process.
    with delivery._silenced_sdk():
        client.batch_ingest_runs(create=delivery._runs(trace))
    assert len(wire.sent) == 1
    assert session.refusal == "Delivery refused: a second write was attempted."
    body = wire.writes()[0].body
    with pytest.raises(TraceDeliveryError):
        session.request("POST", WRITE_URL, data=body)
    assert len(wire.sent) == 1


def test_sdk_failure_logging_is_suppressed_only_for_the_sdk_and_the_call(caplog):
    caplog.set_level(logging.DEBUG)
    sdk_logger = logging.getLogger("langsmith.client")
    application = logging.getLogger("multi_agent_orchestration.example")
    before = list(sdk_logger.filters)
    with delivery._silenced_sdk():
        sdk_logger.warning("Failed to batch ingest runs: %s", REMOTE)
        sdk_logger.error(REMOTE)
        application.warning("application record kept")
    assert REMOTE not in caplog.text and "application record kept" in caplog.text
    assert sdk_logger.filters == before
    sdk_logger.warning("sdk record after the call")
    assert "sdk record after the call" in caplog.text
    with pytest.raises(RuntimeError):
        with delivery._silenced_sdk():
            raise RuntimeError("inside")
    assert sdk_logger.filters == before


def test_unprotected_sdk_call_leaks_and_retries_but_the_adapter_does_not(
    monkeypatch, key, caplog
):
    """Shows the hazard is real in the installed SDK, then that it is contained."""
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    _, trace = traced()
    loose = Wire(monkeypatch, post=500)
    pinned_client(requests.Session()).batch_ingest_runs(create=delivery._runs(trace))
    assert len(loose.sent) == 3  # The SDK retried by itself.
    assert REMOTE in caplog.text  # And logged the hostile reply text.
    caplog.clear()
    wire = Wire(monkeypatch, post=500)
    with pytest.raises(TraceDeliveryError) as raised:
        adapter().deliver(trace)
    assert raised.value.category == "service_failed" and len(wire.sent) == 1
    assert_nothing_remote_or_secret(public_surface(raised.value))
    assert_nothing_remote_or_secret(caplog.text, origin_allowed=True)


@pytest.mark.parametrize(
    "read,category",
    [
        (404, "not_found"),
        (401, "authentication_rejected"),
        (403, "authorization_rejected"),
        (429, "rate_limited"),
        (500, "service_failed"),
        ("list", "unexpected_response"),
        (requests.ConnectionError, "connection_failed"),
        (requests.ReadTimeout, "timed_out"),
    ],
)
def test_accepted_delivery_with_unconfirmed_read_back_is_a_bounded_receipt(
    monkeypatch, key, caplog, read, category
):
    wire = Wire(monkeypatch, read=read)
    _, trace = traced()
    receipt = adapter().deliver(trace)
    assert receipt.confirmation == "accepted_only" and receipt.runs_accepted == 4
    assert receipt.write_status == 202 and receipt.read_failure == category
    assert receipt.read_attempts == READ_ATTEMPTS
    assert len(wire.writes()) == 1 and len(wire.sent) == MAX_REQUESTS == 7
    # Every attempt is reported, including reads that never got a response.
    assert receipt.requests == len(wire.sent) == 7
    assert wire.body_reads == []  # No failed reply body was read.
    assert_nothing_remote_or_secret(
        receipt.model_dump_json() + caplog.text, origin_allowed=True
    )


def test_contradictory_read_back_is_a_failure_after_an_accepted_write(
    monkeypatch, key, caplog
):
    wire = Wire(monkeypatch, read="other")
    _, trace = traced()
    with pytest.raises(TraceDeliveryError) as raised:
        adapter().deliver(trace)
    assert "contradicts the delivery" in str(raised.value)
    assert len(wire.writes()) == 1
    assert_nothing_remote_or_secret(public_surface(raised.value))
    assert_nothing_remote_or_secret(caplog.text, origin_allowed=True)


@pytest.mark.parametrize("post", [400, 403, 500, requests.ConnectionError])
def test_read_back_happens_only_after_an_accepted_batch(monkeypatch, key, post):
    wire = Wire(monkeypatch, post=post)
    _, trace = traced()
    with pytest.raises(TraceDeliveryError):
        adapter().deliver(trace)
    assert [item.method for item, _ in wire.sent] == ["POST"]


def test_budget_allows_exactly_the_configured_number_of_traces(monkeypatch, key):
    wire = Wire(monkeypatch)
    _, trace = traced(GraphTopology.COORDINATOR_WORKER)
    sender = adapter(max_traces=2)
    first, second = sender.deliver(trace), sender.deliver(trace)
    assert first.trace_id != second.trace_id and first.runs_accepted == 2
    with pytest.raises(TraceDeliveryError):
        sender.deliver(trace)
    assert len(wire.sent) == 2 * 2 and len(wire.writes()) == 2


@pytest.mark.parametrize(
    "name,value",
    [
        ("LANGSMITH_ENDPOINT", "https://collector.example.com"),
        ("LANGCHAIN_ENDPOINT", "https://collector.example.com"),
        ("LANGSMITH_RUNS_ENDPOINTS", '{"https://collector.example.com": "k"}'),
        ("LANGSMITH_PROJECT", "someone-elses-project"),
        ("LANGCHAIN_PROJECT", "someone-elses-project"),
        ("HTTPS_PROXY", "http://proxy.example.com:8080"),
        ("LANGSMITH_TRACING_SAMPLING_RATE", "0"),
        ("LANGSMITH_HIDE_METADATA", "true"),
        ("LANGSMITH_AGENT_ID", "agent-from-environment"),
        ("LANGCHAIN_REVISION_ID", "private-revision"),
        ("LANGCHAIN_SESSION", "someone-elses-project"),
    ],
)
def test_environment_cannot_redirect_expand_or_suppress_delivery(
    monkeypatch, key, name, value
):
    wire = Wire(monkeypatch)
    monkeypatch.setenv(name, value)
    _, trace = traced(GraphTopology.COORDINATOR_WORKER)
    try:
        receipt = adapter().deliver(trace)
    except TraceDeliveryError as refused:
        # Refusing outright is acceptable; sending anywhere else is not.
        assert "example.com" not in str(refused)
        assert all(item.url.startswith(f"{ORIGIN}/runs") for item, _ in wire.sent)
        return
    assert receipt.confirmation == "service_read" and receipt.runs_accepted == 2
    assert wire.writes()[0].url == WRITE_URL
    assert all(item.url.startswith(f"{ORIGIN}/runs/") for item, _ in wire.sent)
    assert not any(options["proxies"] for _, options in wire.sent)
    text = json.dumps(wire.runs())
    assert "someone-elses-project" not in text and "private-revision" not in text
    assert "agent-from-environment" not in text
    assert all(run["session_name"] == PROJECT for run in wire.runs())
    assert checked_batch(wire.writes()[0].body)


def test_failure_before_any_request_is_distinguished(monkeypatch, key, caplog):
    wire = Wire(monkeypatch)
    # The SDK refuses to construct a client when both of these are set.
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://collector.example.com")
    monkeypatch.setenv("LANGSMITH_RUNS_ENDPOINTS", '{"https://x.example.com": "k"}')
    _, trace = traced()
    with pytest.raises(TraceDeliveryError) as raised:
        adapter().deliver(trace)
    error = raised.value
    assert error.category == "failed_before_send" and wire.sent == []
    assert error.http_status is None and error.planned_runs is None
    assert str(error) == "Delivery failed before any request was sent."
    assert error.__context__ is None
    assert "example.com" not in public_surface(error)
    assert "collector.example.com" not in caplog.text
    assert_nothing_remote_or_secret(public_surface(error))
    assert_nothing_remote_or_secret(caplog.text, origin_allowed=True)


def test_denied_run_is_delivered_without_invented_accounting(monkeypatch, key):
    wire = Wire(monkeypatch)
    result, trace = traced(GraphTopology.PARALLEL, steps=1)
    assert result is None and trace.outcome.value == "denied"
    receipt = adapter().deliver(trace)
    (run,) = wire.runs()
    assert receipt.runs_accepted == 1 and run["error"] == "denied"
    assert "model_calls" not in run["extra"]["metadata"]
    assert run["extra"]["metadata"]["outcome"] == "denied"


def test_distributed_trace_omits_process_and_assignment_identity(monkeypatch, key):
    wire = Wire(monkeypatch)
    _, trace = traced(distributed=True)
    assert len(trace.steps) == 2
    adapter().deliver(trace)
    text = json.dumps(wire.runs())
    for step in trace.steps:
        assert str(step.worker_pid) not in text
        assert str(step.assignment_id) not in text
    assert [run["name"] for run in wire.runs()] == [
        ROOT_NAME,
        "left_counter",
        "right_counter",
    ]
    assert wire.runs()[0]["extra"]["metadata"]["distributed"] is True


@pytest.mark.parametrize("kind", ["mapping", "text", "extra_field", "missing"])
def test_only_owned_application_traces_are_accepted(monkeypatch, key, kind):
    wire = Wire(monkeypatch)
    _, trace = traced(GraphTopology.COORDINATOR_WORKER)
    forged = {
        "mapping": trace.model_dump(),
        "text": PRIVATE,
        "extra_field": trace.model_copy(update={"prompt": PRIVATE}),
        "missing": None,
    }[kind]
    sender = adapter()
    with pytest.raises(TraceDeliveryError) as error:
        sender.deliver(forged)
    assert error.value.category == "refused"
    assert "private prompt" not in str(error.value) and wire.sent == []
    with pytest.raises(TraceDeliveryError):
        sender.preview(forged)


def valid_runs():
    _, trace = traced()
    return adapter().preview(trace)


@pytest.mark.parametrize(
    "target,change",
    [
        (0, {"inputs": {"prompt": PRIVATE}}),
        (0, {"outputs": {"answer": PRIVATE}}),
        (0, {"events": [{"name": "token", "kwargs": {"token": PRIVATE}}]}),
        (0, {"attachments": {}}),
        (0, {"attachments": {"file": "C:/Users/someone/secret.txt"}}),
        (0, {"dangerously_allow_filesystem": False}),
        (0, {"serialized": {"name": "x"}}),
        (0, {"session_name": "another-project"}),
        (0, {"name": PRIVATE}),
        (0, {"run_type": "llm"}),
        (0, {"tags": ["module6", PRIVATE]}),
        (0, {"error": "Traceback: " + PRIVATE}),
        (0, {"extra": {"metadata": {}, "runtime": {"platform": "x"}}}),
        (0, {"extra": {"metadata": {"prompt": PRIVATE}}}),
        (0, {"extra": {"metadata": {"module": "module-06", "inference": "gpt"}}}),
        (0, {"extra": {"metadata": {"model_calls": 3}}}),
        (0, {"extra": {"metadata": {"distributed": 1}}}),
        (0, {"extra": {"metadata": {"workflow_id": PRIVATE}}}),
        (0, {"trace_id": str(uuid4())}),
        (0, {"dotted_order": "not-an-order"}),
        (0, {"start_time": "yesterday"}),
        (0, {"id": "not-a-uuid"}),
        (1, {"parent_run_id": str(uuid4())}),
        (1, {"name": ROOT_NAME}),
        (1, {"tags": ["module6"]}),
        (1, {"extra": {"metadata": {"role_sequence": 9}}}),
    ],
)
def test_wire_guard_refuses_any_run_outside_the_closed_shape(target, change):
    runs = [dict(run) for run in valid_runs()]
    runs[target] = {**runs[target], **change}
    with pytest.raises((ValueError, KeyError, TypeError)):
        checked_body(json.dumps(runs[target]))
    with pytest.raises((ValueError, KeyError, TypeError)):
        checked_batch(json.dumps({"post": runs}))


@pytest.mark.parametrize(
    "kind",
    [
        "patch",
        "extra_key",
        "empty",
        "five_runs",
        "child_first",
        "two_roots",
        "duplicate_ids",
        "foreign_child",
        "list",
        "not_json",
        "missing",
        "oversized",
    ],
)
def test_wire_guard_refuses_any_batch_outside_one_root_and_its_children(kind):
    runs = [dict(run) for run in valid_runs()]
    other = [dict(run) for run in valid_runs()]
    data = {
        "patch": {"post": runs, "patch": [{"id": runs[1]["id"]}]},
        "extra_key": {"post": runs, "feedback": []},
        "empty": {"post": []},
        "five_runs": {"post": [*runs, {**runs[1], "id": str(uuid4())}]},
        "child_first": {"post": runs[::-1]},
        "two_roots": {"post": [runs[0], other[0]]},
        "duplicate_ids": {"post": [runs[0], runs[1], runs[1]]},
        "foreign_child": {"post": [runs[0], other[1]]},
        "list": runs,
        "not_json": "not json",
        "missing": None,
        "oversized": {"post": runs, "pad": "x" * 9000},
    }[kind]
    encoded = data if kind in ("not_json", "missing") else json.dumps(data)
    with pytest.raises((ValueError, KeyError, TypeError)):
        checked_batch(encoded)
    assert checked_batch(json.dumps({"post": runs})) == runs


def test_pinned_session_permits_one_batch_write_and_nothing_else(monkeypatch):
    wire = Wire(monkeypatch)
    body = json.dumps({"post": list(valid_runs())})
    session = delivery._session(False, time.monotonic())
    for method, url in (
        ("POST", f"{ORIGIN}/runs"),
        ("POST", f"{ORIGIN}/runs/"),
        ("POST", f"{ORIGIN}/runs/multipart"),
        ("POST", f"{ORIGIN}/runs/batch/"),
        ("POST", f"{ORIGIN}/runs/batch?x=1"),
        ("POST", f"{ORIGIN}/sessions"),
        ("PATCH", f"{ORIGIN}/runs/batch"),
        ("PUT", f"{ORIGIN}/runs/batch"),
        ("DELETE", f"{ORIGIN}/runs/batch"),
        ("GET", f"{ORIGIN}/runs/batch"),
        ("GET", f"{ORIGIN}/info"),
        ("GET", f"{ORIGIN}/sessions?limit=1"),
        ("GET", f"{ORIGIN}/runs/{uuid4()}"),
        ("GET", "https://example.com/"),
        ("POST", "https://example.com/runs/batch"),
        ("POST", "http://api.smith.langchain.com/runs/batch"),
        ("POST", f"{ORIGIN}.example.com/runs/batch"),
        ("POST", "https://eu.api.smith.langchain.com/runs/batch"),
        ("POST", "https://api.openai.com/v1/chat/completions"),
    ):
        with pytest.raises(TraceDeliveryError):
            session.request(method, url, data=body)
    with pytest.raises(TraceDeliveryError):
        session.request("POST", WRITE_URL, data=json.dumps({"post": [{"x": 1}]}))
    assert wire.sent == [] and session.trust_env is False and session.writes == 0
    assert session.request("POST", WRITE_URL, data=body).status_code == 202
    with pytest.raises(TraceDeliveryError) as second:
        session.request("POST", WRITE_URL, data=body)
    assert "second write" in str(second.value) and len(wire.sent) == 1
    expired = delivery._session(False, time.monotonic() - delivery.DEADLINE_S - 1)
    with pytest.raises(TraceDeliveryError) as bound:
        expired.request("POST", WRITE_URL, data=body)
    assert "bound" in str(bound.value) and len(wire.sent) == 1


def test_sdk_never_receives_a_failed_reply_from_the_transport(monkeypatch):
    wire = Wire(monkeypatch, post=500)
    body = json.dumps({"post": list(valid_runs())})
    session = delivery._session(False, time.monotonic())
    reply = session.request("POST", WRITE_URL, data=body)
    # The SDK is handed an empty accepted reply; the truth stays in the session.
    assert reply.status_code == 202 and reply.content == b"{}"
    assert not reply.headers and session.write_status == 500
    assert wire.body_reads == []
    Wire(monkeypatch, post=requests.exceptions.SSLError)
    session = delivery._session(False, time.monotonic())
    assert session.request("POST", WRITE_URL, data=body).status_code == 202
    assert session.write_status is None and session.write_category == "tls_failed"


def test_preview_uses_no_network_and_no_credential(monkeypatch):
    wire = Wire(monkeypatch)
    monkeypatch.delenv(API_KEY_VARIABLE, raising=False)
    _, trace = traced()
    sender = adapter()
    runs = sender.preview(trace)
    assert len(runs) == 4 and wire.sent == []
    assert checked_batch(json.dumps({"post": list(runs)}))
    assert "placeholder" not in json.dumps(runs)
    # Previewing does not spend the delivery budget.
    monkeypatch.setenv(API_KEY_VARIABLE, SECRET)
    monkeypatch.setattr(delivery, "READ_INTERVAL_S", 0)
    assert sender.deliver(trace).runs_accepted == 4


def test_local_refusals_are_classified_as_refused_and_send_nothing(monkeypatch, key):
    wire = Wire(monkeypatch)
    _, trace = traced()
    sender = adapter()
    with pytest.raises(TraceDeliveryError) as not_trace:
        sender.deliver({"prompt": PRIVATE})
    monkeypatch.delenv(API_KEY_VARIABLE)
    with pytest.raises(TraceDeliveryError) as no_key:
        sender.deliver(trace)
    for raised in (not_trace, no_key):
        assert raised.value.category == "refused"
        assert raised.value.http_status is raised.value.accepted_runs is None
    assert wire.sent == []


def test_status_vocabulary_is_closed_and_never_reads_a_body():
    seen = {status_category(code) for code in range(100, 600)}
    assert seen <= CATEGORIES and "refused" not in seen
    assert status_category(404, reading=True) == "not_found"
    assert status_category(404) == "request_rejected"
    assert set(delivery._FAILURE_TEXT) == CATEGORIES - {"refused"}
    for text in delivery._FAILURE_TEXT.values():
        assert "{" not in text and "%" not in text and "Partial" not in text


@pytest.mark.parametrize(
    "changes",
    [
        {"runs_accepted": 0},
        {"runs_accepted": 5},
        {"write_status": 400},
        {"write_status": 302},
        {"requests": 9},
        {"read_attempts": 0},
        {"confirmation": "verified"},
        {"destination": "https://example.com"},
        {"write_path": "/runs"},
        {"project": "other"},
        {"api_key": SECRET},
        {"read_failure": "not_found"},
        {"confirmation": "accepted_only"},
        {"confirmation": "accepted_only", "read_failure": REMOTE},
        {"confirmation": "accepted_only", "read_failure": "refused"},
    ],
)
def test_forged_receipts_are_rejected(changes):
    valid = {
        "trace_id": str(uuid4()),
        "runs_accepted": 4,
        "write_status": 202,
        "confirmation": "service_read",
        "read_attempts": 1,
        "requests": 2,
    }
    assert DeliveryReceipt.model_validate(valid).destination == ORIGIN
    with pytest.raises(ValidationError):
        DeliveryReceipt.model_validate({**valid, **changes})
    unread = {**valid, "confirmation": "accepted_only", "read_failure": "timed_out"}
    assert DeliveryReceipt.model_validate(unread).read_failure == "timed_out"


def command():
    spec = importlib.util.spec_from_file_location(
        "module6_langsmith_command", MODULE / "run_langsmith.py"
    )
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_operator_command_sends_nothing_without_explicit_delivery(
    monkeypatch, key, capsys
):
    wire = Wire(monkeypatch)
    operator = command()
    assert operator.main([]) == 2
    assert "opt-in" in capsys.readouterr().out and wire.sent == []
    assert operator.main(["--preview"]) == 0
    shown = capsys.readouterr().out
    assert wire.sent == [] and "Nothing was sent" in shown
    assert "/runs/batch" in shown
    assert f"{API_KEY_VARIABLE}: set" in shown and SECRET not in shown
    runs = json.loads(shown[shown.index("[") :])
    assert len(runs) == 4 and checked_batch(json.dumps({"post": runs}))
    for bad in (
        ["--deliver", "--preview"],
        ["--api-key", SECRET],
        ["--endpoint", "x"],
        ["--path", "/runs"],
    ):
        with pytest.raises(SystemExit):
            operator.main(bad)
    assert wire.sent == []


def test_operator_command_reports_delivery_and_failure_without_secrets(
    monkeypatch, key, capsys
):
    wire = Wire(monkeypatch)
    operator = command()
    assert operator.main(["--deliver"]) == 0
    shown = capsys.readouterr().out
    assert len(wire.sent) == 2 and "Delivery confirmed" in shown
    assert '"confirmation": "service_read"' in shown
    assert '"runs_accepted": 4' in shown and "no model inference" in shown
    assert_nothing_remote_or_secret(shown, origin_allowed=True)
    Wire(monkeypatch, read=503)
    assert operator.main(["--deliver"]) == 3
    shown = capsys.readouterr().out
    assert "[service_failed]" in shown and "not confirmed" in shown
    assert_nothing_remote_or_secret(shown, origin_allowed=True)
    Wire(monkeypatch, post=400)
    assert operator.main(["--deliver"]) == 1
    shown = capsys.readouterr().out
    assert "Delivery failed [request_rejected]" in shown and "(HTTP 400)" in shown
    assert "0 of 4 runs were accepted" in shown and "unaffected" in shown
    assert_nothing_remote_or_secret(shown, origin_allowed=True)
    Wire(monkeypatch, post=requests.exceptions.SSLError)
    assert operator.main(["--deliver"]) == 1
    shown = capsys.readouterr().out
    assert "Delivery failed [tls_failed]" in shown
    assert_nothing_remote_or_secret(shown, origin_allowed=True)
    monkeypatch.delenv(API_KEY_VARIABLE)
    untouched = Wire(monkeypatch)
    assert operator.main(["--deliver"]) == 1
    shown = capsys.readouterr().out
    assert f"{API_KEY_VARIABLE} is not set" in shown and untouched.sent == []


# Bounded inspection of a failed 4xx write reply: untrusted remote content is
# reduced to an application-owned classification and can never be disclosed.

from multi_agent_orchestration.langsmith_delivery import (  # noqa: E402
    MAX_REPLY_BYTES,
    REPLY_TOKENS,
    ReplyHint,
    classify_reply,
)

API_KEY_LIKE = "lsv2_" + "pt_0123456789abcdef0123456789abcdef_0123456789"
BEARER_LIKE = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.c2ln"
UUID_LIKE = "123e4567-e89b-12d3-a456-426614174000"
URL_LIKE = "https://evil.example.com/steal?session=abc"
HOSTILE_PIECES = (
    SECRET,
    REMOTE,
    API_KEY_LIKE,
    "0123456789abcdef",
    BEARER_LIKE,
    "eyJhbGci",
    UUID_LIKE,
    "evil.example.com",
    "alert(",
    "<script",
    "quick brown fox",
    "12345",
)


def padded(prefix: bytes, size: int) -> bytes:
    return prefix + b"x" * (size - len(prefix))


EXACT = b'{"detail": "dotted_order ' + b"x" * (MAX_REPLY_BYTES - 27) + b'"}'
LARGE_JSON = b'{"detail": "tenant ' + b"x" * 3000 + b' workspace"}'
LARGE_TEXT = padded(b"multipart ", 3000) + b" workspace " + b"y" * 2000
SPLIT_CHARACTER = b"endpoint " + b"x" * (MAX_REPLY_BYTES - 10) + "é".encode()

# name, body, content type, declared, observed, complete, mentions
REPLIES = [
    (
        "json_error",
        b'{"detail": "Invalid dotted_order: timestamp must match start_time"}',
        "application/json",
        "json",
        "json",
        True,
        ("dotted_order", "invalid", "start_time", "timestamp"),
    ),
    (
        "json_validation_list",
        json.dumps(
            {
                "detail": [
                    {
                        "loc": ["body", "post", 0, "trace_id"],
                        "msg": "Field required",
                        "type": "missing",
                    }
                ]
            }
        ).encode(),
        "application/json; charset=utf-8",
        "json",
        "json",
        True,
        ("body", "missing", "required", "trace_id"),
    ),
    (
        "json_array",
        b'["dotted_order", 42, null]',
        "application/problem+json",
        "json",
        "json",
        True,
        ("dotted_order",),
    ),
    (
        "html_page",
        (
            "<!DOCTYPE html><html><head><script>alert('"
            + SECRET
            + "')</script></head><body><h1>400 Bad Request</h1>"
            + URL_LIKE
            + "</body></html>"
        ).encode(),
        "text/html",
        "html",
        "html",
        True,
        ("body", "session"),
    ),
    (
        "html_declared_as_json",
        b"<html><body>gateway rejected the request</body></html>",
        "application/json",
        "json",
        "html",
        True,
        ("body",),
    ),
    (
        "plain_text",
        b"Bad Request: multipart ingestion required; this endpoint is deprecated",
        "text/plain",
        "text",
        "text",
        True,
        ("deprecated", "endpoint", "multipart", "required"),
    ),
    (
        "malformed_json",
        b'{"detail": "dotted_order',
        "application/json",
        "json",
        "unknown",
        True,
        (),
    ),
    (
        "malformed_json_undeclared",
        b'{"detail": dotted_order}',
        None,
        "unknown",
        "unknown",
        True,
        (),
    ),
    (
        "malformed_utf8",
        b"\xff\xfe dotted_order \xc3\x28 workspace",
        "application/json",
        "json",
        "unknown",
        True,
        (),
    ),
    ("empty", b"", "application/json", "json", "empty", True, ()),
    ("whitespace", b" \r\n\t ", "text/plain", "text", "empty", True, ()),
    (
        "exactly_2048",
        EXACT,
        "application/json",
        "json",
        "json",
        False,
        ("dotted_order",),
    ),
    ("larger_json", LARGE_JSON, "application/json", "json", "unknown", False, ()),
    ("larger_text", LARGE_TEXT, "text/plain", "text", "text", False, ("multipart",)),
    (
        "split_character",
        SPLIT_CHARACTER,
        "text/plain",
        "text",
        "text",
        False,
        ("endpoint",),
    ),
    (
        "api_key_like",
        json.dumps(
            {"detail": f"api key {API_KEY_LIKE} rejected", "x-api-key": SECRET}
        ).encode(),
        "application/json",
        "json",
        "json",
        True,
        (),
    ),
    (
        "bearer_and_authorization",
        json.dumps(
            {"authorization": BEARER_LIKE, "error": "token secret password credential"}
        ).encode(),
        "application/json",
        "json",
        "json",
        True,
        (),
    ),
    (
        "urls_and_uuids",
        f"see {URL_LIKE} and {UUID_LIKE} at 10.0.0.1:8443".encode(),
        "text/plain",
        "text",
        "text",
        True,
        ("session",),
    ),
    (
        "arbitrary_prose",
        b"The quick brown fox jumps over the lazy dog 12345 times.",
        "text/plain",
        "text",
        "text",
        True,
        (),
    ),
    (
        "allowlisted_words_only_as_substrings",
        (
            b"multipartite workspaces deprecatedness xtrace_idx my_dotted_order_value "
            b"sessionname runtime formatting endpoints tenants invalidated identity "
            b"tagsoup metadatax"
        ),
        "text/plain",
        "text",
        "text",
        True,
        (),
    ),
    (
        "mixed_case_tokens",
        b"DOTTED_ORDER is Invalid; Trace_Id MISSING; use MultiPart, WORKSPACE",
        "text/plain",
        "text",
        "text",
        True,
        ("dotted_order", "invalid", "missing", "multipart", "trace_id", "workspace"),
    ),
    (
        "unknown_content_type",
        b"runs batch unsupported",
        "application/octet-stream",
        "unknown",
        "text",
        True,
        ("batch", "runs", "unsupported"),
    ),
]
REPLY_IDS = [case[0] for case in REPLIES]


def test_allowlist_is_closed_schema_vocabulary_without_credential_terms():
    assert len(REPLY_TOKENS) == len(set(REPLY_TOKENS)) == 51
    assert all(delivery._WORD.fullmatch(token) for token in REPLY_TOKENS)
    assert all(token == token.lower() and len(token) <= 13 for token in REPLY_TOKENS)
    for forbidden in (
        "key",
        "api",
        "apikey",
        "api_key",
        "token",
        "bearer",
        "authorization",
        "auth",
        "secret",
        "password",
        "credential",
        "cookie",
        "user",
        "email",
    ):
        assert forbidden not in REPLY_TOKENS
    # A deliberate snapshot: changing what a reply may reveal changes this test.
    assert REPLY_TOKENS == (
        "id",
        "trace_id",
        "parent_run_id",
        "dotted_order",
        "start_time",
        "end_time",
        "name",
        "run_type",
        "inputs",
        "outputs",
        "events",
        "extra",
        "metadata",
        "tags",
        "session_name",
        "session_id",
        "session",
        "project",
        "run",
        "runs",
        "trace",
        "batch",
        "multipart",
        "endpoint",
        "method",
        "deprecated",
        "unsupported",
        "version",
        "upgrade",
        "workspace",
        "tenant",
        "organization",
        "required",
        "missing",
        "invalid",
        "format",
        "schema",
        "json",
        "body",
        "payload",
        "uuid",
        "timestamp",
        "datetime",
        "future",
        "duplicate",
        "exists",
        "empty",
        "size",
        "limit",
        "quota",
        "usage",
    )
    # Every run field this story transmits is diagnosable by name.
    transmitted = set(valid_runs()[1]) - {"error"}
    assert transmitted <= set(REPLY_TOKENS)


@pytest.mark.parametrize(
    "name,body,content_type,declared,observed,complete,mentions",
    REPLIES,
    ids=REPLY_IDS,
)
def test_reply_classifier_reduces_untrusted_bytes_to_the_closed_vocabulary(
    name, body, content_type, declared, observed, complete, mentions
):
    hint = classify_reply(content_type, body[:MAX_REPLY_BYTES])
    assert hint == ReplyHint(
        declared=declared, observed=observed, complete=complete, mentions=mentions
    )
    assert set(hint.mentions) <= set(REPLY_TOKENS)
    assert list(hint.mentions) == sorted(set(hint.mentions))
    surface = hint.model_dump_json() + repr(hint) + str(hint)
    for piece in HOSTILE_PIECES:
        assert piece not in surface
    # Bytes beyond the bound are ignored even when handed in.
    assert classify_reply(content_type, body) == hint


@pytest.mark.parametrize(
    "content_type,raw",
    [
        (None, None),
        (b"application/json", b"{}"),
        (42, "not bytes"),
        ({"x": SECRET}, [SECRET]),
        ("application/json" + "x" * 5000, b"{}"),
        (SECRET, bytearray(b'{"detail": "dotted_order"}')),
        ("TEXT/HTML; charset=" + REMOTE, b"plain workspace"),
    ],
)
def test_reply_classifier_never_raises_and_never_echoes_its_arguments(
    content_type, raw
):
    hint = classify_reply(content_type, raw)
    text = hint.model_dump_json()
    assert SECRET not in text and REMOTE not in text
    assert hint.declared in ("json", "html", "text", "unknown")
    assert set(hint.mentions) <= set(REPLY_TOKENS)
    if type(raw) is not bytes:
        assert hint.observed == "empty" and hint.mentions == ()


@pytest.mark.parametrize(
    "changes",
    [
        {"mentions": ("workspace", "tenant")},
        {"mentions": ("tenant", "tenant")},
        {"mentions": (SECRET,)},
        {"mentions": ("key",)},
        {"mentions": ("Workspace",)},
        {"observed": "unknown", "mentions": ("tenant",)},
        {"observed": "empty", "mentions": ("tenant",)},
        {"observed": "binary"},
        {"declared": REMOTE},
        {"complete": "yes"},
        {"text": REMOTE},
        {"body": "x"},
    ],
)
def test_forged_reply_hints_are_rejected(changes):
    valid = {"declared": "json", "observed": "json", "complete": True, "mentions": ()}
    assert ReplyHint.model_validate(valid).mentions == ()
    with pytest.raises(ValidationError):
        ReplyHint.model_validate({**valid, **changes})


@pytest.mark.parametrize(
    "name,body,content_type,declared,observed,complete,mentions",
    REPLIES,
    ids=REPLY_IDS,
)
def test_hostile_4xx_reply_cannot_escape_or_change_what_delivery_does(
    monkeypatch,
    key,
    caplog,
    capsys,
    name,
    body,
    content_type,
    declared,
    observed,
    complete,
    mentions,
):
    wire = Wire(monkeypatch, post=400, body=body, content_type=content_type)
    _, trace = traced()
    sender = adapter()
    with pytest.raises(TraceDeliveryError) as raised:
        sender.deliver(trace)
    error = raised.value
    assert error.reply_hint == ReplyHint(
        declared=declared, observed=observed, complete=complete, mentions=mentions
    )
    # Exactly one read, of at most 2048 bytes, and never an unbounded one.
    assert wire.raw_reads == [("POST", 400, 2048, min(len(body), 2048))]
    assert wire.body_reads == []
    # Whatever the reply contains, behaviour is identical: one request, no
    # retry, no read-back, the same category, counts and message, budget spent.
    assert len(wire.sent) == 1 and wire.sent[0][0].url == WRITE_URL
    assert error.category == "request_rejected" and error.http_status == 400
    assert (error.accepted_runs, error.planned_runs) == (0, 4)
    assert str(error) == (
        "LangSmith rejected the request (HTTP 400). 0 of 4 runs were accepted."
    )
    assert error.workspace_header_sent is False
    assert error.__cause__ is None and error.__context__ is None
    with pytest.raises(TraceDeliveryError) as spent:
        sender.deliver(trace)
    assert spent.value.category == "refused" and len(wire.sent) == 1
    surface = public_surface(error) + caplog.text
    for piece in HOSTILE_PIECES:
        assert piece not in surface
    assert_nothing_remote_or_secret(public_surface(error))
    # The operator command prints fixed labels and allowlisted names only.
    Wire(monkeypatch, post=400, body=body, content_type=content_type)
    assert command().main(["--deliver"]) == 1
    shown = capsys.readouterr().out
    listed = ", ".join(mentions) or "none"
    assert (
        f"Reply classification: declared {declared}; observed {observed}; "
        f"complete: {complete}; mentions: {listed}"
    ) in shown
    assert "Workspace header sent: no" in shown
    for piece in HOSTILE_PIECES:
        assert piece not in shown
    assert_nothing_remote_or_secret(shown, origin_allowed=True)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422, 429, 499])
def test_every_4xx_write_reply_is_read_once_and_at_most_2048_bytes(
    monkeypatch, key, status
):
    body = b'{"detail": "' + b"z" * 10000 + b' workspace"}'
    wire = Wire(monkeypatch, post=status, body=body)
    _, trace = traced()
    with pytest.raises(TraceDeliveryError) as raised:
        adapter().deliver(trace)
    assert wire.raw_reads == [("POST", status, MAX_REPLY_BYTES, 2048)]
    assert MAX_REPLY_BYTES == 2048 and wire.body_reads == []
    assert raised.value.reply_hint.mentions == () and len(wire.sent) == 1
    assert raised.value.reply_hint.complete is False


@pytest.mark.parametrize("status", [200, 201, 202, 204, 301, 302, 500, 502, 503, 599])
def test_no_other_write_reply_is_ever_inspected(monkeypatch, key, status):
    wire = Wire(monkeypatch, post=status, body=b'{"detail": "dotted_order"}')
    _, trace = traced()
    hint = None
    try:
        adapter().deliver(trace)
    except TraceDeliveryError as error:
        hint = error.reply_hint
    assert hint is None
    assert [read for read in wire.raw_reads if read[0] == "POST"] == []


@pytest.mark.parametrize("read", [400, 404, 403, 422])
def test_failed_read_back_replies_are_never_inspected(monkeypatch, key, read):
    wire = Wire(monkeypatch, read=read, body=b'{"detail": "dotted_order"}')
    _, trace = traced()
    receipt = adapter().deliver(trace)
    assert receipt.confirmation == "accepted_only"
    assert wire.raw_reads == [] and wire.body_reads == []
    assert "mentions" not in receipt.model_dump_json()


@pytest.mark.parametrize("fault", [RuntimeError, OSError, ValueError, MemoryError])
def test_fault_while_reading_the_reply_fails_closed(monkeypatch, key, caplog, fault):
    wire = Wire(monkeypatch, post=400, raw_fault=fault)
    _, trace = traced()
    with pytest.raises(TraceDeliveryError) as raised:
        adapter().deliver(trace)
    error = raised.value
    assert error.reply_hint == ReplyHint(
        declared="unknown", observed="unknown", complete=False
    )
    assert error.category == "request_rejected" and len(wire.sent) == 1
    assert error.__cause__ is None and error.__context__ is None
    assert_nothing_remote_or_secret(public_surface(error))
    assert SECRET not in caplog.text and REMOTE not in caplog.text


def test_workspace_header_fact_is_a_boolean_and_never_the_value(
    monkeypatch, key, capsys
):
    workspace = "11111111-2222-3333-4444-555555555555"
    monkeypatch.setenv("LANGSMITH_WORKSPACE_ID", workspace)
    wire = Wire(monkeypatch, post=400, body=b'{"detail": "tenant invalid"}')
    _, trace = traced()
    with pytest.raises(TraceDeliveryError) as raised:
        adapter().deliver(trace)
    assert raised.value.workspace_header_sent is True
    assert wire.sent[0][0].headers["X-Tenant-Id"] == workspace
    assert workspace not in public_surface(raised.value)
    Wire(monkeypatch, post=400, body=b'{"detail": "tenant invalid"}')
    assert command().main(["--deliver"]) == 1
    shown = capsys.readouterr().out
    assert "Workspace header sent: yes" in shown and workspace not in shown
    assert "mentions: invalid, tenant" in shown


def test_reply_hint_is_data_only_and_never_steers_the_adapter():
    import ast

    source = (
        MODULE / "src" / "multi_agent_orchestration" / "langsmith_delivery.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    steering = (ast.If, ast.While, ast.IfExp, ast.Assert, ast.Match, ast.BoolOp)
    for node in ast.walk(tree):
        if isinstance(node, steering):
            probe = node.test if hasattr(node, "test") else node
            names = {
                item.attr for item in ast.walk(probe) if isinstance(item, ast.Attribute)
            } | {item.id for item in ast.walk(probe) if isinstance(item, ast.Name)}
            assert not names & {"reply_hint", "hint", "workspace_header_sent"}
    # The only uses are the assignment in the session and the hand-off to the
    # public error; nothing reads its fields inside the adapter.
    assert source.count("session.reply_hint") == 1
    assert ".mentions" not in source.split("class TraceDeliveryError")[1]
    assert ".observed" not in source.split("class TraceDeliveryError")[1]


# Credential format validation: a malformed credential is refused locally,
# before any session, client or request exists. The failure that motivated it
# was a paste that delivered the single control character U+0016.

from multi_agent_orchestration.langsmith_delivery import (  # noqa: E402
    credential_format_valid,
    credential_usable,
    normalized_credential,
)

VALID_LOOKING = "lsv2_" + "pt_0123456789abcdef0123456789abcdef_0123456789"
INVALID_FORMAT = f"{API_KEY_VARIABLE} has an invalid format. Nothing was sent."
NOT_SET = f"{API_KEY_VARIABLE} is not set in this process. Nothing was sent."

# Text that is present but unusable: delivery must say "invalid format".
MALFORMED = {
    "ascii_22_alone": "\x16",
    "ascii_22_twice": "\x16\x16",
    "ascii_22_inside": "lsv2_pt_0123\x16abcdef",
    "ascii_22_prefix": "\x16" + VALID_LOOKING,
    "ascii_22_suffix": VALID_LOOKING + "\x16",
    "soh_control": "lsv2\x01abcdef",
    "bel_control": "lsv2\x07abcdef",
    "backspace_control": "lsv2\x08abcdef",
    "escape_control": "lsv2\x1babcdef",
    "inner_tab": "lsv2_pt\tabcdef",
    "inner_newline": "lsv2_pt\nabcdef",
    "inner_carriage_return": "lsv2_pt\rabcdef",
    "inner_unit_separator": "lsv2_pt\x1fabcdef",
    "del_127_alone": "\x7f",
    "del_127_inside": "lsv2_pt\x7fabcdef",
    "inner_space": "lsv2_pt abcdef",
    "latin_1": "cl\xe9-secr\xe8te-0123",
    "cyrillic": "ключ-0123456789",
    "bom_read_as_ansi": "\xef\xbb\xbf" + VALID_LOOKING,
    "true_bom": "﻿" + VALID_LOOKING,
    "zero_width_space": "lsv2_pt​abcdef",
    "typographic_quotes": "“" + VALID_LOOKING + "”",
    "c1_control": "lsv2_pt\x9babcdef",
    "one_character": "a",
    "one_character_quoted": '"a"',
    "one_character_after_nested_quotes": "'\"a",
    "one_character_padded": "  z \r\n",
    "quotes_only": '""',
    "single_quotes_only": "''",
    "mixed_quotes_only": "'\"'\"",
    "quotes_around_spaces": '"   "',
}
# Present text that normalizes to a usable credential.
WELL_FORMED = {
    "representative": VALID_LOOKING,
    "two_characters": "ab",
    "all_visible_punctuation": "!#$%&()*+,-./:;<=>?@[]^_`{|}~",
    "surrounding_spaces": "  " + VALID_LOOKING + "  ",
    "trailing_newline": VALID_LOOKING + "\r\n",
    "double_quoted": '"' + VALID_LOOKING + '"',
    "single_quoted": "'" + VALID_LOOKING + "'",
    "nested_quotes": "'\"" + VALID_LOOKING + "\"'",
    "story_test_secret": SECRET,
}


def assert_credential_text_absent(text, value):
    """Neither the credential, a visible fragment of it, nor its length appears."""
    normalized = normalized_credential(value)
    for piece in {value, normalized, value.strip()}:
        if len(piece) > 1:
            assert piece not in text
    visible = "".join(char for char in value if "!" <= char <= "~")
    if len(visible) >= 6:
        assert visible[:6] not in text and visible[-6:] not in text
    assert not any(ord(char) < 32 and char not in "\n\r" for char in text)
    assert "\x7f" not in text and "\x16" not in text


@pytest.mark.parametrize("code", [*range(0, 33), 127, *range(128, 161), 173])
def test_no_control_space_or_non_ascii_character_is_ever_format_valid(code):
    char = chr(code)
    assert not credential_format_valid(char)
    assert not credential_format_valid(char * 2)
    assert not credential_format_valid(f"lsv2_pt_0123{char}abcdef")
    assert not credential_format_valid(f"ab{char}cd")


@pytest.mark.parametrize("code", range(0x21, 0x7F))
def test_every_visible_ascii_character_is_accepted_in_a_credential(code):
    # Quotes are normalized away at the edges, so place each one in the middle.
    assert credential_format_valid(f"ab{chr(code)}cd")
    assert normalized_credential(f"ab{chr(code)}cd") == f"ab{chr(code)}cd"


@pytest.mark.parametrize("name", MALFORMED)
def test_malformed_text_fails_the_format_rule(name):
    assert not credential_format_valid(MALFORMED[name])


@pytest.mark.parametrize("name", WELL_FORMED)
def test_well_formed_text_passes_and_normalizes_to_what_the_sdk_would_send(name):
    import langsmith.utils

    value = WELL_FORMED[name]
    assert credential_format_valid(value)
    normalized = normalized_credential(value)
    # A fixed point of the SDK's own normalization: the SDK will not change it.
    assert langsmith.utils.get_api_key(normalized) == normalized
    assert langsmith.utils.get_api_key(value) is not None
    assert len(normalized) > 1 and all("!" <= char <= "~" for char in normalized)


@pytest.mark.parametrize(
    "value",
    [None, 42, b"lsv2_" + b"pt_bytes", ["x", "y"], {"a": 1}],
)
def test_non_text_is_never_a_valid_credential(value):
    assert not credential_format_valid(value)
    assert normalized_credential(value) == ""


@pytest.mark.parametrize("name", MALFORMED)
def test_malformed_credential_is_refused_locally_with_zero_network_attempts(
    monkeypatch, caplog, capsys, name
):
    import langsmith

    value = MALFORMED[name]
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(delivery, "READ_INTERVAL_S", 0)
    wire = Wire(monkeypatch)
    constructed, original = [], langsmith.Client.__init__

    def counting(self, *args, **kwargs):
        constructed.append(True)
        return original(self, *args, **kwargs)

    sessions, make_session = [], delivery._session

    def counting_session(*args, **kwargs):
        sessions.append(True)
        return make_session(*args, **kwargs)

    monkeypatch.setattr(langsmith.Client, "__init__", counting)
    monkeypatch.setattr(delivery, "_session", counting_session)
    monkeypatch.setenv(API_KEY_VARIABLE, value)
    _, trace = traced()
    sender = adapter()
    assert credential_configured() == bool(value.strip())
    assert not credential_usable()
    with pytest.raises(TraceDeliveryError) as raised:
        sender.deliver(trace)
    error = raised.value
    # Refused before a session or client exists, so nothing can be sent.
    assert wire.sent == [] and constructed == [] and sessions == []
    assert error.category == "refused" and error.http_status is None
    assert error.reply_hint is None and error.accepted_runs is None
    assert str(error) in (INVALID_FORMAT, NOT_SET)
    assert (str(error) == NOT_SET) == (not value.strip())
    assert not any(char.isdigit() for char in str(error))  # No length, no code.
    assert error.__cause__ is None and error.__context__ is None
    surface = public_surface(error) + caplog.text
    assert_credential_text_absent(surface, value)
    # The refusal did not spend the budget: a corrected credential then works.
    monkeypatch.setenv(API_KEY_VARIABLE, VALID_LOOKING)
    assert sender.deliver(trace).confirmation == "service_read"
    assert len(wire.sent) == 2 and constructed == [True] and sessions == [True]
    # The operator command behaves the same way and shows only the format class.
    monkeypatch.setenv(API_KEY_VARIABLE, value)
    silent = Wire(monkeypatch)
    operator = command()
    capsys.readouterr()
    assert operator.main(["--deliver"]) == 1
    shown = capsys.readouterr().out
    assert silent.sent == []
    expected = "invalid format" if value.strip() else "is not set"
    assert f"Delivery failed [refused]: {API_KEY_VARIABLE}" in shown
    assert expected in shown and "Nothing was sent." in shown
    state = "set (format invalid)" if value.strip() else "not set"
    assert f"Credential variable {API_KEY_VARIABLE}: {state}" in shown
    assert "Reply classification" not in shown
    assert_credential_text_absent(shown, value)
    # Preview needs no credential and still makes no request.
    assert operator.main(["--preview"]) == 0
    assert silent.sent == []
    assert_credential_text_absent(capsys.readouterr().out, value)


def test_ascii_22_paste_failure_is_reported_as_invalid_format_only(monkeypatch, capsys):
    wire = Wire(monkeypatch)
    monkeypatch.setenv(API_KEY_VARIABLE, "\x16")
    _, trace = traced()
    with pytest.raises(TraceDeliveryError) as raised:
        adapter().deliver(trace)
    assert str(raised.value) == INVALID_FORMAT and wire.sent == []
    assert command().main(["--deliver"]) == 1
    shown = capsys.readouterr().out
    assert f"Delivery failed [refused]: {INVALID_FORMAT}" in shown
    assert "Credential variable LANGSMITH_API_KEY: set (format invalid)" in shown
    # Only the two lines about the credential are examined: other lines report
    # the workflow and legitimately contain digits and ordinary words.
    about = [
        line.replace(API_KEY_VARIABLE, "")
        for line in shown.splitlines()
        if "Delivery failed" in line or "Credential variable" in line
    ]
    assert len(about) == 2
    for line in about:
        assert not any(char.isdigit() for char in line)
        for revealing in ("SYN", "control", "character", "length", "code", "byte"):
            assert revealing not in line
    assert wire.sent == []


@pytest.mark.parametrize("name", WELL_FORMED)
def test_well_formed_credential_is_sent_normalized_and_only_in_its_header(
    monkeypatch, name
):
    monkeypatch.setattr(delivery, "READ_INTERVAL_S", 0)
    wire = Wire(monkeypatch)
    value = WELL_FORMED[name]
    monkeypatch.setenv(API_KEY_VARIABLE, value)
    _, trace = traced(GraphTopology.COORDINATOR_WORKER)
    assert credential_usable()
    receipt = adapter().deliver(trace)
    assert receipt.confirmation == "service_read"
    sent = normalized_credential(value)
    for prepared, _ in wire.sent:
        assert prepared.headers["x-api-key"] == sent
        assert all("!" <= char <= "~" for char in prepared.headers["x-api-key"])
        # A very short dummy can occur in a URL or body by coincidence.
        if len(sent) >= 8:
            assert sent not in prepared.url and sent not in str(prepared.body)
    if len(sent) >= 8:
        assert sent not in receipt.model_dump_json()


def test_valid_looking_credential_alone_authorizes_nothing(monkeypatch, capsys):
    import langsmith

    def forbidden(*args, **kwargs):
        pytest.fail("A LangSmith client was constructed without explicit delivery")

    wire = Wire(monkeypatch)
    monkeypatch.setattr(langsmith.Client, "__init__", forbidden)
    monkeypatch.setenv(API_KEY_VARIABLE, VALID_LOOKING)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    assert credential_configured() and credential_usable()
    # Running workflows, building the adapter, and the command without
    # --deliver all leave the network untouched.
    result, trace = traced()
    assert result is not None
    adapter()
    operator = command()
    assert operator.main([]) == 2
    shown = capsys.readouterr().out
    assert "opt-in" in shown and VALID_LOOKING not in shown
    assert wire.sent == []
    with pytest.raises(TraceDeliveryError):
        LangSmithTraceDelivery({"mode": MODE, "api_key": VALID_LOOKING})
    assert wire.sent == []


def test_format_validation_precedes_every_external_effect_in_the_source():
    import ast

    source = (
        MODULE / "src" / "multi_agent_orchestration" / "langsmith_delivery.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    deliver = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "deliver"
    )
    calls = [
        (node.lineno, getattr(node.func, "attr", getattr(node.func, "id", "")))
        for node in ast.walk(deliver)
        if isinstance(node, ast.Call)
    ]
    check = min(line for line, name in calls if name == "credential_format_valid")
    run = min(line for line, name in calls if name == "_run")
    assert check < run
    # deliver itself creates no session or client and imports no SDK.
    assert not {"_session", "Client", "import_module"} & {name for _, name in calls}
    # The validator performs no input or output of its own.
    for name in ("normalized_credential", "credential_format_valid"):
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == name
        )
        used = {
            getattr(node.func, "attr", getattr(node.func, "id", ""))
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
        }
        assert used <= {"strip", "all", "len", "type", "normalized_credential"}


# Request accounting: the receipt counts request ATTEMPTS, using the same
# counter that enforces the request budget. Received responses are recorded
# separately as statuses and are never presented as a request count.


def observed_session(monkeypatch):
    """Capture the pinned session of the next delivery for inspection."""
    captured, make_session = [], delivery._session

    def capturing(*args, **kwargs):
        captured.append(make_session(*args, **kwargs))
        return captured[-1]

    monkeypatch.setattr(delivery, "_session", capturing)
    return captured


def test_one_write_and_six_reads_without_a_response_report_seven_requests(
    monkeypatch, key
):
    """The independently reproduced case: unanswered reads must still be counted."""
    captured = observed_session(monkeypatch)
    wire = Wire(monkeypatch, read=requests.ConnectionError)
    _, trace = traced()
    receipt = adapter().deliver(trace)
    assert len(wire.sent) == 7 and len(wire.writes()) == 1
    assert receipt.confirmation == "accepted_only"
    assert receipt.read_attempts == 6 and receipt.read_failure == "connection_failed"
    assert receipt.requests == 7
    (session,) = captured
    # Attempts and received responses are different facts and stay separate:
    # seven requests were attempted, one response (the write) was received.
    assert session.attempted == 7 == len(wire.sent)
    assert session.statuses == [("POST", 202)]
    assert receipt.write_status == 202


@pytest.mark.parametrize(
    "reads,attempts,responses,confirmation",
    [
        (["match"], 1, 2, "service_read"),
        ([404, "match"], 2, 3, "service_read"),
        ([404, 404, "match"], 3, 4, "service_read"),
        ([requests.ConnectionError, "match"], 2, 2, "service_read"),
        (
            [requests.ReadTimeout, 404, requests.ConnectionError, "match"],
            4,
            3,
            "service_read",
        ),
        ([requests.ConnectionError] * 5 + ["match"], 6, 2, "service_read"),
        ([404] * 6, 6, 7, "accepted_only"),
        ([requests.ReadTimeout] * 6, 6, 1, "accepted_only"),
        (
            [500, requests.ConnectionError, 404, 403, requests.ReadTimeout, 429],
            6,
            5,
            "accepted_only",
        ),
    ],
)
def test_receipt_counts_every_attempt_whether_or_not_it_was_answered(
    monkeypatch, key, reads, attempts, responses, confirmation
):
    captured = observed_session(monkeypatch)
    wire = Wire(monkeypatch, read=list(reads))
    _, trace = traced()
    receipt = adapter().deliver(trace)
    assert receipt.confirmation == confirmation
    assert receipt.read_attempts == attempts
    # One write plus every read attempt, answered or not.
    assert receipt.requests == 1 + attempts == len(wire.sent)
    (session,) = captured
    assert session.attempted == receipt.requests
    # Responses actually received are recorded on their own and may be fewer.
    assert len(session.statuses) == responses <= receipt.requests
    assert session.statuses[0] == ("POST", 202)
    assert receipt.requests <= MAX_REQUESTS


def test_successful_delivery_reports_one_write_and_its_reads(monkeypatch, key):
    captured = observed_session(monkeypatch)
    wire = Wire(monkeypatch)
    _, trace = traced()
    receipt = adapter().deliver(trace)
    assert (receipt.read_attempts, receipt.requests) == (1, 2)
    assert captured[0].attempted == 2 == len(wire.sent) == len(captured[0].statuses)


@pytest.mark.parametrize("post", [400, 500, requests.ConnectionError])
def test_failed_write_attempts_exactly_one_request_and_no_read(monkeypatch, key, post):
    captured = observed_session(monkeypatch)
    wire = Wire(monkeypatch, post=post)
    _, trace = traced()
    with pytest.raises(TraceDeliveryError):
        adapter().deliver(trace)
    (session,) = captured
    # The write was attempted once whether or not a response came back.
    assert session.attempted == 1 == len(wire.sent)
    assert len(session.statuses) == (0 if isinstance(post, type) else 1)


@pytest.mark.parametrize("value", ["\x16", "a", "lsv2 pt", "", "   "])
def test_refusal_before_the_network_attempts_no_request(monkeypatch, value):
    captured = observed_session(monkeypatch)
    wire = Wire(monkeypatch)
    monkeypatch.setenv(API_KEY_VARIABLE, value)
    _, trace = traced()
    with pytest.raises(TraceDeliveryError) as raised:
        adapter().deliver(trace)
    # No session exists, so no request could be attempted or counted.
    assert captured == [] and wire.sent == []
    assert raised.value.category == "refused"


def test_refused_requests_are_not_counted_and_the_budget_counts_attempts(
    monkeypatch,
):
    wire = Wire(monkeypatch, read=requests.ConnectionError)
    body = json.dumps({"post": list(valid_runs())})
    session = delivery._session(False, time.monotonic())
    refusals = (
        ("GET", "https://example.com/", body),
        ("POST", f"{ORIGIN}/runs", body),
        ("POST", WRITE_URL, json.dumps({"post": [{"x": 1}]})),
        ("GET", f"{ORIGIN}/runs/{uuid4()}", None),
    )
    for method, url, data in refusals:
        with pytest.raises(TraceDeliveryError):
            session.request(method, url, data=data)
    # Refused before an outbound attempt began: not a request attempt.
    assert session.attempted == 0 and wire.sent == []
    session.request("POST", WRITE_URL, data=body)
    assert session.attempted == 1
    with pytest.raises(TraceDeliveryError):
        session.request("POST", WRITE_URL, data=body)  # Second write refused.
    assert session.attempted == 1 == len(wire.sent)
    session.readable = f"{ORIGIN}/runs/{uuid4()}"
    for expected in range(2, MAX_REQUESTS + 1):
        with pytest.raises(requests.ConnectionError):
            session.request("GET", session.readable)
        assert session.attempted == expected
    # The budget is spent by attempts, although only one response was received.
    assert session.attempted == MAX_REQUESTS == 7 and len(session.statuses) == 1
    with pytest.raises(TraceDeliveryError) as bound:
        session.request("GET", session.readable)
    assert "bound" in str(bound.value)
    assert session.attempted == MAX_REQUESTS == len(wire.sent)


@pytest.mark.parametrize(
    "changes",
    [
        {
            "confirmation": "accepted_only",
            "read_failure": "connection_failed",
            "read_attempts": 6,
            "requests": 1,
        },
        {"read_attempts": 1, "requests": 1},
        {"read_attempts": 1, "requests": 3},
        {"read_attempts": 3, "requests": 3},
        {"read_attempts": 6, "requests": 6},
    ],
)
def test_receipt_rejects_a_request_count_that_is_not_one_write_plus_reads(changes):
    valid = {
        "trace_id": str(uuid4()),
        "runs_accepted": 4,
        "write_status": 202,
        "confirmation": "service_read",
        "read_attempts": 1,
        "requests": 2,
    }
    assert DeliveryReceipt.model_validate(valid).requests == 2
    with pytest.raises(ValidationError):
        DeliveryReceipt.model_validate({**valid, **changes})
    live = {**valid, "read_attempts": 3, "requests": 4}
    assert DeliveryReceipt.model_validate(live).requests == 4
    unanswered = {
        **valid,
        "confirmation": "accepted_only",
        "read_failure": "connection_failed",
        "read_attempts": 6,
        "requests": 7,
    }
    assert DeliveryReceipt.model_validate(unanswered).requests == 7


def test_receipt_request_count_comes_from_the_budget_counter_in_the_source():
    source = (
        MODULE / "src" / "multi_agent_orchestration" / "langsmith_delivery.py"
    ).read_text(encoding="utf-8")
    assert "requests=session.attempted" in source
    assert "requests=len(session.statuses)" not in source
    # One counter: it is advanced in exactly the two places a request is sent
    # and is the value the budget check compares against.
    assert source.count("self.attempted += 1") == 2
    assert "self.attempted >= MAX_REQUESTS" in source
