"""Offline request/response, endpoint, disclosure and supervised-runtime tests."""

import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path

import httpx
import pytest
from multi_agent_orchestration.live_contracts import (
    MAX_TOKEN_COUNT,
    LiveAuthorization,
    LiveBudget,
    ModelSelection,
)
from multi_agent_orchestration.live_errors import LiveExecutionError
from multi_agent_orchestration.live_execution import (
    LiveRuntimeError,
    execute_live_workflow,
)
from multi_agent_orchestration.local_model_gateway import (
    LOCAL_CHAT_ENDPOINT,
    LocalModelGateway,
)
from multi_agent_orchestration.model_gateway import ModelRequest

CANARY = "SYNTHETIC_ADAPTER_SECRET_7431"


def request(**updates):
    fields = {
        "selection": ModelSelection(
            execution_class="local_model_inference",
            provider="ollama",
            model="synthetic:1",
        ),
        "role": "graph_researcher",
        "prompt": "Role and task " + CANARY,
        "max_output_tokens": 256,
        "max_reply_bytes": 1024,
        "timeout_ms": 3000,
    }
    fields.update(updates)
    return ModelRequest(**fields)


def envelope(**updates):
    data = {
        "model": "synthetic:1",
        "done": True,
        "message": {"role": "assistant", "content": '{"findings":["Test"]}'},
    }
    data.update(updates)
    return data


def response(data=None, *, body=None, status=200, headers=None):
    return httpx.Response(
        status,
        headers={"content-type": "application/json", **(headers or {})},
        stream=httpx.ByteStream(
            json.dumps(envelope() if data is None else data).encode()
            if body is None
            else body
        ),
    )


def sanitized(error):
    assert error.__cause__ is None and error.__context__ is None
    for value in (str(error), repr(error), repr(error.args), repr(vars(error))):
        assert CANARY not in value
        assert "127.0.0.1" not in value


async def complete(reply, req=None):
    seen = []

    def handle(req):
        seen.append(req)
        if isinstance(reply, Exception):
            raise reply
        return reply

    adapter = LocalModelGateway(transport=httpx.MockTransport(handle))
    try:
        result = await adapter.complete(request() if req is None else req)
    except LiveExecutionError as error:
        sanitized(error)
        assert len(seen) == 1
        raise
    assert len(seen) == 1
    return result, seen[0]


async def test_request_identity_content_bounds_and_no_authority():
    req = request()
    reply, sent = await complete(response(), req)
    assert str(sent.url) == LOCAL_CHAT_ENDPOINT
    assert sent.method == "POST"
    assert json.loads(sent.content) == {
        "model": req.selection.model,
        "messages": [{"role": "user", "content": req.prompt}],
        "stream": False,
        "options": {"num_predict": req.max_output_tokens},
    }
    assert set(sent.headers) == {
        "host",
        "accept",
        "accept-encoding",
        "connection",
        "user-agent",
        "content-length",
        "content-type",
    }
    assert sent.headers["accept-encoding"] == "identity"
    assert all(
        value == req.timeout_ms / 1000 for value in sent.extensions["timeout"].values()
    )
    assert reply.selection == req.selection
    assert reply.text == envelope()["message"]["content"]
    assert reply.usage.input_tokens is None and reply.usage.output_tokens is None


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://example.com/" + CANARY,
        "http://192.168.0.1:11434/api/chat",
        "http://localhost:11434/api/chat",
        "http://[::1]:11434/api/chat",
        "https://127.0.0.1:11434/api/chat",
        "file:///" + CANARY,
        "ftp://127.0.0.1/",
        "http://" + CANARY + "@127.0.0.1:11434/api/chat",
        "http://user:" + CANARY + "@127.0.0.1:11434/api/chat",
        LOCAL_CHAT_ENDPOINT + "?key=" + CANARY,
        LOCAL_CHAT_ENDPOINT + "#" + CANARY,
        LOCAL_CHAT_ENDPOINT + "/",
        LOCAL_CHAT_ENDPOINT.replace("11434", "12345"),
        "http://2130706433:11434/api/chat",
        "http://127.1:11434/api/chat",
        LOCAL_CHAT_ENDPOINT + "\r\n" + CANARY,
        None,
    ],
)
def test_endpoint_exact_allowlist_no_io(endpoint):
    with pytest.raises(LiveExecutionError) as caught:
        LocalModelGateway(endpoint=endpoint)
    sanitized(caught.value)


@pytest.mark.parametrize(
    "error,category",
    [
        (httpx.ConnectError(CANARY), "connection_failed"),
        (httpx.ReadError(CANARY), "connection_failed"),
        (httpx.RemoteProtocolError(CANARY), "connection_failed"),
        (httpx.ConnectTimeout(CANARY), "timed_out"),
        (httpx.ReadTimeout(CANARY), "timed_out"),
        (httpx.WriteTimeout(CANARY), "timed_out"),
        (httpx.PoolTimeout(CANARY), "timed_out"),
        (ValueError(CANARY), "unexpected_provider_failure"),
        (RuntimeError(CANARY), "unexpected_provider_failure"),
        (OSError(CANARY), "unexpected_provider_failure"),
    ],
)
async def test_transport_failure_closed_zero_retry(error, category):
    with pytest.raises(LiveExecutionError) as caught:
        await complete(error)
    assert caught.value.category == category


