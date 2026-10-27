# Module 6 — Multi-Agent Systems & Orchestration

![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)
![pytest](https://img.shields.io/badge/tests-pytest-brightgreen)
![Ruff](https://img.shields.io/badge/code%20quality-Ruff-brightgreen)
![Pydantic](https://img.shields.io/badge/validation-Pydantic-blueviolet)
![LangGraph](https://img.shields.io/badge/orchestration-LangGraph-1C3C3C)
![CrewAI](https://img.shields.io/badge/orchestration-CrewAI-FF5A50)
![Google ADK](https://img.shields.io/badge/orchestration-Google%20ADK-4285F4)
![LangSmith](https://img.shields.io/badge/AI%20tracing-LangSmith-1C3C3C)
![OpenTelemetry](https://img.shields.io/badge/telemetry-OpenTelemetry-425CC7)
![Prometheus](https://img.shields.io/badge/metrics-Prometheus-E6522C)
![Grafana](https://img.shields.io/badge/dashboards-Grafana-F46800)
![Ollama](https://img.shields.io/badge/local%20inference-Ollama-lightgrey)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B)

A standalone, production-grade study of scalable AI orchestration with
multi-agent architectures: sequential, parallel, hierarchical,
coordinator-worker and distributed patterns on LangGraph, CrewAI and Google ADK,
with cost governance, reliability controls, scaling evidence and layered
observability, presented through one Streamlit reviewer cockpit.

## Executive overview

Module 6 keeps workflow contracts, authority, policy, cost governance, evidence
and telemetry semantics in the application, and treats the three agent runtimes
as interchangeable implementations behind those boundaries. Every result carries
an explicit evidence class, so deterministic, synthetic, real-local, recorded and
current evidence are never blurred.

## Status and reviewer start-here

Module 6 engineering is independently reviewed and accepted, and the committed
candidate (`3e2ed63e8621d3fc0d3760f763fb920f3c6c8ada`) passed local human browser
acceptance. That browser acceptance is a recorded human decision made after the
engineering candidate was committed and reviewed; the detailed engineering
history in [PROJECT_STATUS.md](docs/PROJECT_STATUS.md) has not yet been reconciled
for the final release closeout and still records the earlier pre-closeout state,
so it is not the current status source. [TRACEABILITY.md](docs/TRACEABILITY.md)
reconciles all 26 source requirements as `Verified with limitation` (none
unqualified). Module 6 is delivered as a local, loopback reviewer system. Public
Streamlit deployment verification and the final release closeout are still
pending, so Module 6 is not described as publicly deployed or released, and it
makes no production-deployment, SLA or hosted-telemetry claim.

**Start here:** run the cockpit (see [Run](#run-and-reviewer-instructions)), open
the **Guide** tab first, then run a demonstration on **Deterministic Demo**.

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

## Key capabilities: the reviewer cockpit

One Streamlit app with six tabs; the Guide opens first. The workflow tabs each
state their purpose, the action to take, the expected result and what that
result proves.

| Tab | What it shows | Default behaviour |
| --- | --- | --- |
| Guide | Orientation, evidence labels, observability roles, how to explore and how to test each capability | Static text; runs nothing |
| Deterministic Demo | Eight deterministic demonstrations, the synthetic canonical workflow and the local scaling benchmark | Runs only on an explicit action; no keys, model or external delivery |
| Live / BYOK | The canonical workflow with real local Ollama inference for a trusted private operator | Unavailable unless trusted embedding code supplies the runtime; the stock launcher never does |
| Operations | Recorded local OpenTelemetry -> Collector -> Prometheus -> Grafana verification beside an explicit current-host check | Nothing is queried until the check is selected |
| LangSmith Tracing | Recorded `service_read` and `unverified_write` deliveries, never merged | The current check reports unavailable: the stock page supplies no read capability |
| Implementation Evidence | Curated, abridged source excerpts for LangGraph, CrewAI, Google ADK, LangSmith and the OpenTelemetry delivery boundary, each naming its file and function | Static; shows implementation structure only, never delivery, runtime state or current service availability |

A trusted operator on their own machine can reach the Live / BYOK action through
the separate private-local launcher, `module-06/run_local_live.py`, which serves
`private_local_app.py` on loopback and supplies the application-owned runtime
only while rendering. The stock launcher and any deployed app never do, and the
launcher grants no authority: each live run still needs explicit operator action
and a fresh bounded authorization.

The only unsafe-HTML surface in the app is one static, application-owned CSS
block for styling. No workflow, model, user, tool or provider value can flow
into it, and there is no iframe, component or link surface.

## Production-grade engineering

- **Cost and reliability:** per-run budgets, deadlines, cancellation, supervised
  child processes with kill/reap, fail-closed denial, and zero retries by design
  ([COST_GOVERNANCE.md](docs/COST_GOVERNANCE.md)).
- **Observability:**
  - AI / agent observability: LangSmith (specialist agent tracing).
  - Operational observability: OpenTelemetry -> OTel Collector -> Prometheus ->
    Grafana, a containerized stack under [`telemetry/`](telemetry/). It was
    verified end-to-end **locally** (2026-10-23: 14 of 14 workflows, 3 alert
    rules loaded, dashboard provisioned). The Collector runs a metrics pipeline
    only; traces and logs have no storage backend. It is loopback-only and is not
    hosted telemetry, a public Grafana or Prometheus, or an SLA
    ([OPERATIONAL_TELEMETRY.md](docs/OPERATIONAL_TELEMETRY.md)).
  - Unified reviewer presentation: the Streamlit cockpit curates both layers
    natively. It never embeds or iframes Grafana, Prometheus or LangSmith.

## Security and trust boundaries

- Demo is deterministic and keyless: the deployed-safe baseline.
- Local Live/BYOK is for a trusted operator only. BYOK means the operator's
  trusted runtime brings its own provider connectivity; there is no key field
  in the UI. Local Ollama inference does not itself require a credential;
  where a provider does, that runtime holds it. Credential presence never
  authorizes execution.
- Every real run needs a fresh single-use `LiveAuthorization` under the fixed
  ADR-008 NORMAL profile (200,000 ms workflow, 45,000 ms per call, at most 4
  calls and 1 repair, 0 retries, concurrency 1). No approval is remembered and
  reruns never execute.
- Public/deployed live is fail-closed. No deployment-compatible authority
  boundary exists, so a public visitor cannot execute local live mode.
- No automatic LangSmith write and no automatic operational query; external
  writes require separate authority. See [SECURITY.md](docs/SECURITY.md).

## Verification and evidence

The Module 6 suite is run offline (see [Run](#run-and-reviewer-instructions)).
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

## Limitations and evidence boundaries

Local, single-host and deterministic evidence; one benchmark sample on one
workstation; no production load test, capacity, SLA or cloud-scale claim; no
remote-host distribution; no persistent shared memory; model output quality is
not claimed; the live repair path is unexercised. One live-execution timing test
is a known load-sensitive reliability observation under future hardening (see the
detailed engineering history, [PROJECT_STATUS.md](docs/PROJECT_STATUS.md)). Remaining release gates: public

## Run and reviewer instructions

```powershell
uv sync --locked --offline
uv run --locked --offline python module-06/run_console.py
```

Open the loopback URL the launcher prints (normally `http://127.0.0.1:8501`).
The Demo needs no credentials. Open the **Guide** tab first, then run a
demonstration on **Deterministic Demo**. Nothing runs, queries or delivers until
you select an action. Use synthetic text rather than secrets. Do not expose this
console publicly: it has no authentication, multi-user support or verified
capacity.

To run the tests offline from the repository root:

```powershell
uv run --locked --offline pytest module-06/tests -q
```

## Documentation

[SOURCE_REQUIREMENTS](docs/SOURCE_REQUIREMENTS.md) · [TRACEABILITY](docs/TRACEABILITY.md) ·
[Detailed engineering history](docs/PROJECT_STATUS.md) · [ARCHITECTURE](docs/ARCHITECTURE.md) ·
[SECURITY](docs/SECURITY.md) · [COST_GOVERNANCE](docs/COST_GOVERNANCE.md) ·
[OBSERVABILITY](docs/OBSERVABILITY.md) · [OPERATIONS_CONSOLE](docs/OPERATIONS_CONSOLE.md) ·
[Reviewer experience contract](docs/REVIEWER_EXPERIENCE_CONTRACT.md) ·
[SCALING_BENCHMARK](docs/SCALING_BENCHMARK.md) ·
[LANGSMITH_DELIVERY](docs/LANGSMITH_DELIVERY.md) ·
[Portfolio README](../README.md). Per-slice records in `docs/` are dated history;
where they say "Planned" or "candidate", the traceability document supersedes
them for requirement status.

---

Developed from Techademy AI Engineering program requirements. Independent
implementation and engineering enhancements.
