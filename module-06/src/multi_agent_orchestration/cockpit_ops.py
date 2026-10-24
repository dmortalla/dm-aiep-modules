"""Bounded read-only operational observation for the reviewer cockpit (S3).

This application-layer module performs the explicit, reviewer-requested,
single-shot, read-only current-host check of the accepted local
operational stack (Prometheus query/rules; Grafana health, dashboard
provisioning and data source query). It reuses the accepted telemetry
curators so untrusted responses are validated before any value is shown.

Policy, all encoded here and therefore testable:

- no request occurs on import, construction, property access or rendering;
  the only effectful function is ``query_local_stack``, which the cockpit
  calls from an explicit reviewer action;
- endpoints are fixed application-owned constants on ``127.0.0.1`` (the
  loopback of the current running host — a deployed Streamlit host, never
  a visitor's machine); no caller can supply a URL, host, port or query, so
  there is no SSRF surface and no arbitrary PromQL;
- one attempt per query call, bounded timeouts, bounded response reads,
  no retries, no polling, no background refresh;
- malformed or failed responses produce truthful ``None`` fields and an
  ``unavailable`` state; values are never fabricated and recorded
  historical evidence is never substituted for a fresh observation.
"""

import json
import urllib.parse
import urllib.request
from typing import Annotated, Literal, Protocol

from pydantic import Field

from .cockpit_view import OperationsState
from .contracts import Contract

HOST = "127.0.0.1"
PROMETHEUS_PORT = 9090
GRAFANA_PORT = 3000
MODULE6_FINISHED_QUERY = "sum(module6_workflow_finished_total)"
ALERT_RULE_NAMES = (
    "Module6CollectionBoundaryDown",
    "Module6ObservationLoss",
    "Module6WorkflowFailureRatioHigh",
)
QUERY_TIMEOUT_S = 5
MAX_RESPONSE_BYTES = 1_048_576


class StackReader(Protocol):
    """Bounded read-only fetcher boundary; the cockpit only injects test fakes.

    Implementations receive only URLs built from this module's fixed internal
    constants; no proxies, credentials, retries or background refresh.
    """

    def __call__(self, url: str, body: dict | None = None) -> object:
        """Fetch one bounded read-only JSON document; raise on failure."""


class LocalStackObservation(Contract):
    """One fresh bounded read-only current-host operational observation.

    Attributes:
        query_state: ``result`` when the check ran, ``unavailable`` when the
            stack could not be read; never the recorded historical state.
        finished_total: Curated finished-workflow total, or ``None`` when
            absent/unleasable — never fabricated as zero.
        alert_rules_loaded: Number of accepted alert rules loaded.
        grafana_healthy: Grafana health fact, or ``None`` unknown.
        dashboard_provisioned: Dashboard provisioning fact, or ``None``.
        dashboard_reference: The validated loopback dashboard reference for
            the current host, rendered inertly; never a fabricated link.
    """

    query_state: Literal[OperationsState.RESULT, OperationsState.UNAVAILABLE]
    finished_total: float | None = None
    alert_rules_loaded: int | None = None
    grafana_healthy: bool | None = None
    dashboard_provisioned: bool | None = None
    dashboard_reference: (
        Annotated[str, Field(strict=True, min_length=1, max_length=256)] | None
    ) = None


class StoredOperationsObservation(Contract):
    """Presentation-scoped result of one explicit operational check.

    Stored by the application session after the reviewer's explicit action;
    re-rendering never re-queries. Session state never authorizes anything.

    Attributes:
        happened_ns: Wall-clock freshness marker of the check, in nanoseconds.
        observation: The validated fresh observation, or ``None`` when the
            check itself failed at the presentation boundary.
    """

    happened_ns: int
    observation: LocalStackObservation | None


def _production_reader(url: str, body: dict | None = None) -> object:
    """Bounded loopback GET/POST ignoring proxies; raises on failure."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    target = url
    data = None
    if body is not None:
        data = json.dumps(body).encode()
    request = urllib.request.Request(
        target,
        data=data,
        headers={"Content-Type": "application/json"} if body else {},
    )
    with opener.open(request, timeout=QUERY_TIMEOUT_S) as response:
        return json.loads(response.read(MAX_RESPONSE_BYTES))


def query_local_stack(
    reader: StackReader = _production_reader,
) -> LocalStackObservation:
    """Perform one bounded read-only current-host operational check.

    Exactly one attempt per call: five read-only requests against the fixed
    loopback endpoints (Prometheus instant query and rules; Grafana health,
    dashboard and data source query). No retries, no polling, no background
    refresh; failures do not raise and never fabricate values.

    Args:
        reader: Optional bounded fetcher injection for deterministic tests.
            Production callers never pass one. The fetcher receives only
            URLs built from fixed internal constants.

    Returns:
        A validated fresh observation; every unreadable fact stays ``None``
        and the state reflects truth.

    Raises:
        Never; all expected failures are represented in the result.
    """
    from .telemetry_delivery import (
        DASHBOARD_UID,
        TelemetryDeliveryError,
        grafana_reference,
        grafana_scalar,
        prometheus_scalar,
    )

    prometheus = f"http://{HOST}:{PROMETHEUS_PORT}"
    grafana = f"http://{HOST}:{GRAFANA_PORT}"
    finished = None
    rules_loaded = None
    healthy = None
    provisioned = None
    reference = None

    query = urllib.parse.urlencode({"query": MODULE6_FINISHED_QUERY})
    try:
        finished = prometheus_scalar(
            reader(f"{prometheus}/api/v1/query?{query}", None)
        )
    except (TelemetryDeliveryError, OSError, ValueError, TypeError):
        finished = None
    try:
        rules = reader(f"{prometheus}/api/v1/rules", None)
        rules_loaded = len(
            {
                rule["name"]
                for group in rules["data"]["groups"]
                for rule in group["rules"]
                if rule["name"] in ALERT_RULE_NAMES
            }
        )
    except (OSError, ValueError, TypeError, KeyError, IndexError):
        rules_loaded = None
    try:
        health = reader(f"{grafana}/api/health", None)
        if type(health) is dict:
            healthy = health.get("database") == "ok"
    except (OSError, ValueError, AttributeError):
        healthy = None
    try:
        board = reader(f"{grafana}/api/dashboards/uid/{DASHBOARD_UID}", None)
        provisioned = board["dashboard"]["uid"] == DASHBOARD_UID
    except (OSError, ValueError, TypeError, KeyError):
        provisioned = None
    try:
        expected = {
            "refId": "A",
            "datasource": {"uid": "module6-prometheus"},
            "expr": MODULE6_FINISHED_QUERY,
            "instant": True,
            "range": False,
        }
        through = grafana_scalar(
            reader(
                f"{grafana}/api/ds/query",
                {"queries": [expected], "from": "now-5m", "to": "now"},
            )
        )
    except (TelemetryDeliveryError, OSError, ValueError, TypeError):
        through = None

    if finished is None and rules_loaded is None and healthy is None \
            and provisioned is None and through is None:
        return LocalStackObservation(query_state=OperationsState.UNAVAILABLE)
    try:
        reference = grafana_reference(f"{grafana}/d/{DASHBOARD_UID}")
    except TelemetryDeliveryError:
        reference = None
    return LocalStackObservation(
        query_state=OperationsState.RESULT,
        finished_total=finished,
        alert_rules_loaded=rules_loaded,
        grafana_healthy=healthy,
        dashboard_provisioned=provisioned,
        dashboard_reference=reference,
    )
