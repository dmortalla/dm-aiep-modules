# Module 6 - Multi-Agent Systems & Orchestration

A standalone, production-minded study of scalable AI orchestration with
multi-agent architectures: sequential, parallel, hierarchical,
coordinator-worker and distributed patterns on LangGraph, CrewAI and Google ADK,
with cost governance, reliability controls, scaling evidence and layered
observability, presented through one Streamlit reviewer cockpit.

**Status:** the engineering stories are delivered as a local, loopback reviewer
system. [TRACEABILITY.md](docs/TRACEABILITY.md) reconciles all 26 source
requirements as `Verified with limitation` (none unqualified; that
reconciliation is under independent review). Module 6 is not complete: hosted
deployment, human browser acceptance and release are separate, still-open gates,
and this module makes no production-deployment, SLA or hosted-telemetry claim.
Canonical engineering status: [PROJECT_STATUS.md](docs/PROJECT_STATUS.md).

## Start here (reviewers)

```powershell
uv sync --locked --offline
uv run --locked --offline python module-06/run_console.py
```

Open the loopback URL the launcher prints (normally `http://127.0.0.1:8501`).
No credentials are needed. Open the **Guide** tab first, then run a
demonstration on **Deterministic demo**. Nothing runs, queries or delivers until
you select an action. Do not expose this console publicly: it has no
authentication, multi-user support or verified capacity.

To run the tests offline from the repository root:

```powershell
uv run --locked --offline pytest module-06/tests -q
```

## Architecture

Streamlit and the CLI call an application layer that owns workflow contracts,
authority, policy, cost governance, evidence and telemetry semantics.
LangGraph, CrewAI and Google ADK are interchangeable runtime implementations
behind application-owned boundaries; model output is untrusted data and never
grants authority ([ARCHITECTURE.md](docs/ARCHITECTURE.md), ADRs 001-008).

| Capability | Where it is demonstrated |
| --- | --- |
| Sequential, parallel (cap two), hierarchical and coordinator-worker graphs | LangGraph |
| Role-based collaboration with validated task context | CrewAI |
| Delegation and validated hand-offs; one native role per worker process | Google ADK |
| Distributed orchestration across two independent local worker processes | ADK workers, serialized IPC, start barrier, PID and reaping evidence |
| Context passing, task delegation, synchronisation, workflow-scoped shared state | typed immutable contracts revalidated at every hand-off |
| Researcher -> Analyst -> Critic with bounded repair | the canonical workflow (deterministic, synthetic and real-local modes) |
| Scaling | opt-in local benchmark at admission caps 1, 2 and 4 |
| Cost and reliability | per-run budgets, deadlines, cancellation, supervised child processes with kill/reap, fail-closed denial, zero retries by design |

## Reviewer cockpit

One Streamlit app with five tabs; each states its purpose, the action to take,
the expected result and what that result proves.

| Tab | What it shows | Default behaviour |
| --- | --- | --- |
| Deterministic demo | Eight deterministic demonstrations, the synthetic canonical workflow and the local scaling benchmark | Runs only on an explicit action; no keys, model or external delivery |
| Live / BYOK | The canonical workflow with real local Ollama inference for a trusted private operator | Unavailable unless trusted embedding code supplies the runtime; the stock launcher never does |
| Operations | Recorded local OpenTelemetry -> Collector -> Prometheus -> Grafana verification beside an explicit current-host check | Nothing is queried until the check is selected |
| LangSmith tracing | Recorded `service_read` and `unverified_write` deliveries, never merged | The current check reports unavailable: the stock page supplies no read capability |
| Guide | Orientation, evidence labels, observability roles and how to test each capability | Static text |

## Observability

