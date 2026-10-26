# Module 6 operations console

Run from the repository root after synchronizing the accepted environment:

```powershell
uv sync --locked --offline
uv run --locked --offline python module-06/run_console.py
```

Open the loopback URL the launcher prints, normally `http://127.0.0.1:8501`. The
launcher binds to loopback, disables Streamlit usage analytics and automatic
browser launch, suppresses detailed browser exception output and limits
WebSocket messages to 1 MB. No credentials are needed. Do not expose this review console
publicly; authentication, multi-user deployment and aggregate capacity are not
implemented or verified.

## Reviewer cockpit at a glance

The page is one reviewer cockpit with five tabs; each tab states its purpose,
the action to take, the expected result and what that result proves. Start with
**Guide**, then **Deterministic demo**.

| Tab | What it shows | Default behaviour |
| --- | --- | --- |
| Deterministic demo | Eight deterministic multi-agent demonstrations, the synthetic canonical workflow and the local scaling benchmark | Runs only on an explicit action; no keys, model or external delivery |
| Live / BYOK | The canonical workflow with real local Ollama inference for a trusted private operator | Unavailable unless trusted embedding code supplies the runtime; the stock launcher never does |
| Operations | Recorded local OpenTelemetry → Collector → Prometheus → Grafana verification beside an explicit current-host check | Nothing is queried until the check is selected |
| LangSmith tracing | Recorded `service_read` and `unverified_write` deliveries, never merged | The current check reports unavailable: this page supplies no read capability |
| Guide | Orientation, evidence labels, observability roles and how to test each capability | Static text only |

Observability is presented in three layers: LangSmith for AI/agent tracing;
OpenTelemetry → Collector → Prometheus → Grafana for operational metrics,
verified end-to-end locally (not hosted); and this Streamlit cockpit as the
unified reviewer view. No external service is embedded in the page.

Choose one of the eight demonstrations explicitly, enter synthetic text and
select **Run demonstration**. The page explains what each run proves and how to
try bounded failures. Start with eight steps and a 30,000 ms deadline. Text over
4,096 characters, steps outside 1–32 and deadlines outside 1–30,000 ms are
rejected by the application service on submit; nothing is adjusted or run. Fixture,
all four LangGraph choices, CrewAI collaboration, Google ADK orchestration and
real local two-process ADK distribution use their accepted services unchanged.

Results show validated application evidence, local trace references, role
provenance, workflow latency and available call counters. Tokens, monetary cost,
provider billing and remote observability are labeled unavailable. No live
model/provider calls, paid execution or remote telemetry delivery is enabled.

Recent results are limited to eight temporary views in each browser session.
Clearing results removes those views. Refreshing or selecting controls does not
execute; successful and failed runs remain distinct. Input text is not copied
into result history or telemetry. Use synthetic text rather than secrets.

[Console design and verification](docs/OPERATIONS_CONSOLE.md) records security,
scope, acceptance evidence and limitations. The console does not complete the
module or its requirements; all 26 source requirements remain Planned.

[Local-model provider adapter](docs/LOCAL_MODEL_ADAPTER.md) documents the additive
offline implementation candidate and synthetic process-runtime verification.
One separately authorized post-repair real Ollama response was verified at the
accepted adapter baseline; this does not verify the three-role workflow. The
console still offers the eight deterministic demonstrations plus the synthetic
canonical live workflow demonstration; no real canonical live control is added.

[Canonical live workflow candidate](docs/CANONICAL_LIVE_WORKFLOW.md) documents the
application API for Researcher → Analyst → Critic and its synthetic offline
verification. Real canonical execution requires independent offline acceptance
and fresh human HITL; no live console control is added. The first authorized
live run failed closed at the Researcher (malformed output after one repair).
After the structured-output remediation, a second authorized run completed one
bounded real Researcher → Analyst → Critic execution (3 calls, 0 repairs,
0 retries). Its Analyst assessment reached the 400-character maximum and
appeared incomplete (cause unproven), so an offline prose-completeness candidate
follows; that candidate is exercised by the third run but its acceptance is a
separate review decision. A third run completed the workflow (3 calls,
0 repairs, 64,531 ms) on schema-valid 300,000/120,000 ms bounds whose human
authorization is not established by accepted evidence; it is retained as a
factual timing observation only and is classified permanently out-of-policy
per [ADR-008](docs/adr/008-real-local-canonical-budget-profile.md), whose
named `NORMAL_REAL_LOCAL_BUDGET` profile (200,000 ms workflow / 45,000 ms
per call, 4,096/4,096/16,000 content ceilings) is policy data that
authorizes nothing; every real run still needs fresh explicit HITL. A fourth,
explicitly authorized run verified the NORMAL path (48,407 ms). A fifth
recorded run took a live-model trace through the committed live-family
LangSmith projection and delivery (`unverified_write` only; no service-read
confirmation; authority-consumption operator-attested and not independently
confirmed — see docs/CANONICAL_LIVE_WORKFLOW.md), so four recorded real runs
is a floor, not a proven total.

The observability side is verified end-to-end locally too: one authorized
deterministic run delivered application telemetry through OTLP/HTTP loopback
into an OpenTelemetry Collector, Prometheus (storage, 3 loaded alert rules)
and a provisioned Grafana dashboard, with the pipeline verification passing
([details](docs/OPERATIONAL_TELEMETRY.md)). This is local verification of a
loopback-only stack, not hosted or production observability.

The console also has a separate **canonical live workflow (synthetic)**
demonstration: it runs the accepted canonical workflow through the supervised
live process path with a fixed module-level synthetic gateway, so no real
provider connection, credential or delivery occurs. Receipts stay classified
synthetic offline, role content is labeled unverified model-shaped synthetic
text, and the page presents validated accounting, local observation and
post-run projection statuses without any delivery or export.
