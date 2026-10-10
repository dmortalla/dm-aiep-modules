# Module 6 Architecture

## Status

**Architecture B+ - APPROVED AND FROZEN**

The human-approved additive observability amendment is recorded in
[ADR-006](adr/006-operational-metrics-and-unified-observation.md). All other
B+ decisions remain unchanged; historical ADRs retain the original decisions.

Material changes to trust boundaries, source coverage, runtime ownership,
security posture, or cost exposure require explicit human review and an ADR.

## Goal

Build a production-grade, provider-neutral multi-agent orchestration platform.

The application owns its workflow semantics, contracts, policy, security,
cost governance, evidence model, and telemetry semantics.

LangGraph, CrewAI, and Google ADK are runtime implementations behind
application-owned boundaries.

## Core Principle

> Frameworks are implementation mechanisms. Application contracts, authority,
> policy, workflow semantics, evidence, and cost controls belong to the application.

## B+ Platform Architecture

```mermaid
flowchart TD
    U[User] --> UI[Streamlit / API]
    UI --> APP[Application Layer]
    APP --> ORCH[Orchestration Service]
    ORCH --> DOMAIN[Workflow Domain]
    ORCH --> POLICY[Policy / Security]
    ORCH --> OBS[Observability]
    DOMAIN --> RI[Runtime Interface]
    POLICY --> RI
    OBS --> RI
    RI --> LG[LangGraph Runtime]
    RI --> CR[CrewAI Runtime]
    RI --> ADK[Google ADK Runtime]
    LG --> VE[Validated Evidence]
    CR --> VE
    ADK --> VE
    VE --> TE[Telemetry / Events]
    VE --> RESULT[Validated Workflow Result]
    TE --> LS[LangSmith]
    TE --> OTEL[OpenTelemetry]
    OTEL --> COL[OpenTelemetry Collector / Compatible Collection Boundary]
    COL --> PM[Prometheus Operational Metrics]
    PM --> GF[Grafana Specialist Dashboards / Alerting]
    RESULT --> ST[Streamlit Unified Curated Operations Console]
    TE --> CE[Curated Validated Workflow Evidence]
    CE --> ST
    PM --> CM[Curated Operational Measures via Application Services]
    CM --> ST
    GF -. Drill-down reference .-> ST
    LS -. AI trace reference .-> ST
```

## Reference Collaborative Workflow

```mermaid
flowchart TD
    WR[Workflow Request] --> C[Coordinator]
    C --> R[Researcher]
    C --> A[Analyst]
    C --> K[Critic]
    R --> S[Shared Workflow State]
    A --> S
    K --> S
    S --> Y[Synthesizer]
    Y --> V[Validation Boundary]
    V --> F[Validated Final Result]
```

## Runtime Responsibilities

### LangGraph

Primary runtime for stateful coordinator-worker workflows, sequential execution,
parallel fan-out/fan-in, hierarchical routing, workflow state, conditional
transitions, and bounded execution.

### CrewAI

Primary runtime for collaborative role-based agents, the collaborative AI lab,
specialist task collaboration, and collaborative task/result exchange.

### Google ADK

Primary runtime for the distributed-orchestration lab, ADK-native multi-agent
delegation, and distributed-processing evidence where technically justified.

Genuine distribution must be distinguished from simulation.

### LangSmith

Required AI execution observability for agent/LLM traces, model-call evidence,
runtime debugging, and trace correlation.

LangSmith does not own application telemetry semantics.

## Three-Layer Observability

### Streamlit

Unified human-facing operations console and primary interactive product.
Aggregates curated workflow evidence, operational metrics, health, orchestration
state, reliability, cost, and AI trace references through application services.
Grafana and LangSmith links support specialist investigation. The goal is unified
user observation, not unified telemetry storage; Streamlit is not a telemetry
database and does not duplicate every specialist panel or trace. Presentation
remains separate from domain/orchestration logic.

### LangSmith

Answers: What happened inside the AI/agent execution?

### Grafana

Answers: How is the production system behaving across executions and over time?

### OpenTelemetry

Preferred vendor-neutral operational instrumentation boundary.

Domain/orchestration code must not couple to Prometheus or Grafana.

### Collection Boundary and Prometheus

OpenTelemetry instrumentation routes operational telemetry through an
OpenTelemetry Collector or compatible collection boundary outside domain logic.
Prometheus is the operational metrics/time-series backend; Grafana uses it for
specialist cross-run dashboards, PromQL exploration, alerting, and deeper drill-down.
The collection boundary must keep local and future hosted deployment practical
without unnecessary infrastructure. Backend replacement must not change workflow
semantics. This metrics path does not imply additional trace or log storage.

## Model Gateway

```mermaid
flowchart TD
    R[Agent Runtimes] --> M[Provider-Neutral Model Gateway]
    M --> F[Deterministic Fixture]
    M --> L[Local / Open-Weight]
    M --> B[Budget Hosted Provider]
    M --> P[Premium Hosted Provider]
```

Selection is governed by capability, security, quality, availability, and cost.

OpenCode may be used as an engineering agent/client. A hosted gateway such as
OpenCode Zen may be evaluated only after its production API contract, security,
terms, availability, and pricing are verified.

OpenCode itself is not automatically part of the production serving path.

## Execution Modes

1. Deterministic fixture - zero billable calls, CI-safe, reproducible.
2. Local/open-weight - optional, no external inference charge.
3. Budget hosted - explicitly authorized and budget bounded.
4. Premium hosted - explicitly authorized and used only when justified.

Credential presence alone must never authorize paid execution.

## Standalone Boundary

Module 6 must not import application code from Modules 1-5.

## Architecture Freeze

- avoid unnecessary structural refactoring;
- change architecture only for a demonstrated design problem;
- implement incrementally;
- observe real duplication before extracting shared runtime utilities;
- preserve source faithfulness, security, reliability, cost efficiency, and
  defensible evidence as hard invariants.
