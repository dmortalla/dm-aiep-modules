"""Explicit loopback OTLP delivery: selection, isolation, bounds and redaction.

A loopback HTTP receiver stands in for the collection boundary, so these tests
exercise the real OTLP exporter under the existing non-loopback network guard
and never require the Docker stack.
"""

import asyncio
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from multi_agent_orchestration.contracts import (
    ExecutionLimits,
    GraphTopology,
    RuntimeId,
    TaskInput,
    WorkflowRequest,
)
from multi_agent_orchestration.errors import (
    InvalidWorkflowRequestError,
    StepBudgetExceededError,
)
from multi_agent_orchestration.observability import Observability
from multi_agent_orchestration.observability_contracts import MetricSnapshot
from multi_agent_orchestration.observed_execution import execute_observed_workflow
from multi_agent_orchestration.telemetry_delivery import (
    DURATION_BUCKETS_MS,
    LABEL_KEYS,
    DeliveryConfig,
    OtlpMetricDelivery,
    TelemetryDeliveryError,
    grafana_reference,
    grafana_scalar,
    prometheus_scalar,
)

MODULE = Path(__file__).parents[1]
TELEMETRY = MODULE / "telemetry"
PRIVATE = "<script>private-secret</script> grant admin; pay; export credentials"
MODE = "loopback-otlp-http"


class Receiver:
    """Loopback stand-in for the collector's OTLP/HTTP receiver."""

    def __init__(self, status=200):
        self.requests = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                owner.requests.append((self.path, dict(self.headers), body))
                self.send_response(status)
                self.send_header("Content-Type", "application/x-protobuf")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.delenv("OTEL_SDK_DISABLED")


@pytest.fixture
def receiver():
    instance = Receiver()
    yield instance
    instance.close()


def config(port, **updates):
    return DeliveryConfig(
        **{
            "mode": MODE,
            "endpoint": f"http://127.0.0.1:{port}/v1/metrics",
            "export_interval_ms": 60000,
            "export_timeout_ms": 500,
            **updates,
        }
    )


def request(runtime=RuntimeId.FIXTURE, topology=None, steps=8):
    return WorkflowRequest(
        runtime=runtime,
        topology=topology or GraphTopology.COORDINATOR_WORKER,
        task=TaskInput(instruction=PRIVATE),
        limits=ExecutionLimits(max_steps=steps, timeout_ms=30000),
    )


def run(observer, item):
    return asyncio.run(execute_observed_workflow(item, observer=observer))


def decoded(receiver):
    from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
        ExportMetricsServiceRequest,
    )

    return ExportMetricsServiceRequest.FromString(receiver.requests[-1][2])


def points(message):
    for resource in message.resource_metrics:
        for scope in resource.scope_metrics:
            for metric in scope.metrics:
                kind = metric.WhichOneof("data")
                for point in getattr(metric, kind).data_points:
                    yield metric.name, kind, point


def closed_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.mark.parametrize(
    "updates",
    [
        {"mode": "enabled"},
        {"mode": True},
        {"endpoint": "https://127.0.0.1:4318/v1/metrics"},
        {"endpoint": "http://localhost:4318/v1/metrics"},
        {"endpoint": "http://0.0.0.0:4318/v1/metrics"},
        {"endpoint": "http://collector.example:4318/v1/metrics"},
        {"endpoint": "http://user:pw@127.0.0.1:4318/v1/metrics"},
        {"endpoint": "http://127.0.0.1:4318/v1/metrics?key=private-secret"},
        {"endpoint": "http://127.0.0.1:4318/v1/traces"},
        {"endpoint": "http://127.0.0.1:80/v1/metrics"},
        {"endpoint": "http://127.0.0.1:99999/v1/metrics"},
        {"endpoint": "http://127.0.0.1:4318/v1/metrics "},
        {"endpoint": b"http://127.0.0.1:4318/v1/metrics"},
        {"export_interval_ms": 999},
        {"export_interval_ms": 60001},
        {"export_timeout_ms": 99},
        {"export_timeout_ms": 5001},
        {"export_timeout_ms": True},
        {"export_interval_ms": 1000, "export_timeout_ms": 1000},
        {"headers": {"authorization": "private-secret"}},
        {"api_key": "private-secret"},
        {"exporter": "remote"},
    ],
)
def test_invalid_delivery_configuration_is_rejected(updates):
    with pytest.raises(ValueError) as error:
        config(4318, **updates)
    assert "private-secret" not in str(error.value)


