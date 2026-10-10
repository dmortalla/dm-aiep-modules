# Module 6 Observability

## Objective

Provide correlated application, AI-execution, and operational evidence without
making the presentation layer the telemetry source of truth.

## Observability Layers

| Layer | Primary purpose |
| --- | --- |
| Streamlit | User interaction and curated per-run engineering evidence |
| LangSmith | AI, LLM, and agent execution tracing and debugging |
| OpenTelemetry | Vendor-neutral operational instrumentation boundary |
| Grafana | Cross-run operational dashboards and alerting |

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

Streamlit consumes normalized telemetry. It does not own instrumentation.

## LangSmith

LangSmith is source-required and must be used meaningfully for AI execution
tracing.

Live remote trace delivery must be distinguished from deterministic adapter or
offline integration evidence.

## OpenTelemetry

OpenTelemetry is the preferred vendor-neutral operational instrumentation
boundary where technically appropriate.

Application semantics must not depend on a specific telemetry backend.

## Grafana

Grafana is the cross-run production operations surface.

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

Workflow correctness must not depend on Grafana or LangSmith availability.

Observability failure must be surfaced and bounded without corrupting workflow
semantics or silently converting a failed workflow into a successful one.