@pytest.mark.parametrize(
    "status,category",
    [
        (301, "unexpected_provider_failure"),
        (302, "unexpected_provider_failure"),
        (307, "unexpected_provider_failure"),
        (308, "unexpected_provider_failure"),
        (400, "unexpected_provider_failure"),
        (401, "provider_authentication_failed"),
        (403, "provider_authorization_failed"),
        (429, "rate_limited"),
        (500, "provider_service_failed"),
        (503, "provider_service_failed"),
    ],
)
async def test_status_and_redirect_no_body_disclosure_or_follow(status, category):
    with pytest.raises(LiveExecutionError) as caught:
        await complete(
            response(
                body=CANARY.encode(),
                status=status,
                headers={
                    "location": "https://example.com/" + CANARY,
                    "x-secret": CANARY,
                },
            )
        )
    assert caught.value.category == category


@pytest.mark.parametrize(
    "data",
    [
        [],
        None,
        {CANARY: CANARY},
        envelope(model=CANARY),
        envelope(done=False),
        envelope(done=1),
        envelope(message={}),
        envelope(message=CANARY),
        envelope(message={"role": "user", "content": CANARY}),
        envelope(message={"role": "assistant", "content": ""}),
        envelope(message={"role": "assistant", "content": "   "}),
        envelope(message={"role": "assistant", "content": 12}),
        envelope(message={"role": "assistant", "content": CANARY, "tool_calls": []}),
        envelope(error=CANARY),
        envelope(**{CANARY: CANARY}),
    ],
)
async def test_untrusted_response_shapes_closed(data):
    body = json.dumps(data).encode()
    with pytest.raises(LiveExecutionError) as caught:
        await complete(response(body=body))
    assert caught.value.category == "unexpected_provider_failure"


@pytest.mark.parametrize(
    "body",
    [
        b"{",
        CANARY.encode(),
        b"\xff",
        b'{"model":NaN}',
        b'{"model":"synthetic:1","model":"other"}',
        json.dumps(
            envelope(message={"role": "assistant", "content": "\ud800"})
        ).encode(),
        b"[" * 2000 + b"]" * 2000,
    ],
)
async def test_malformed_json_closed(body):
    with pytest.raises(LiveExecutionError) as caught:
        await complete(response(body=body))
    assert caught.value.category == "unexpected_provider_failure"


@pytest.mark.parametrize(
    "headers",
    [
        {"content-type": "text/plain"},
        {"content-encoding": "gzip"},
    ],
)
async def test_representation_refused(headers):
    with pytest.raises(LiveExecutionError):
        await complete(response(body=CANARY.encode(), headers=headers))


@pytest.mark.parametrize(
    "body",
    [
        b"x" * 10241,
        json.dumps(
            envelope(message={"role": "assistant", "content": "x" * 1025})
        ).encode(),
        json.dumps(
            envelope(message={"role": "assistant", "content": "\u00e9" * 513})
        ).encode(),
    ],
)
async def test_wire_and_utf8_content_bounds(body):
    with pytest.raises(LiveExecutionError) as caught:
        await complete(response(body=body))
    assert caught.value.category == "output_too_large"


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, 0),
        (3, 3),
        (MAX_TOKEN_COUNT, MAX_TOKEN_COUNT),
        (None, None),
        (True, None),
        (-1, None),
        (MAX_TOKEN_COUNT + 1, None),
        ("3", None),
        (3.0, None),
        ({CANARY: CANARY}, None),
    ],
)
async def test_usage_only_faithful_bounded_counts(value, expected):
    reply, _ = await complete(
        response(envelope(prompt_eval_count=value, eval_count=value))
    )
    assert reply.usage.input_tokens == reply.usage.output_tokens == expected


async def test_role_output_is_untrusted_data_no_adapter_repair():
    reply, _ = await complete(
        response(
            envelope(
                message={"role": "assistant", "content": "{" + CANARY},
            )
        )
    )
    assert reply.text == "{" + CANARY


async def test_wrong_provider_or_unchecked_request_no_transport():
    def forbidden(req):
        pytest.fail("Transport must not run.")

    adapter = LocalModelGateway(transport=httpx.MockTransport(forbidden))
    other = request().selection.model_copy(update={"provider": "other"})
    for req in (
        request(selection=other),
        request().model_copy(update={"timeout_ms": 0}),
        request().model_copy(update={"extra": CANARY}),
    ):
        with pytest.raises(LiveExecutionError) as caught:
            await adapter.complete(req)
        sanitized(caught.value)


