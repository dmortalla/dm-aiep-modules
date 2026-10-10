# ADR-002: Runtime Responsibilities

- Status: Accepted
- Decision authority: Human-approved Architecture B+

## Context

The source requires CrewAI, LangGraph, and Google ADK. Installing all three
without giving each a meaningful system responsibility would not satisfy the
engineering or source-faithfulness objective.

## Decision

- LangGraph is the primary stateful coordinator-worker runtime.
- CrewAI is the primary collaborative role-based agent runtime.
- Google ADK is the primary distributed-orchestration lab/runtime.
- All runtime output crosses application-owned validation and policy boundaries
  before becoming trusted application state.

## LangGraph Responsibilities

- sequential workflows;
- parallel fan-out and fan-in;
- hierarchical routing;
- coordinator-worker execution;
- typed workflow state;
- bounded transitions and execution.

## CrewAI Responsibilities

- collaborative specialist roles;
- collaborative AI system lab;
- task collaboration;
- collaborative result exchange.

## Google ADK Responsibilities

- distributed-orchestration lab;
- ADK-native delegation;
- distributed-processing evidence where technically justified.

## Evidence Rule

Simulated distribution must never be represented as genuine distributed
execution. Evidence must describe the execution mode actually demonstrated.