- **AI / agent observability:** LangSmith (specialist agent tracing).
- **Operational observability:** OpenTelemetry -> OTel Collector -> Prometheus ->
  Grafana, a containerized stack under [`telemetry/`](telemetry/). It was
  verified end-to-end **locally** (2026-10-23: 14 of 14 workflows, 3 alert rules
  loaded, dashboard provisioned). The Collector runs a metrics pipeline only;
  traces and logs have no storage backend. It is loopback-only and is not hosted
  telemetry, a public Grafana or Prometheus, or an SLA
  ([OPERATIONAL_TELEMETRY.md](docs/OPERATIONAL_TELEMETRY.md)).
- **Unified reviewer presentation:** the Streamlit cockpit curates both layers
  natively. It never embeds or iframes Grafana, Prometheus or LangSmith.

## Security and authority model

- Demo is deterministic and keyless: the deployed-safe baseline.
- Local Live/BYOK is for a trusted operator only. BYOK means the operator's
  trusted runtime brings its own provider connectivity; there is no key field
  in the UI. Credential presence never authorizes execution.
- Every real run needs a fresh single-use `LiveAuthorization` under the fixed
  ADR-008 NORMAL profile (200,000 ms workflow, 45,000 ms per call, at most 4
  calls and 1 repair, 0 retries, concurrency 1). No approval is remembered and
  reruns never execute.
- Public/deployed live is fail-closed. No deployment-compatible authority
  boundary exists, so a public visitor cannot execute local live mode.
- No automatic LangSmith write and no automatic operational query; external
  writes require separate authority. See [SECURITY.md](docs/SECURITY.md).

Use synthetic text rather than secrets.


## Evidence classifications

Every result and recorded item is labelled by `execution_kind`, `provenance`,
`delivery_confirmation`, `operational_classification` and `source`.

- **Deterministic / synthetic / real-local:** deterministic agents; the
  synthetic canonical workflow (`synthetic_offline`); local model inference
  (`local_provider_execution`).
- **Recorded versus current:** `recorded_historical` curated records never stand
  in for a `fresh_execution`; projections are local and never delivery.
- **Real-local runs:** Run 3 is an `out_of_policy_observation`; Run 4 is an
  authorized current-path real-local verification; Run 5 is exactly "One-run
  live-model current-path LangSmith projection and delivery verification
  (`unverified_write` receipt); authority-consumption status operator-attested
  and not independently confirmed." Four recorded real runs is a floor, not a
  proven total ([CANONICAL_LIVE_WORKFLOW.md](docs/CANONICAL_LIVE_WORKFLOW.md)).
- **LangSmith:** one deterministic delivery was read back (`service_read`); Run 5
  was not (`unverified_write`). Not every live run is delivered or read back.

## Limitations

Local, single-host and deterministic evidence; one benchmark sample on one
workstation; no production load test, capacity, SLA or cloud-scale claim; no
remote-host distribution; no persistent shared memory; model output quality is
not claimed; the live repair path is unexercised. One live-execution timing test
is a known load-sensitive reliability observation under future hardening (see
[PROJECT_STATUS.md](docs/PROJECT_STATUS.md)). Remaining release gates: human
browser acceptance, deployment verification, root README reconciliation,
publication and release.

## Documentation map

[SOURCE_REQUIREMENTS](docs/SOURCE_REQUIREMENTS.md) · [TRACEABILITY](docs/TRACEABILITY.md) ·
[PROJECT_STATUS](docs/PROJECT_STATUS.md) · [ARCHITECTURE](docs/ARCHITECTURE.md) ·
[SECURITY](docs/SECURITY.md) · [COST_GOVERNANCE](docs/COST_GOVERNANCE.md) ·
[OBSERVABILITY](docs/OBSERVABILITY.md) · [OPERATIONS_CONSOLE](docs/OPERATIONS_CONSOLE.md) ·
[Reviewer experience contract](docs/REVIEWER_EXPERIENCE_CONTRACT.md) ·
[SCALING_BENCHMARK](docs/SCALING_BENCHMARK.md) ·
[LANGSMITH_DELIVERY](docs/LANGSMITH_DELIVERY.md). Per-slice records in `docs/`
are dated history; where they say "Planned" or "candidate", the traceability
document and project status supersede them.
