# ADR-001: Provider-Neutral Orchestration Core

- Status: Accepted
- Decision authority: Human-approved Architecture B+

## Context

Module 6 must meaningfully use LangGraph, CrewAI, and Google ADK while
remaining a coherent production-grade system rather than three unrelated demos.

## Decision

Application-owned contracts, workflow semantics, security policy, cost policy,
telemetry semantics, and evidence models remain independent of LangGraph,
CrewAI, and Google ADK.

Required frameworks execute behind explicit runtime boundaries.

## Rationale

This preserves source fidelity while preventing framework lock-in and allows
common security, reliability, cost, and evidence policy to be enforced across
runtime implementations.

## Consequences

- Runtime adapters must conform to application-owned contracts.
- Framework-specific objects must not leak unnecessarily into domain contracts.
- Shared abstractions are extracted only after real duplication is demonstrated.
- Framework replacement must not require redesigning application authority.

## Guardrail

Framework neutrality must not become speculative abstraction. Implement the
smallest boundary required by actual runtime behavior.