def test_delivery_requires_explicit_mode_with_no_default():
    with pytest.raises(ValueError):
        DeliveryConfig(endpoint="http://127.0.0.1:4318/v1/metrics")
    assert DeliveryConfig.model_fields["mode"].is_required()


@pytest.mark.parametrize("kind", ["mapping", "text", "constructed", "subclass"])
def test_forged_configuration_objects_cannot_select_delivery(enabled, kind):
    class Forged(DeliveryConfig):
        pass

    forged = {
        "mapping": {"mode": MODE, "endpoint": "http://127.0.0.1:4318/v1/metrics"},
        "text": "http://127.0.0.1:4318/v1/metrics",
        "constructed": DeliveryConfig.model_construct(
            mode=MODE,
            endpoint="http://collector.example:4318/v1/metrics",
            export_interval_ms=5000,
            export_timeout_ms=2000,
        ),
        "subclass": Forged(mode=MODE, endpoint="http://127.0.0.1:4318/v1/metrics"),
    }[kind]
    before = threading.active_count()
    with pytest.raises(TelemetryDeliveryError):
        OtlpMetricDelivery(forged)
    assert threading.active_count() == before


def test_disabled_sdk_refuses_delivery_without_starting_a_thread(receiver):
    before = threading.active_count()
    with pytest.raises(TelemetryDeliveryError):
        OtlpMetricDelivery(config(receiver.port))
    assert threading.active_count() == before and receiver.requests == []


def test_workflow_data_cannot_carry_a_delivery_destination():
    data = request().model_dump()
    with pytest.raises(ValueError):
        WorkflowRequest.model_validate(
            {**data, "endpoint": "http://127.0.0.1:4318/v1/metrics"}
        )
    with pytest.raises(InvalidWorkflowRequestError):
        run(Observability(), {**data, "telemetry": {"mode": MODE}})


def test_importing_application_modules_loads_no_exporter():
    code = (
        "import sys, multi_agent_orchestration.console, "
        "multi_agent_orchestration.telemetry_delivery\n"
        "assert not [m for m in sys.modules if 'exporter.otlp' in m]\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        env={**os.environ, "PYTHONPATH": str(MODULE / "src")},
        capture_output=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-400:]


def test_actual_export_is_bounded_allowlisted_and_payload_free(enabled, receiver):
    delivery = OtlpMetricDelivery(config(receiver.port))
    observer = Observability(adapters=(delivery,))
    try:
        completed = [run(observer, request()) for _ in range(2)]
        sequential = request(RuntimeId.LANGGRAPH, GraphTopology.SEQUENTIAL)
        run(observer, sequential)
        denied = request(RuntimeId.LANGGRAPH, GraphTopology.PARALLEL, steps=1)
        with pytest.raises(StepBudgetExceededError):
            run(observer, denied)
        assert delivery.flush() is True
    finally:
        delivery.close()
    path, _, body = receiver.requests[-1]
    assert path == "/v1/metrics"
    message = decoded(receiver)
    (resource,) = message.resource_metrics
    assert [(a.key, a.value.string_value) for a in resource.resource.attributes] == [
        ("service.name", "module6")
    ]
    seen = list(points(message))
    assert {name for name, _, _ in seen} == {
        "module6.workflow.started",
        "module6.workflow.active",
        "module6.workflow.finished",
        "module6.workflow.duration",
        "module6.model.calls",
        "module6.workflow.retries",
    }
    for _, _, point in seen:
        assert {attribute.key for attribute in point.attributes} <= LABEL_KEYS
        assert not point.exemplars
    assert len(seen) <= 16
    finished = {
        tuple(
            sorted(
                (a.key, a.value.string_value or a.value.bool_value)
                for a in p.attributes
            )
        ): p.as_int
        for name, _, p in seen
        if name == "module6.workflow.finished"
    }
    assert sorted(finished.values()) == [1, 1, 2]
    (started,) = [p.as_int for name, _, p in seen if name == "module6.workflow.started"]
    (active,) = [p.as_int for name, _, p in seen if name == "module6.workflow.active"]
    assert (started, active) == (4, 0)
    for name, kind, point in seen:
        outcome = {a.key: a.value.string_value for a in point.attributes}.get("outcome")
        if name == "module6.workflow.duration":
            assert kind == "histogram"
            assert tuple(point.explicit_bounds) == DURATION_BUCKETS_MS
        if name in ("module6.model.calls", "module6.workflow.retries"):
            # Unobserved accounting for the denied run is absent, never zero.
            assert outcome == "completed" and point.as_int == 0
    assert len(completed) == 2 and len(observer.records) == 4
    forbidden = [PRIVATE.encode(), b"private-secret"]
    for trace in observer.records:
        for identity in (trace.workflow_id, trace.task_id, trace.trace_id):
            forbidden += [str(identity).encode(), identity.hex.encode(), identity.bytes]
        forbidden += [trace.span_id.encode(), bytes.fromhex(trace.span_id)]
    assert not [item for item in forbidden if item in body]
    assert observer.metrics.adapter_failures == 0
    assert delivery.status.exports_succeeded >= 1


