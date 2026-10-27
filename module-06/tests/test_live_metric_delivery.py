"""Real SDK-encoded OTLP to test-owned loopback only; bounded failing I/O."""

import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from multi_agent_orchestration import live_metric_delivery as delivery
from multi_agent_orchestration.live_metrics import LiveOperationalMetrics
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceRequest,
    ExportMetricsServiceResponse,
)

from .test_live_metrics import PRIVATE, add, record, signals


class Receiver:
    def __init__(self):
        self.requests = []
        self.status, self.body = 200, b""
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                packet = self.rfile.read(int(self.headers["Content-Length"]))
                owner.requests.append((self.path, dict(self.headers), packet))
                self.send_response(owner.status)
                self.send_header("Content-Type", "application/x-protobuf")
                self.send_header("Content-Length", str(len(owner.body)))
                self.send_header("Location", "https://must-not-follow.invalid")
                self.end_headers()
                try:
                    self.wfile.write(owner.body)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # A bounded client may close before the large body is sent.

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def config(self, **changes):
        data = dict(
            mode="loopback-otlp-http",
            endpoint=f"http://127.0.0.1:{self.server.server_port}/v1/metrics",
            timeout_ms=2000,
        )
        data.update(changes)
        return delivery.LiveMetricDeliveryConfig(**data)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(2)


@pytest.fixture
def receiver():
    instance = Receiver()
    yield instance
    instance.close()


