# ADR-005: Streamlit Operations Console

- Status: Accepted
- Decision authority: Human-approved Architecture B+

## Context

Every portfolio module requires a runnable and understandable presentation
layer, while Module 6 also needs visible orchestration evidence.

## Decision

Streamlit is the primary interactive application and reviewer-facing operations
console for Module 6.

It aggregates curated workflow, performance, reliability, security, cost, and
trace evidence while leaving telemetry ownership outside the UI.

## Required User Experience

The interface should explain:

- what workflow or orchestration pattern is being demonstrated;
- what action the user should take;
- what result to expect;
- what engineering property the result demonstrates.

Where relevant, the interface should expose:

- run identifier and status;
- selected runtime and workflow pattern;
- participating agents and delegated tasks;
- workflow transitions;
- latency;
- retries and timeouts;
- model and token usage;
- cost evidence;
- policy and validation events;
- final validated result;
- trace or operations references when available.

## Boundary

Streamlit must not contain core orchestration logic. It invokes application
services and renders validated application-owned results and evidence.

## Rationale

A reviewer should be able to execute and understand the platform from one
coherent interface while engineers retain deeper LangSmith and Grafana
observability surfaces.