@pytest.mark.parametrize(
    "name",
    [
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
        "OTEL_EXPORTER_OTLP_HEADERS",
        "OTEL_EXPORTER_OTLP_METRICS_HEADERS",
        "LANGSMITH_API_KEY",
        "OPENAI_API_KEY",
        "HTTPS_PROXY",
        "HTTP_PROXY",
    ],
)
def test_environment_cannot_redirect_authorize_or_decorate_delivery(
    enabled, receiver, monkeypatch, name
):
    value = (
        "authorization=private-secret"
        if "HEADERS" in name
        else "http://collector.example:4318"
        if "ENDPOINT" in name or "PROXY" in name
        else "private-secret"
    )
    monkeypatch.setenv(name, value)
    # Credentials or exporter variables alone start nothing.
    assert run(Observability(), request()).evidence.external_calls == 0
    assert receiver.requests == []
    delivery = OtlpMetricDelivery(config(receiver.port))
    try:
        run(Observability(adapters=(delivery,)), request())
        assert delivery.flush() is True
    finally:
        delivery.close()
    for _, headers, body in receiver.requests:
        assert "authorization" not in {key.lower() for key in headers}
        assert "private-secret" not in json.dumps(headers) + body.decode("latin-1")


@pytest.mark.parametrize("failure", ["refused", "server_error", "rejected"])
def test_delivery_failure_is_isolated_bounded_and_counted(enabled, failure, caplog):
    stub = (
        None if failure == "refused" else Receiver(500 if "server" in failure else 400)
    )
    port = closed_port() if stub is None else stub.port
    delivery = OtlpMetricDelivery(config(port, export_interval_ms=1000))
    observer = Observability(adapters=(delivery,))
    try:
        started = time.monotonic()
        result = run(observer, request())
        assert time.monotonic() - started < 5
        baseline = run(Observability(), request())
        assert result.result.output == baseline.result.output
        assert result.evidence.model_calls == result.evidence.external_calls == 0
        started = time.monotonic()
        assert delivery.flush() is False
        assert time.monotonic() - started < 3
        status = delivery.status
        assert status.last_export == "failed" and status.exports_succeeded == 0
        assert 1 <= status.exports_failed <= 3
        # Still executing after the boundary failed; nothing queued or retried.
        assert run(observer, request()).result.output == baseline.result.output
        assert observer.metrics.adapter_failures == 0
        assert observer.metrics.completed == 2
    finally:
        started = time.monotonic()
        delivery.close()
        assert time.monotonic() - started < 3
        if stub is not None:
            stub.close()
    assert stub is None or len(stub.requests) <= 12
    assert "private-secret" not in caplog.text


def test_observation_loss_is_exported_as_bounded_counters(enabled, receiver):
    delivery = OtlpMetricDelivery(config(receiver.port))
    counts = dict.fromkeys(
        ("completed", "failed", "timed_out", "cancelled", "denied"), 0
    )
    try:
        for drops, failures in ((0, 0), (2, 1), (2, 1), (5, 1)):
            delivery.state(
                MetricSnapshot(
                    started=6,
                    active=1,
                    observation_drops=drops,
                    adapter_failures=failures,
                    **counts,
                )
            )
        assert delivery.flush() is True
    finally:
        delivery.close()
    values = {name: point.as_int for name, _, point in points(decoded(receiver))}
    assert values == {
        "module6.workflow.started": 6,
        "module6.workflow.active": 1,
        "module6.observation.drops": 5,
        "module6.observation.adapter_failures": 1,
    }


