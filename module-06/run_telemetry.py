"""Operator command: bounded demonstrations with explicit loopback OTLP delivery.

Nothing is delivered unless ``--deliver`` is given. The destination is always
``127.0.0.1``; only ports are selectable. ``--verify`` additionally reads curated
values back from the local Prometheus and Grafana started by
``telemetry/compose.yaml``. No model, provider or paid call is made.
"""

import argparse
import asyncio
import json
import time
import urllib.parse
import urllib.request

ALERTS = (
    "Module6CollectionBoundaryDown",
    "Module6ObservationLoss",
    "Module6WorkflowFailureRatioHigh",
)
QUERY = "sum(module6_workflow_finished_total)"


def port(text: str) -> int:
    value = int(text)
    if not 1024 <= value <= 65535:
        raise argparse.ArgumentTypeError("port must be 1024 to 65535")
    return value


def run_count(text: str) -> int:
    value = int(text)
    if not 1 <= value <= 32:
        raise argparse.ArgumentTypeError("runs must be 1 to 32")
    return value


def read_json(url: str, body: dict | None = None) -> object:
    """Bounded loopback request ignoring proxy settings; ``None`` if unavailable."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    target = url
    if body is not None:
        target = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
    try:
        with opener.open(target, timeout=5) as response:
            return json.loads(response.read(1_048_576))
    except (OSError, ValueError):
        return None


def deliver(runs: int, otlp_port: int):
    """Run bounded accepted demonstrations through one delivering observer."""
    from multi_agent_orchestration.console import Demonstration, selection
    from multi_agent_orchestration.contracts import (
        ExecutionLimits,
        TaskInput,
        WorkflowRequest,
    )
    from multi_agent_orchestration.errors import RuntimeFoundationError
    from multi_agent_orchestration.observability import Observability
    from multi_agent_orchestration.observed_execution import execute_observed_workflow
    from multi_agent_orchestration.telemetry_delivery import (
        DeliveryConfig,
        OtlpMetricDelivery,
    )

    # The one-step parallel run is denied by the step budget on purpose, so the
    # dashboard shows more than one outcome.
    plan = (
        (Demonstration.FIXTURE, 8),
        (Demonstration.COORDINATOR, 8),
        (Demonstration.SEQUENTIAL, 8),
        (Demonstration.PARALLEL, 8),
        (Demonstration.PARALLEL, 1),
        (Demonstration.HIERARCHICAL, 8),
        (Demonstration.DISTRIBUTED, 8),
    )
    delivery = OtlpMetricDelivery(
        DeliveryConfig(
            mode="loopback-otlp-http",
            endpoint=f"http://127.0.0.1:{otlp_port}/v1/metrics",
        )
    )
    observer = Observability(adapters=(delivery,))
    try:
        for index in range(runs):
            mode, steps = plan[index % len(plan)]
            runtime, topology, distributed = selection(mode)
            request = WorkflowRequest(
                runtime=runtime,
                topology=topology,
                task=TaskInput(instruction="Synthetic telemetry demonstration text."),
                limits=ExecutionLimits(max_steps=steps, timeout_ms=30000),
            )
            try:
                asyncio.run(
                    execute_observed_workflow(
                        request, observer=observer, distributed=distributed
                    )
                )
            except RuntimeFoundationError:
                pass  # Outcome is already counted by the observer.
        accepted = delivery.flush()
    finally:
        delivery.close()
    return observer.metrics, delivery.status, accepted


def stored_total(prometheus_port: int) -> float | None:
    """Curated finished-workflow total from Prometheus; ``None`` if absent."""
    from multi_agent_orchestration.telemetry_delivery import (
        TelemetryDeliveryError,
        prometheus_scalar,
    )

    query = urllib.parse.urlencode({"query": QUERY})
    try:
        return prometheus_scalar(
            read_json(f"http://127.0.0.1:{prometheus_port}/api/v1/query?{query}")
        )
    except TelemetryDeliveryError:
        return None


def verify(expected: int, prometheus_port: int, grafana_port: int) -> bool:
    """Read curated evidence back from local Prometheus and Grafana."""
    from multi_agent_orchestration.telemetry_delivery import (
        DASHBOARD_UID,
        TelemetryDeliveryError,
        grafana_reference,
        grafana_scalar,
    )

    prometheus = f"http://127.0.0.1:{prometheus_port}"
    grafana = f"http://127.0.0.1:{grafana_port}"
    stored = None
    for _ in range(12):  # At most about one minute for collection and scrape.
        stored = stored_total(prometheus_port)
        if stored == expected:
            break
        time.sleep(5)
    shown = "unavailable" if stored is None else stored
    print(f"Prometheus finished-workflow total: {shown}")

    rules = read_json(f"{prometheus}/api/v1/rules")
    try:
        loaded = sorted(
            rule["name"]
            for group in rules["data"]["groups"]
            for rule in group["rules"]
            if rule["name"] in ALERTS
        )
    except (KeyError, TypeError):
        loaded = []
    print(f"Prometheus alert rules loaded: {len(loaded)} of {len(ALERTS)}")

    health = read_json(f"{grafana}/api/health")
    healthy = type(health) is dict and health.get("database") == "ok"
    board = read_json(f"{grafana}/api/dashboards/uid/{DASHBOARD_UID}")
    try:
        provisioned = board["dashboard"]["uid"] == DASHBOARD_UID
    except (KeyError, TypeError):
        provisioned = False
    query = {
        "refId": "A",
        "datasource": {"uid": "module6-prometheus"},
        "expr": QUERY,
        "instant": True,
        "range": False,
    }
    try:
        through = grafana_scalar(
            read_json(
                f"{grafana}/api/ds/query",
                {"queries": [query], "from": "now-5m", "to": "now"},
            )
        )
    except TelemetryDeliveryError:
        through = None
    print(f"Grafana healthy: {healthy}; dashboard provisioned: {provisioned}")
    shown = "unavailable" if through is None else through
    print(f"Grafana datasource query total: {shown}")
    if provisioned:
        print("Dashboard:", grafana_reference(f"{grafana}/d/{DASHBOARD_UID}"))
    return (
        stored == expected
        and loaded == sorted(ALERTS)
        and healthy
        and provisioned
        and through == expected
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--deliver", action="store_true", help="required to export")
    parser.add_argument("--runs", type=run_count, default=7)
    parser.add_argument("--otlp-port", type=port, default=4318)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--prometheus-port", type=port, default=9090)
    parser.add_argument("--grafana-port", type=port, default=3000)
    args = parser.parse_args(argv)
    if not args.deliver:
        print("Nothing ran. Delivery is opt-in: pass --deliver to export metrics.")
        return 2
    if args.verify and stored_total(args.prometheus_port) is not None:
        # Exact verification needs an empty starting point; otherwise series
        # from an earlier process could satisfy the check.
        print(
            "Nothing ran. Earlier Module 6 series are still present. Restart the "
            "collector (docker compose restart otel-collector) and verify again."
        )
        return 1
    metrics, status, accepted = deliver(args.runs, args.otlp_port)
    finished = sum(
        getattr(metrics, name)
        for name in ("completed", "failed", "timed_out", "cancelled", "denied")
    )
    print(
        f"Workflows started: {metrics.started}; finished: {finished}; "
        f"completed: {metrics.completed}; denied: {metrics.denied}"
    )
    print(
        f"Exports accepted: {status.exports_succeeded}; "
        f"failed: {status.exports_failed}; final export accepted: {accepted}"
    )
    if not accepted:
        print("Collection boundary unavailable. Workflow results are unaffected.")
    if args.verify:
        ok = verify(finished, args.prometheus_port, args.grafana_port)
        print("Pipeline verification:", "passed" if ok else "failed")
        return 0 if ok else 1
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