@pytest.fixture
def metrics(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")
    instance = LiveOperationalMetrics()
    assert add(instance, record()).status == "recorded"
    yield instance
    instance.close()


def config(**changes):
    data = dict(
        mode="loopback-otlp-http",
        endpoint="http://127.0.0.1:4318/v1/metrics",
        timeout_ms=100,
    )
    data.update(changes)
    return delivery.LiveMetricDeliveryConfig(**data)


def test_real_wire_exact_namespace_labels_and_one_shot_sealing(metrics, receiver):
    result = delivery.deliver_live_metrics(metrics, receiver.config())
    assert result.status == "accepted" and result.attempts == 1
    assert result.evidence_class == "otlp_write_unverified"
    assert (
        delivery.deliver_live_metrics(metrics, receiver.config()).failure
        == "already_attempted"
    )
    assert add(metrics, record()).failure == "sealed"
    assert len(receiver.requests) == 1
    path, headers, raw = receiver.requests[0]
    assert path == "/v1/metrics" and headers["Content-Type"] == "application/x-protobuf"
    packet = ExportMetricsServiceRequest()
    packet.ParseFromString(raw)
    data = signals(packet)
    assert set(data) == {
        "module6.live.synthetic.workflow.finished",
        "module6.live.synthetic.workflow.duration",
        "module6.live.synthetic.accounting.observed",
        "module6.live.synthetic.model.calls",
        "module6.live.synthetic.workflow.repair_attempts",
    }
    assert len(raw) <= 65536
    assert not any(key.lower() in ("authorization", "x-api-key") for key in headers)
    assert PRIVATE.encode() not in raw
    metrics.close()
    assert len(receiver.requests) == 1  # shutdown does not export


@pytest.mark.parametrize("status", [302, 400, 401, 403, 429, 500, 503])
def test_http_failure_or_redirect_has_one_request_no_retry(
    metrics, receiver, status, caplog
):
    receiver.status, receiver.body = status, PRIVATE.encode()
    result = delivery.deliver_live_metrics(metrics, receiver.config())
    assert result.status == "failed" and result.failure == "export_failed"
    assert len(receiver.requests) == 1
    assert (
        delivery.deliver_live_metrics(metrics, receiver.config()).failure
        == "already_attempted"
    )
    assert PRIVATE not in repr(result) + caplog.text


@pytest.mark.parametrize("status,consumed", [(302, 0), (200, 1025)])
def test_actual_large_loopback_response_consumption_is_bounded(
    metrics, receiver, monkeypatch, status, consumed, caplog
):
    """Probe actual urllib3 reads and Requests buffering, without faking responses."""
    import requests

    receiver.status, receiver.body = status, b"x" * (1024 * 1024)
    original_send = requests.adapters.HTTPAdapter.send
    replies = []
    reads = []

    def observed_send(adapter, request, **kwargs):
        reply = original_send(adapter, request, **kwargs)
        original_read = reply.raw.read

        def observed_read(*args, **read_kwargs):
            chunk = original_read(*args, **read_kwargs)
            reads.append((args, read_kwargs, len(chunk)))
            return chunk

        reply.raw.read = observed_read
        replies.append(reply)
        return reply

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", observed_send)
    result = delivery.deliver_live_metrics(metrics, receiver.config())
    assert result.status == "failed"
    assert result.failure == ("export_failed" if status == 302 else "invalid_response")
    assert len(receiver.requests) == len(replies) == 1
    assert sum(size for _, _, size in reads) == consumed
    assert replies[0].raw._fp_bytes_read == consumed
    assert replies[0]._content is False
    assert replies[0]._content_consumed is False
    if status == 302:
        assert reads == []  # No body read at all, including inside Session.send.
        assert replies[0].next is None
    else:
        assert len(reads) == 1
        assert reads[0][0] == (1025,)
        assert reads[0][1] == {"decode_content": False}
    assert replies[0].raw.closed
    assert (
        delivery.deliver_live_metrics(metrics, receiver.config()).failure
        == "already_attempted"
    )
    assert PRIVATE not in repr(result) + caplog.text


@pytest.mark.parametrize(
    "body,expected",
    [
        (b"not protobuf " + PRIVATE.encode(), "invalid_response"),
        (b"x" * 1025, "invalid_response"),
        (
            ExportMetricsServiceResponse(
                partial_success={"rejected_data_points": 1, "error_message": PRIVATE}
            ).SerializeToString(),
            "partial",
        ),
        (
            ExportMetricsServiceResponse(
                partial_success={"rejected_data_points": 0, "error_message": PRIVATE}
            ).SerializeToString(),
            "partial",
        ),
    ],
)
def test_bounded_otlp_reply_partial_and_malformed_are_not_success(
    metrics, receiver, body, expected, caplog
):
    receiver.body = body
    result = delivery.deliver_live_metrics(metrics, receiver.config())
    assert result.status == "failed" and result.failure == expected
    assert len(receiver.requests) == 1
    assert PRIVATE not in repr(result) + caplog.text


def test_environment_cannot_activate_redirect_or_decorate_delivery(
    monkeypatch, metrics, receiver
):
    import requests

    for key in (
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_HEADERS",
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
        "OTEL_RESOURCE_ATTRIBUTES",
        "OTEL_EXPORTER_OTLP_CLIENT_KEY",
        "HTTP_PROXY",
        "HTTPS_PROXY",
    ):
        monkeypatch.setenv(key, PRIVATE)
    original = requests.Session.request
    seen = []

    def request(session, method, url, **kwargs):
        assert session.trust_env is False
        assert session.max_redirects == 0
        assert all(a.max_retries.total == 0 for a in session.adapters.values())
        assert kwargs["stream"] and kwargs["allow_redirects"] is False
        assert kwargs.get("auth") is None and kwargs.get("cert") is None
        seen.append(url)
        return original(session, method, url, **kwargs)

    monkeypatch.setattr(requests.Session, "request", request)
    result = delivery.deliver_live_metrics(metrics, receiver.config())
    assert result.status == "accepted" and len(seen) == 1
    assert PRIVATE not in repr(receiver.requests) + repr(result)


@pytest.mark.parametrize(
    "changes",
    [
        {"endpoint": "https://external.invalid/v1/metrics"},
        {"endpoint": "http://localhost:4318/v1/metrics"},
        {"endpoint": "http://127.0.0.1:80/v1/metrics"},
        {"endpoint": "http://127.0.0.1:4318/v1/traces"},
        {"endpoint": "http://127.0.0.1:4318/v1/metrics?q=x"},
        {"endpoint": PRIVATE},
        {"timeout_ms": 0},
        {"timeout_ms": 5001},
        {"timeout_ms": True},
        {"mode": "automatic"},
        {PRIVATE: PRIVATE},
    ],
)
def test_forged_configuration_refuses_without_sealing_or_diagnostics(
    metrics, changes, caplog
):
    data = dict(config().__dict__)
    data.update(changes)
    forged = delivery.LiveMetricDeliveryConfig.model_construct(**data)
    if PRIVATE in changes:
        forged.__dict__[PRIVATE] = PRIVATE
    result = delivery.deliver_live_metrics(metrics, forged)
    assert result.failure == "invalid_config" and result.attempts == 0
    assert not metrics._sealed
    assert PRIVATE not in repr(result) + caplog.text


def test_config_and_collection_require_exact_owned_types(metrics):
    class Child(delivery.LiveMetricDeliveryConfig):
        pass

    for candidate in (None, {}, config().model_dump(), Child(**config().model_dump())):
        assert (
            delivery.deliver_live_metrics(metrics, candidate).failure
            == "invalid_config"
        )
    assert delivery.deliver_live_metrics({}, config()).failure == "invalid_collection"


def test_disabled_empty_closed_and_missing_encoder_refuse_safely(
    metrics, monkeypatch, receiver
):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    assert (
        delivery.deliver_live_metrics(metrics, receiver.config()).failure
        == "sdk_disabled"
    )
    assert not metrics._sealed and receiver.requests == []
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")
    empty = LiveOperationalMetrics()
    try:
        assert (
            delivery.deliver_live_metrics(empty, receiver.config()).failure == "no_data"
        )
    finally:
        empty.close()

    def missing():
        raise ImportError(PRIVATE)

    monkeypatch.setattr(metrics, "_batch", missing)
    assert (
        delivery.deliver_live_metrics(metrics, receiver.config()).failure
        == "sdk_unavailable"
    )
    metrics.close()
    assert delivery.deliver_live_metrics(metrics, receiver.config()).failure == "closed"
    assert receiver.requests == []


def test_oversize_snapshot_refuses_before_network(metrics, monkeypatch, receiver):
    monkeypatch.setattr(metrics, "_batch", lambda: b"x" * 65537)
    result = delivery.deliver_live_metrics(metrics, receiver.config())
    assert result.failure == "collection_failed" and not metrics._sealed
    assert receiver.requests == []


def test_known_partial_collection_cannot_be_delivered_as_complete(metrics, receiver):
    metrics._damaged = True
    result = delivery.deliver_live_metrics(metrics, receiver.config())
    assert result.failure == "collection_failed" and result.attempts == 0
    assert receiver.requests == []


def test_unexpected_transport_exception_and_start_failure_are_isolated(
    metrics, monkeypatch, caplog
):
    def fail(*args):
        raise RuntimeError(PRIVATE)

    monkeypatch.setattr(delivery, "_send_once", fail)
    result = delivery.deliver_live_metrics(metrics, config())
    assert result.failure == "export_failed" and result.attempts == 1
    assert PRIVATE not in repr(result) + caplog.text
    other = LiveOperationalMetrics()
    try:
        assert add(other, record()).status == "recorded"
        with monkeypatch.context() as local:
            local.setattr(threading.Thread, "start", fail)
            assert (
                delivery.deliver_live_metrics(other, config()).failure
                == "export_failed"
            )
    finally:
        other.close()
    # All three global permits were returned even when worker startup failed.
    claimed = [delivery._SLOTS.acquire(blocking=False) for _ in range(3)]
    try:
        assert claimed == [True, True, True]
    finally:
        for acquired in claimed:
            if acquired:
                delivery._SLOTS.release()


def test_actual_requests_resolver_stall_is_bounded_and_late_result_isolated(
    metrics, monkeypatch
):
    entered, release = threading.Event(), threading.Event()

    def resolver(*args, **kwargs):
        entered.set()
        release.wait(5)
        raise socket.gaierror(PRIVATE)

    monkeypatch.setattr(socket, "getaddrinfo", resolver)
    before = set(threading.enumerate())
    result = None
    try:
        started = time.monotonic()
        result = delivery.deliver_live_metrics(metrics, config())
        assert time.monotonic() - started < 1.0
        assert entered.is_set() and result.failure == "timed_out"
        assert metrics.close()  # does not wait for blocked I/O
        assert delivery.deliver_live_metrics(metrics, config()).failure == "closed"
    finally:
        release.set()
        for worker in set(threading.enumerate()) - before:
            if worker.name == "module6-live-metrics":
                worker.join(2)
                assert not worker.is_alive()
    assert result.failure == "timed_out"  # late failure cannot rewrite result


@pytest.mark.parametrize("late", ["accepted", "partial", "export_failed"])
def test_global_surviving_workers_are_bounded_across_windows(monkeypatch, late):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")
    release = threading.Event()
    started = []
    windows = []

    def blocked(batch, selected):
        started.append(threading.current_thread())
        release.wait(5)
        return late

    monkeypatch.setattr(delivery, "_send_once", blocked)
    results = []
    try:
        for _ in range(3):
            window = LiveOperationalMetrics()
            windows.append(window)
            assert add(window, record()).status == "recorded"
            results.append(delivery.deliver_live_metrics(window, config()))
        assert all(r.failure == "timed_out" for r in results)
        assert len(started) == 3 and all(w.is_alive() for w in started)
        for _ in range(20):
            window = LiveOperationalMetrics()
            windows.append(window)
            assert add(window, record()).status == "recorded"
            assert (
                delivery.deliver_live_metrics(window, config()).failure
                == "capacity_spent"
            )
        assert len(started) == 3  # no replacement workers or queued exports
        for window in windows:
            assert (
                delivery.deliver_live_metrics(window, config()).failure
                == "already_attempted"
            )
    finally:
        release.set()
        for worker in started:
            worker.join(2)
            assert not worker.is_alive()
        for window in windows:
            window.close()
    assert all(r.failure == "timed_out" for r in results)
    # Actual worker completion restores global admission.
    fresh = LiveOperationalMetrics()
    try:
        assert add(fresh, record()).status == "recorded"
        result = delivery.deliver_live_metrics(fresh, config(timeout_ms=1000))
        assert result.status == ("accepted" if late == "accepted" else "failed")
    finally:
        fresh.close()


def test_existing_collection_policy_supports_live_namespace_without_trace_export():
    directory = Path(__file__).parents[1] / "telemetry"
    collector = (directory / "otel-collector.yaml").read_text()
    prometheus = (directory / "prometheus.yaml").read_text()
    assert 'IsMatch(name, "^module6\\\\.")' in collector
    assert "traces:" not in collector
    assert "regex: module6_.*" in prometheus
    assert "__name__|job|instance|le|runtime|topology|distributed|outcome" in prometheus
