# Module 5 — AI Agent Engineering

## Authority

This document transcribes and decomposes the supplied Module 5 course screenshot.

The screenshot is the sole authoritative course source for this module.

Requirements must not be added, removed, replaced, or reinterpreted based on
assumptions about the course or on implementations from other modules.

Module 5 is standalone. Its implementation must not depend on, reuse, modify,
or otherwise alter another module's contents.

Additive engineering enhancements are permitted only when they preserve every
source requirement.

---

## Source Title

**MODULE 5: AI AGENT ENGINEERING [5 Hours]**

## Objective

> Teach engineers how to build autonomous AI systems capable of reasoning and
> tool usage.

---

# Source Requirements

## Topics Covered

### Agent systems

- **M5-T01** — Agent lifecycle
- **M5-T02** — Agent architectures
- **M5-T03** — ReAct framework
- **M5-T04** — Goal-oriented systems
- **M5-T05** — Execution loops

### Tools and execution

- **M5-T06** — Function calling
- **M5-T07** — Tool schemas
- **M5-T08** — Tool orchestration
- **M5-T09** — Dynamic tool selection
- **M5-T10** — Multi-step execution

### Memory and state

- **M5-T11** — Short-term memory
- **M5-T12** — Long-term memory
- **M5-T13** — Episodic memory
- **M5-T14** — State management
- **M5-T15** — Context continuity

### Reliability and safety

- **M5-T16** — Retry strategies
- **M5-T17** — Timeout handling
- **M5-T18** — Failure recovery
- **M5-T19** — Validation
- **M5-T20** — Safe execution patterns

---

## Hands-on Labs

- **M5-L01** — Build tool-using AI agent
- **M5-L02** — Implement memory-enabled workflows
- **M5-L03** — Create multi-step reasoning systems
- **M5-L04** — Build retry/fallback mechanisms

---

## Required Tools

- **M5-R01** — LangChain Agents
- **M5-R02** — OpenAI Function Calling
- **M5-R03** — Anthropic Tool Use
- **M5-R04** — Mem0

Each named tool must receive genuine implementation/runtime evidence.
Installation, documentation, naming, or an unused import alone does not
constitute use.

---

## Deliverables

- **M5-D01** — Autonomous AI agent
- **M5-D02** — Stateful workflow system

---

# Requirement Inventory

| Category | Count |
| --- | ---: |
| Topics | 20 |
| Hands-on labs | 4 |
| Required tools | 4 |
| Deliverables | 2 |
| **Total atomic source requirements** | **30** |

---

# Hard Acceptance Invariants

1. All 30 atomic source requirements must be traceable to implementation and/or
   verification evidence appropriate to the requirement.
2. All four hands-on labs must be implemented.
3. Both explicit deliverables must exist and be demonstrable.
4. LangChain Agents, OpenAI Function Calling, Anthropic Tool Use, and Mem0 must
   all be genuinely exercised.
5. Module 5 must remain standalone and must not import from, depend on, modify,
   or reuse another module's contents.
6. External services, model output, tool output, and other untrusted data must
   not acquire privileged authority merely by being returned to the agent.
7. Additive features must not replace, weaken, omit, or reinterpret source
   requirements.
8. A runnable presentation/UI layer must demonstrate the module without
   replacing its underlying implementation.
9. The UI must contain concise guidance explaining what users should do, what
   result to expect, and what the demonstrated result proves.
10. Claims about live providers or remote systems must match actual verification
    evidence; mocked or deterministic evidence must not be represented as live
    provider evidence.

---

# Source-Faithfulness Boundary

The authoritative source does **not** specify:

- a particular autonomous-agent use case;
- a particular agent architecture beyond covering the named concepts;
- a specific UI framework;
- storage technology for memory;
- a specific retry algorithm;
- a specific fallback ordering;
- deployment infrastructure;
- cloud hosting;
- authentication architecture;
- observability vendor;
- database technology;
- number of agents;
- production deployment requirements.

Those decisions therefore belong to architecture/design and must remain
subordinate to the 30 source requirements above.

---

# Architecture Status

**DESIGNED, APPROVED AND IMPLEMENTED (Stories 1-10 accepted; Story 11
reconciliation complete, awaiting independent acceptance and release
approval).**

When this source contract was first written, the status here was
"NOT YET DESIGNED". The architecture was then designed in `ARCHITECTURE.md`,
mapped to all 30 requirements, and approved and frozen by human review before
Story 1 began.

This source contract is unchanged by implementation. The requirement IDs,
wording and count (30) above are the same as when it was frozen.

Current reconciliation of every requirement against implementation and
verification evidence is in `TRACEABILITY.md`. Story-by-story evidence is in
`VERIFICATION.md`.
