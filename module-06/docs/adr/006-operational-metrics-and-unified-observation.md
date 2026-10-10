# ADR-006: Operational Metrics and Unified Curated Observation

- Status: Accepted
- Decision authority: Human-approved bounded amendment supplied in the Module 6 Codex handoff
- Recorded: 2026-10-10
- Amends: ADR-003 and ADR-005 additively; historical accepted records remain intact

## Context

Frozen Architecture B+ already separates application-owned telemetry semantics,
LangSmith AI tracing, Grafana operations, and Streamlit evidence presentation.
The human approved an explicit operational metrics backend and collection
boundary, and a unified curated human-facing observation surface. This does not
reinterpret the authoritative course source or add requirement IDs.

## Decision

Operational application/workflow instrumentation uses OpenTelemetry, then an
OpenTelemetry Collector or compatible collection boundary, then Prometheus for
operational metrics/time series, then Grafana for specialist dashboards, PromQL
exploration, cross-run analysis, operational alerting, and deeper drill-down.
Collection/routing stays outside domain logic. Domain/orchestration contracts
must not couple to Prometheus or Grafana; backend portability is preserved.
Use the smallest practical collection boundary for local and future hosted use.

LangSmith retains specialized AI/LLM/agent execution tracing and debugging.
Operational metrics do not replace or duplicate all LangSmith functionality.

Streamlit is the unified human-facing operations console. Application services
validate and curate workflow evidence, operational measures, health, orchestration
state, reliability, cost, and AI trace references for presentation. Provide safe
Grafana and LangSmith drill-down references where appropriate. A reviewer should
understand important platform state from one interface. Streamlit is not a
telemetry database and must not duplicate every raw specialist panel or trace.
Presentation remains separate from domain/orchestration logic.

The goal is unified user observation, not unified telemetry storage.

## Rationale

An explicit metrics backend clarifies storage and operational ownership while
vendor-neutral instrumentation preserves portability. Curated observation makes
platform behavior understandable without requiring every reviewer to operate
specialist tools. Separate specialist surfaces preserve deeper investigation.

## Alternatives Considered

- Direct OTLP/Grafana without standalone Prometheus: could reduce local components
  where a compatible hosted/backend arrangement exists, but leaves metrics storage
  and service/cost boundaries dependent on that arrangement. The human selected
  explicit Prometheus ownership; this alternative is not the accepted path.
- Application-specific Prometheus instrumentation: less indirection, but couples
  domain logic to a backend and weakens portability.
- Raw Grafana panels and LangSmith traces replicated in Streamlit: duplicates
  specialist functionality and increases UI, query, and maintenance cost.
- Streamlit as unified telemetry storage: conflates presentation and persistence
  and introduces unnecessary responsibility.

## Security and High-Cardinality Controls

Allowlist/redact telemetry before export. Exclude secrets, prompts, sensitive
payloads, user identifiers, and free-form labels from metrics. Run/task/trace IDs
remain in protected evidence/reference channels rather than metric labels.
Bound label sets, series counts, and histogram buckets. Restrict collection,
scrape, query, and admin endpoints; use least privilege, appropriate access and
transport protection, and external secret configuration. Model output cannot
modify collection policy or acquire authority through telemetry. Validate remote
responses and specialist links before display; enforce authorized evidence access.
[Security](../SECURITY.md) defines the associated planned controls.

## Cost and Operational Consequences

Bound CPU, memory, storage, retention, collection/scrape frequency, batches,
export queues, retries, timeouts, console queries, refresh rates, and caches.
Sampling/detail controls apply where appropriate. Local infrastructure consumes
resources; hosted telemetry/storage/egress and remote AI tracing may incur charges.
Credentials alone never authorize paid delivery. CI remains deterministic without
required remote telemetry. Live/billable verification requires explicit approval
and budgets. Label cost estimates and stale/unavailable observations accurately.
[Cost Governance](../COST_GOVERNANCE.md) governs these bounds.

Telemetry failure must not corrupt workflow semantics. Surface bounded loss,
backpressure, and unavailable/stale console data; do not create retry storms.
Prometheus stores metrics, not the OpenTelemetry trace/log streams. AI tracing
continues through LangSmith; no additional trace/log storage is approved.

## Tradeoffs and Evidence

Prometheus and collection add resource/operational ownership and future
configuration work. Curated views can omit specialist detail and can lag; show
observation windows/freshness and provide drill-down references. Portability
requires disciplined application-owned contracts. Future evidence must verify
redaction, cardinality, bounded failure, curated view consistency, resource/cost
bounds, local metrics integration, and separately authorized live trace delivery.
No runtime integration or production readiness is established by this ADR.

## Bounded Scope

Only Module 6 architecture documentation and existing requirement evidence plans
are amended. Architecture B+ runtime ownership, authority, provider portability,
standalone boundary, Python constraints, dependency versions, and all 26 frozen
source IDs remain unchanged. No Modules 1–5 changes, application/Streamlit code,
Python dependencies, Prometheus configuration, Grafana dashboards, Docker or
deployment configuration are authorized here. No Loki, Tempo, Jaeger,
Elasticsearch, Kubernetes, or unrelated observability systems are added.
