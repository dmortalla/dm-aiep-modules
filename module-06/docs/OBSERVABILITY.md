# Module 6 Observability

## Objective

[Slice 4 live operational metrics candidate](LIVE_METRICS_SLICE_4.md) adds a
separate bounded metric window and explicit one-shot loopback OTLP write.
Offline/test-owned wire evidence is distinct from external pipeline acceptance.

Live foundation extension: [Slice 3 local OTel trace projection](LIVE_OTEL_SLICE_3.md)
documents the candidate post-workflow boundary, SDK correlation, bounded local
collection and deferred live metrics. This is not external delivery acceptance.

Provide correlated application, AI-execution, and operational evidence without
making the presentation layer the telemetry source of truth.

## Observability Layers

| Layer | Primary purpose |
| --- | --- |
| Streamlit | Unified human-facing console aggregating curated platform and per-run evidence |
| LangSmith | AI, LLM, and agent execution tracing and debugging |
| OpenTelemetry | Vendor-neutral operational instrumentation boundary |
| OpenTelemetry Collector or compatible collection boundary | Receive and route telemetry outside domain logic |
| Prometheus | Operational metrics/time-series backend |
| Grafana | Specialist cross-run dashboards, PromQL exploration, and operational alerting |

## Correlation

Every execution should use an application-generated run ID that can correlate,
where supported:

- workflow state;
- runtime events;
- model calls;
- LangSmith traces;
- OpenTelemetry traces, metrics, and logs;
- Grafana views;
- Streamlit run evidence.

## Normalized Event Contract

Initial normalized event fields include:

- run_id;
- timestamp;
- event_type;
- workflow_pattern;
- runtime;
- agent identity or role;
- task_id;
- state_from;
- state_to;
- duration_ms;
- retry_count;
- status;
- provider and model identifier when safe;
- token usage when available;
- cost evidence;
- policy decision;
- validation result;
- error category;
- trace correlation identifier.

Sensitive content and credentials must not be emitted merely for observability.

## Streamlit

Streamlit is the product and reviewer-facing operations console.

It should expose enough curated evidence to execute, understand, and evaluate a
run without requiring a reviewer to inspect source code or open another system.

Streamlit aggregates curated measures, workflow evidence, operational metrics,
health indicators, orchestration state, reliability, cost, and AI trace references
where practical. Application services validate and curate these inputs before
presentation; UI code does not implement domain/orchestration logic.

A reviewer should understand system health, workflow behavior, reliability, and
cost from one interface, with drill-down links to Grafana and LangSmith where
appropriate. Streamlit owns neither instrumentation nor telemetry storage and
does not duplicate every raw Grafana panel or LangSmith trace.

The goal is unified user observation, not unified telemetry storage.

## LangSmith

LangSmith is source-required and must be used meaningfully for AI execution
tracing.

Live remote trace delivery must be distinguished from deterministic adapter or
offline integration evidence.

## OpenTelemetry

OpenTelemetry is the preferred vendor-neutral operational instrumentation
boundary where technically appropriate.

Application semantics must not depend on a specific telemetry backend. Domain
and orchestration code use vendor-neutral instrumentation rather than
Prometheus/Grafana-specific contracts.

## Collection Boundary and Prometheus

The approved operational path is application/workflow instrumentation ->
OpenTelemetry Collector or compatible collection boundary -> Prometheus ->
Grafana. Collection and routing occur outside domain logic; use the smallest
practical boundary for local and future hosted deployment. AI/LLM/agent execution
continues to use LangSmith for specialized tracing and debugging.

Prometheus stores operational metrics/time series. Applicable signals include
workflow throughput, active workflows, success/failure rates, agent/runtime
latency, model-call counts, token usage, estimated cost, retries, timeouts, policy
denials, queue depth, and worker utilization. Queue/worker measures apply only
when those resources actually exist. Do not invent metrics for absent features.

Run IDs, task IDs, trace IDs, free-form errors, prompts, and sensitive payloads
must not become metric labels. Correlate individual executions using validated
workflow evidence and trace references instead. Use allowlisted, bounded label
sets such as runtime, workflow pattern, and status; bound series count and
histogram buckets. Apply the controls in [Security](SECURITY.md) and
[Cost Governance](COST_GOVERNANCE.md).

OpenTelemetry trace/log correlation is instrumentation capability, not a decision
to store traces or logs in Prometheus or add another telemetry backend.

[ADR-006](adr/006-operational-metrics-and-unified-observation.md) records the
human-approved amendment to ADR-003 and ADR-005 without rewriting their history.

## Grafana

Grafana is the specialist cross-run operational analysis surface, providing
dashboards, PromQL exploration, operational alerting, and deeper drill-down than
Streamlit. It does not duplicate LangSmith AI tracing. Per-run cost detail remains
in workflow evidence; Prometheus holds bounded aggregates rather than run-ID labels.

Target operational signals include:

- workflow throughput;
- success and failure rates;
- latency distributions where statistically meaningful;
- retry and timeout rates;
- runtime and provider failures;
- model and token usage;
- cost per run and aggregate spend;
- budget violations;
- policy denials;
- validation failures;
- runtime availability and resource pressure.

## Degraded Operation

Workflow correctness must not depend on Collector/collection-boundary,
Prometheus, Grafana, or LangSmith availability. Bound export queues, retries,
timeouts, and resource use; surface loss or backpressure without retry storms.
Streamlit must label unavailable or stale metrics and trace references rather
than presenting missing telemetry as healthy state.

Observability failure must be surfaced and bounded without corrupting workflow
semantics or silently converting a failed workflow into a successful one.

## Implemented Local Boundary (Partial Evidence)

[Execution Observability](EXECUTION_OBSERVABILITY.md) documents the explicit
application observation service, immutable payload-free contracts, bounded local
LangSmith RunTree and OpenTelemetry span/metric adapters, correlation, accounting
availability, failure isolation and evidence. Accepted execution entry points
remain unchanged. This is actual offline SDK integration and remains the default.
[Operational Telemetry](OPERATIONAL_TELEMETRY.md) adds an explicit, opt-in
loopback OTLP metric delivery adapter and a local Docker Compose stack
(Collector, Prometheus, Grafana, alert rules), verified on one workstation.
Live LangSmith delivery and any hosted or production deployment of the
operational path remain future work.
[Operations Console](OPERATIONS_CONSOLE.md) now presents bounded session-scoped
curated local evidence, freshness and unavailable specialist references through
application services. It does not persist raw telemetry or configure delivery.
All 26 requirements remain Planned.
