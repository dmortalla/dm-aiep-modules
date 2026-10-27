# ADR-003: Three-Layer Observability

- Status: Accepted
- Decision authority: Human-approved Architecture B+

## Context

The platform needs reviewer-facing evidence, AI execution tracing, and
cross-run operational observability. These are related but distinct concerns.

## Decision

Use:

- Streamlit for product interaction and curated per-run evidence;
- LangSmith for AI, LLM, and agent execution tracing;
- OpenTelemetry for vendor-neutral operational instrumentation;
- Grafana for cross-run operational dashboards and alerting.

## Responsibility Boundaries

### Streamlit

Answers what happened in this run and what the user should inspect.

### LangSmith

Answers what happened inside AI and agent execution.

### OpenTelemetry

Provides normalized operational instrumentation without coupling application
semantics to a single observability vendor.

### Grafana

Answers how the platform behaves across runs and over time.

## Reliability Rule

Workflow correctness must not depend on Grafana or LangSmith availability.

Observability failure must be visible and bounded without corrupting workflow
semantics.

## Consequence

Streamlit consumes telemetry but does not become the instrumentation source of
truth.