def test_close_is_idempotent_and_stops_the_export_thread(enabled, receiver):
    before = threading.active_count()
    delivery = OtlpMetricDelivery(config(receiver.port))
    assert threading.active_count() == before + 1
    delivery.close()
    delivery.close()
    assert threading.active_count() == before


@pytest.mark.parametrize(
    "candidate",
    [
        "https://127.0.0.1:3000/d/module6-operations",
        "http://localhost:3000/d/module6-operations",
        "http://grafana.example:3000/d/module6-operations",
        "http://127.0.0.1:3000/d/module6-operations?token=private-secret",
        "http://127.0.0.1:3000/d/module6-operations#x",
        "http://admin:admin@127.0.0.1:3000/d/module6-operations",
        "http://127.0.0.1:3000/d/other",
        "http://127.0.0.1:80/d/module6-operations",
        "javascript:alert(1)",
        None,
        3000,
    ],
)
def test_only_the_fixed_loopback_dashboard_reference_is_permitted(candidate):
    with pytest.raises(TelemetryDeliveryError) as error:
        grafana_reference(candidate)
    assert "private-secret" not in str(error.value)
    good = "http://127.0.0.1:3000/d/module6-operations"
    assert grafana_reference(good) == good


def vector(*samples):
    return {
        "status": "success",
        "data": {"resultType": "vector", "result": list(samples)},
    }


def test_metric_responses_are_curated_and_absent_is_not_zero():
    assert prometheus_scalar(vector({"metric": {}, "value": [1.0, "7"]})) == 7.0
    assert prometheus_scalar(vector({"metric": {}, "value": [1.0, "0"]})) == 0.0
    assert prometheus_scalar(vector()) is None


@pytest.mark.parametrize(
    "payload",
    [
        None,
        "7",
        {"status": "error", "error": PRIVATE},
        {"status": "success"},
        {"status": "success", "data": {"resultType": "matrix", "result": []}},
        vector({"metric": {"run_id": PRIVATE}, "value": [1.0, "7"]}),
        vector({"metric": {}, "value": [1.0, "7"]}, {"metric": {}, "value": [1, "8"]}),
        vector({"metric": {}, "value": [1.0, 7]}),
        vector({"metric": {}, "value": [1.0, "NaN"]}),
        vector({"metric": {}, "value": [1.0, "+Inf"]}),
        vector({"metric": {}, "value": [1.0, "-1"]}),
        vector({"metric": {}, "value": [1.0, PRIVATE]}),
        vector({"metric": {}}),
    ],
)
def test_untrusted_metric_responses_are_rejected_without_echo(payload):
    with pytest.raises(TelemetryDeliveryError) as error:
        prometheus_scalar(payload)
    assert "private-secret" not in str(error.value)


