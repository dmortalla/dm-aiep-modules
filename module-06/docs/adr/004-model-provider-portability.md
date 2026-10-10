# ADR-004: Model Provider Portability and Cost Routing

- Status: Accepted
- Decision authority: Human-approved Architecture B+

## Context

The orchestration platform should not depend on one model vendor, and normal
development or CI must not create uncontrolled inference cost.

## Decision

The orchestration domain uses a provider-neutral model boundary.

Supported execution classes may include:

1. deterministic fixtures;
2. local or open-weight inference;
3. verified free or budget hosted inference;
4. premium hosted inference.

Actual providers are selected only after compatibility, security, quality,
availability, and cost verification.

OpenCode may be used as an engineering client or agent.

OpenCode Zen or another hosted gateway may be evaluated as a model provider
only when its production API contract, security properties, availability,
terms, and pricing have been verified.

OpenCode itself is not automatically part of the production serving path.

## Cost Routing Rule

Use the least expensive authorized execution class that satisfies the required
capability and quality constraints.

## Hard Guardrails

- Credential presence does not authorize spending.
- No silent premium-provider escalation.
- Agents and models cannot increase their own budget.
- Budget exhaustion must terminate or safely degrade execution.
- Free pricing or quotas are never architectural assumptions.