async def test_total_timeout_and_cancellation_not_retried():
    calls = 0
    entered = asyncio.Event()

    async def blocked(req):
        nonlocal calls
        calls += 1
        entered.set()
        await asyncio.Event().wait()

    adapter = LocalModelGateway(transport=httpx.MockTransport(blocked))
    with pytest.raises(LiveExecutionError) as caught:
        await adapter.complete(request(timeout_ms=20))
    assert caught.value.category == "timed_out"
    sanitized(caught.value)
    assert calls == 1
    entered.clear()
    task = asyncio.create_task(adapter.complete(request()))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls == 2


@pytest.mark.parametrize(
    "scenario,count,repairs,category",
    [
        ("happy", 3, 0, None),
        ("repair", 4, 1, None),
        ("bad_always", 2, 1, "malformed_output"),
        ("connection", 1, 0, "connection_failed"),
    ],
)
async def test_adapter_in_accepted_process_runtime(
    tmp_path,
    monkeypatch,
    scenario,
    count,
    repairs,
    category,
):
    source = (
        Path(__file__).with_name("local_provider_cases.py").read_text(encoding="utf-8")
    )
    log = tmp_path / "calls.jsonl"
    module_path = tmp_path / "synthetic_local_provider.py"
    module_path.write_text(
        source + f"\nSCENARIO = {scenario!r}\nLOG = {str(log)!r}\n",
        encoding="utf-8",
    )
    spec = importlib.util.spec_from_file_location(
        "synthetic_local_provider", module_path
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    spawned = []
    original = asyncio.create_subprocess_exec

    async def observed(*args, **kwargs):
        process = await original(*args, **kwargs)
        spawned.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", observed)
    auth = LiveAuthorization(
        mode="live-model",
        selection=request().selection,
        budget=LiveBudget(
            max_model_calls=4,
            max_repair_attempts=1,
            max_concurrency=1,
            deadline_ms=15000,
            call_timeout_ms=3000,
            max_input_chars=4096,
            max_output_tokens=256,
            max_reply_bytes=1024,
        ),
    )
    if category is None:
        result = await execute_live_workflow(
            "Synthetic task",
            authorization=auth,
            gateway_factory=module.factory,
        )
        accounting = result.evidence.accounting
        assert result.evidence.selection == auth.selection
        assert accounting.usage.input_tokens == count * 2
        assert accounting.usage.output_tokens == count * 3
        assert accounting.transport_retries == 0
    else:
        with pytest.raises(LiveRuntimeError) as caught:
            await execute_live_workflow(
                "Synthetic task",
                authorization=auth,
                gateway_factory=module.factory,
            )
        assert caught.value.category == category
        sanitized(caught.value)
        accounting = caught.value.failure
    assert accounting.model_calls == count
    assert accounting.repair_attempts == repairs
    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(events) == count <= 4
    assert len(spawned) == 1
    assert {event["pid"] for event in events} == {spawned[0].pid}
    assert spawned[0].pid != os.getpid()
    assert spawned[0].returncode is not None and spawned[0].stdin.is_closing()


async def test_default_transport_explicit_zero_retries_and_no_environment(monkeypatch):
    configured = []

    def transport(**kwargs):
        configured.append(kwargs)
        return httpx.MockTransport(lambda req: response())

    monkeypatch.setenv("HTTP_PROXY", "http://" + CANARY + "@example.com")
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", transport)
    await LocalModelGateway().complete(request())
    assert configured == [{"retries": 0, "trust_env": False}]


async def test_stream_bound_stops_reading_and_closes():
    class HostileStream(httpx.AsyncByteStream):
        closed = False
        chunks = 0

        async def __aiter__(self):
            for chunk in (b"x" * 6000, b"x" * 5000, CANARY.encode()):
                self.chunks += 1
                yield chunk

        async def aclose(self):
            self.closed = True

    stream = HostileStream()
    reply = httpx.Response(
        200,
        headers={"content-type": "application/json"},
        stream=stream,
    )
    with pytest.raises(LiveExecutionError) as caught:
        await complete(reply)
    assert caught.value.category == "output_too_large"
    assert stream.closed and stream.chunks == 2


async def test_maximum_json_escaping_and_discarded_provider_metadata():
    text = "\x00" * 1024
    reply, _ = await complete(
        response(
            envelope(
                message={"role": "assistant", "content": text},
                created_at=CANARY,
                total_duration={CANARY: CANARY},
            )
        )
    )
    assert reply.text == text
    assert CANARY not in reply.model_dump_json()


async def test_caller_exception_context_cannot_disclose():
    try:
        raise RuntimeError(CANARY)
    except RuntimeError:
        with pytest.raises(LiveExecutionError) as caught:
            await complete(httpx.ConnectError(CANARY))
        sanitized(caught.value)


def test_invalid_endpoint_caller_exception_context_cannot_disclose():
    try:
        raise RuntimeError(CANARY)
    except RuntimeError:
        with pytest.raises(LiveExecutionError) as caught:
            LocalModelGateway(endpoint="http://example.com/" + CANARY)
        sanitized(caught.value)