def test_operator_command_does_nothing_without_explicit_delivery(monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location(
        "module6_telemetry_command", MODULE / "run_telemetry.py"
    )
    command = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(command)

    def forbidden(*args, **kwargs):
        pytest.fail("Delivery ran without explicit selection")

    monkeypatch.setattr(command, "deliver", forbidden)
    monkeypatch.setattr(command, "verify", forbidden)
    assert command.main([]) == 2
    assert command.main(["--verify", "--runs", "3"]) == 2
    assert "opt-in" in capsys.readouterr().out
    for bad in (["--deliver", "--runs", "33"], ["--deliver", "--otlp-port", "80"]):
        with pytest.raises(SystemExit):
            command.main(bad)


def test_stack_is_pinned_loopback_only_and_minimal():
    compose = (TELEMETRY / "compose.yaml").read_text(encoding="utf-8")
    images = re.findall(r"^\s+image:\s*(\S+)$", compose, re.MULTILINE)
    assert len(images) == 3
    for image in images:
        assert re.fullmatch(r"[a-z/.-]+:v?\d+\.\d+\.\d+(@sha256:[0-9a-f]{64})?", image)
    published = re.findall(r'^\s+- "([^"]*:\d+)"$', compose, re.MULTILINE)
    assert len(published) == 3
    assert all(entry.startswith("127.0.0.1:") for entry in published)
    assert "8889" not in "".join(published)
    lowered = compose.lower()
    for unapproved in ("loki", "tempo", "jaeger", "elasticsearch", "alertmanager"):
        assert unapproved not in lowered
    assert "password" not in lowered.replace("no password exists", "")
    assert lowered.count("mem_limit") == 3 and lowered.count("cpus:") == 3
    assert "retention.time=7d" in compose and "retention.size=256MB" in compose


def test_collection_and_storage_configuration_enforce_bounds():
    collector = (TELEMETRY / "otel-collector.yaml").read_text(encoding="utf-8")
    assert "memory_limiter" in collector and "send_batch_max_size" in collector
    assert 'IsMatch(name, "^module6\\\\.")' in collector
    assert "traces:" not in collector and "logs:\n      receivers" not in collector
    assert "processors: [memory_limiter, filter/module6, batch]" in collector
    prometheus = (TELEMETRY / "prometheus.yaml").read_text(encoding="utf-8")
    keep = re.search(r"regex: (\S+)\n\s+action: labelkeep", prometheus).group(1)
    assert set(keep.split("|")) == {"__name__", "job", "instance", "le"} | LABEL_KEYS
    assert "sample_limit: 1000" in prometheus and "label_limit: 12" in prometheus
    assert "remote_write" not in prometheus and "alertmanagers" not in prometheus


def test_dashboard_and_rules_use_only_implemented_signals_and_labels():
    board = json.loads(
        (TELEMETRY / "grafana" / "dashboards" / "module6-operations.json").read_text(
            encoding="utf-8"
        )
    )
    assert board["uid"] == "module6-operations" and board["editable"] is False
    assert board["refresh"] == "30s" and 1 <= len(board["panels"]) <= 12
    rules = (TELEMETRY / "rules" / "module6.rules.yaml").read_text(encoding="utf-8")
    expressions = [t["expr"] for p in board["panels"] for t in p["targets"]]
    expressions += re.findall(r"module6_\w+(?:\{[^}]*\})?", rules)
    allowed = {
        "module6_workflow_started_total",
        "module6_workflow_finished_total",
        "module6_workflow_active",
        "module6_workflow_duration_milliseconds_bucket",
        "module6_workflow_retries_total",
        "module6_worker_reaped_total",
        "module6_model_calls_total",
        "module6_observation_drops_total",
        "module6_observation_adapter_failures_total",
    }
    for expression in expressions:
        assert set(re.findall(r"module6_\w+", expression)) <= allowed
        selectors = re.findall(r"[{,]\s*(\w+)\s*(?:=~|!=|=)", expression)
        grouped = re.findall(r"by \(([^)]*)\)", expression)
        names = set(selectors) | {n.strip() for g in grouped for n in g.split(",")}
        assert names <= LABEL_KEYS | {"le", "job", "alertname", "alertstate"}
    text = json.dumps(board).lower() + rules.lower()
    for invented in ("token", "cost_usd", "queue_depth", "utilization"):
        assert invented not in text.replace("token usage, cost, queue depth", "")
    assert len(re.findall(r"^\s+- alert: Module6\w+$", rules, re.MULTILINE)) == 3
    for panel in board["panels"]:
        assert panel["datasource"]["uid"] == "module6-prometheus"


def frame(values, labels=None, status=200):
    fields = [{"name": "Time"}, {"name": "Value", "labels": labels or {}}]
    return {
        "results": {
            "A": {
                "status": status,
                "frames": [{"schema": {"fields": fields}, "data": {"values": values}}],
            }
        }
    }


def test_grafana_query_replies_are_curated_and_absent_is_not_zero():
    assert grafana_scalar(frame([[1791830962821], [14]])) == 14.0
    assert grafana_scalar(frame([[1791830962821], [0]])) == 0.0
    assert grafana_scalar(frame([])) is None


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {"results": {}},
        {"results": {"A": {"status": 200, "frames": []}}},
        {"results": {"A": {"status": 500, "error": PRIVATE, "frames": [{}]}}},
        frame([[1], [14]], status=403),
        frame([[1], [14]], labels={"run_id": PRIVATE}),
        frame([[1, 2], [14, 15]]),
        frame([[1], ["14"]]),
        frame([[1], [True]]),
        frame([[1], [-1]]),
        frame([[1], [float("nan")]]),
        frame([[1], [PRIVATE]]),
        frame([[1]]),
    ],
)
def test_untrusted_grafana_replies_are_rejected_without_echo(payload):
    with pytest.raises(TelemetryDeliveryError) as error:
        grafana_scalar(payload)
    assert "private-secret" not in str(error.value)
