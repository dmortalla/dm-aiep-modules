# Module 6 Cost Governance

## Objective

Cost optimisation is both a source requirement and a production-grade
engineering property.

The default developer, CI, import, startup, and deterministic demonstration
paths must not create billable inference traffic.

## Execution Hierarchy

1. Deterministic fixture.
2. Local or open-weight model where appropriate.
3. Verified free or budget hosted model.
4. Premium hosted model only when justified.

Free provider or model status is never assumed permanent. Pricing and limits
are external evidence and configuration, not architectural constants.

## Required Per-Run Bounds

Every live workflow must support enforceable limits where applicable for:

- model calls;
- input tokens;
- output tokens;
- retries;
- workflow duration;
- parallel agents and tasks;
- delegated tasks;
- estimated or provider-reported monetary cost;
- telemetry volume where practical.

## Authorization Rules

- Credential presence does not authorize spending.
- Live or billable execution must be explicit.
- Automatic premium escalation is forbidden unless active policy explicitly
  permits it within the current budget.
- Budget exhaustion must terminate or safely degrade execution.
- A model or agent cannot increase its own budget.

## Cost Evidence

Normalized per-run evidence should include, when available:

- provider;
- model;
- runtime;
- input tokens;
- output tokens;
- model-call count;
- retry count;
- latency;
- estimated cost;
- provider-reported cost;
- configured budget;
- budget consumed;
- termination reason.

Estimated values must be explicitly labeled as estimates.

## Observability Cost

Observability itself consumes resources and may incur external charges.

The system should support:

- environment-aware tracing;
- sampling where justified;
- bounded telemetry cardinality;
- configurable trace detail;
- no unnecessary remote tracing during deterministic CI;
- environment-appropriate retention.

## Cost Definition of Done

Cost optimisation requires evidence that the platform:

1. measures relevant resource consumption;
2. enforces budgets;
3. runs deterministic tests with zero external inference cost;
4. prevents silent paid escalation;
5. exposes cost evidence through operational surfaces.
