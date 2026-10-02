# Module 2 Source Requirements

## Source Authority

This document records the requirements extracted from the authoritative
AI Engineering Program Module 2 source supplied by the user.

The source material is authoritative. Implementation choices may extend these
requirements, but must not silently replace, omit, or reinterpret them.

Any necessary deviation requires explicit human approval.

## Module Identity

**Module:** 2  
**Title:** Prompt Engineering & Structured Output Systems

## Objective

Teach engineers how to design reliable and controllable LLM interaction
systems.

## Source Requirements

### Prompt Engineering

| ID | Requirement | Required Evidence | Status |
| --- | --- | --- | --- |
| M2-PE-01 | Demonstrate prompt anatomy | Implementation + tests + runnable demonstration | Pending |
| M2-PE-02 | Demonstrate instruction hierarchy | Implementation + tests + runnable demonstration | Pending |
| M2-PE-03 | Demonstrate context engineering | Implementation + tests + runnable demonstration | Pending |
| M2-PE-04 | Demonstrate role prompting | Implementation + tests + runnable demonstration | Pending |
| M2-PE-05 | Demonstrate few-shot prompting | Implementation + tests + runnable demonstration | Pending |
| M2-PE-06 | Demonstrate chain-of-thought prompting concepts | Implementation + tests/demo appropriate to the technique | Pending |
| M2-PE-07 | Demonstrate tree-of-thought prompting concepts | Implementation + tests/demo appropriate to the technique | Pending |
| M2-PE-08 | Demonstrate self-consistency prompting | Implementation + tests + runnable demonstration | Pending |
| M2-PE-09 | Demonstrate ReAct prompting | Implementation + tests + runnable demonstration | Pending |

### Structured Output Systems

| ID | Requirement | Required Evidence | Status |
| --- | --- | --- | --- |
| M2-SO-01 | Enforce JSON schemas | Implementation + tests | Pending |
| M2-SO-02 | Implement typed outputs | Implementation + tests | Pending |
| M2-SO-03 | Integrate Pydantic for structured output models and validation | Implementation + tests | Pending |
| M2-SO-04 | Validate model outputs | Implementation + tests + failure-path evidence | Pending |

### Safety and Adversarial Testing

| ID | Requirement | Required Evidence | Status |
| --- | --- | --- | --- |
| M2-SA-01 | Implement or demonstrate prompt-injection defense | Implementation + adversarial tests | Pending |
| M2-SA-02 | Implement or demonstrate jailbreak detection | Implementation + adversarial tests | Pending |
| M2-SA-03 | Establish safety boundaries | Implementation/policy + tests | Pending |
| M2-SA-04 | Perform red-team testing | Repeatable adversarial evaluation evidence | Pending |

## Hands-On Labs

| ID | Source Lab | Required Evidence | Status |
| --- | --- | --- | --- |
| M2-LAB-01 | Structured output generator | Runnable implementation + tests + UI demonstration | Pending |
| M2-LAB-02 | Schema validation | Runnable implementation + validation/failure tests | Pending |
| M2-LAB-03 | Evaluation workflows | Repeatable evaluation pipeline + tests/results | Pending |
| M2-LAB-04 | Prompt-injection attack simulation | Safe local simulation + adversarial verification | Pending |

## Required Tools

The source explicitly identifies the following technologies. Their presence
must be demonstrated with implementation evidence rather than documentation
claims alone.

| ID | Tool | Required Evidence | Status |
| --- | --- | --- | --- |
| M2-TOOL-01 | Pydantic | Runtime implementation + tests | Pending |
| M2-TOOL-02 | OpenAI JSON Mode | Provider integration + tests and/or live verification | Pending |
| M2-TOOL-03 | LangChain PromptTemplate | Runtime prompt construction + tests | Pending |
| M2-TOOL-04 | PromptLayer | Evaluation/observability integration + verification | Pending |

## Required Deliverables

| ID | Deliverable | Acceptance Evidence | Status |
| --- | --- | --- | --- |
| M2-DEL-01 | Structured prompting framework | Runnable implementation + tests + documentation | Pending |
| M2-DEL-02 | Prompt evaluation pipeline | Runnable implementation + tests + evaluation evidence | Pending |

## Portfolio Demonstration Requirement

This repository additionally requires each completed module to expose a proper
runnable user interface or demonstrable front end.

For Module 2, the UI must demonstrate the source-required capabilities without
replacing or distorting the underlying implementation.

| ID | Requirement | Required Evidence | Status |
| --- | --- | --- | --- |
| M2-PORT-01 | Runnable Module 2 demonstration UI | UI contract tests + manual/live verification | Pending |

## Python Engineering Standards

All Module 2 Python implementation must follow these engineering standards:

1. Use Google-style docstrings for modules, classes, public functions, and
   public methods where appropriate.
2. Google-style docstrings must include `Args`, `Returns`, and `Raises`
   sections when applicable.
3. Use type hints throughout public interfaces and where they materially
   improve correctness and maintainability.
4. Implement intentional exception handling at genuine failure boundaries,
   including provider/API calls, malformed model output, schema validation,
   configuration, credentials, and external integrations.
5. Do not silently swallow exceptions or use blanket patterns such as
   `except Exception: pass`.
6. Errors must be specific and actionable and should preserve useful causal
   context.
7. Use exception chaining (`raise ... from exc`) where appropriate when
   translating lower-level failures into domain-level errors.
8. Expected failure paths must be tested rather than merely caught.
9. Error handling must live at the correct architectural boundary; unnecessary
   `try`/`except` blocks must not be added defensively throughout otherwise
   straightforward code.
10. Python implementation must satisfy the repository's Ruff, pytest, and
    compile quality gates before Module 2 can be declared complete.

These standards are candidates for persistent shared engineering policy in
both `AGENTS.md` and `CLAUDE.md`. Detailed reusable Python implementation and
verification procedures may later be extracted into provider-neutral
`SKILL.md` workflows when repeated module evidence supports that abstraction.
## Engineering Acceptance Rules

1. Every source requirement must have implementation and/or verification
   evidence appropriate to that requirement.
2. Passing quality gates alone does not prove source completeness.
3. No requirement may be marked complete solely because related functionality
   exists elsewhere.
4. Source-specified tools must be genuinely integrated where required.
5. Additive engineering improvements must not replace source requirements.
6. External/model-generated content is untrusted until validated.
7. Prompt-injection and jailbreak demonstrations must remain bounded and safe.
8. Tests and quality rules must not be weakened merely to obtain a green build.
9. Any source deviation requires explicit human approval.
10. Module completion requires both deterministic quality gates and a completed
    source-to-evidence traceability review.

## Automation Research Capture

Module 2 is the second training case for the future automated module-building
system.

The eventual system is intended to support both:

- Codex, governed through `AGENTS.md`
- Claude Code, governed through `CLAUDE.md`

The two agent instruction files should encode essentially the same
non-negotiable engineering policy.

Reusable procedural workflows should be extracted into relevant provider-neutral
`SKILL.md` files rather than duplicating large workflows independently in
`AGENTS.md` and `CLAUDE.md`.

Candidate automation responsibilities discovered during module development
should be classified as:

1. **Agent policy** — persistent rules suitable for `AGENTS.md` / `CLAUDE.md`.
2. **Reusable skill** — procedural workflows suitable for `SKILL.md`.
3. **Deterministic automation** — operations better enforced by scripts/tools.
4. **Human authority** — requirements, architecture, security, or deviation
   decisions that require explicit human judgment.

Module 2 must be implemented before treating these candidate abstractions as
stable. Repeated evidence across modules should determine what is generalized.

## Definition of Done

- [ ] All prompt-engineering source topics have verified evidence.
- [ ] Structured output generator is implemented.
- [ ] JSON/schema validation is implemented.
- [ ] Typed Pydantic outputs are implemented.
- [ ] OpenAI JSON Mode is genuinely integrated.
- [ ] LangChain PromptTemplate is genuinely integrated.
- [ ] PromptLayer is genuinely integrated.
- [ ] Prompt evaluation workflow is implemented.
- [ ] Prompt-injection attack simulation is implemented safely.
- [ ] Jailbreak detection and safety boundaries are demonstrated.
- [ ] Red-team testing is repeatable.
- [ ] Structured prompting framework is complete.
- [ ] Prompt evaluation pipeline is complete.
- [ ] Runnable UI demonstrates Module 2 functionality.
- [ ] Automated tests cover required behavior and failure paths.
- [ ] Repository quality gates pass in fail-fast order.
- [ ] Source-to-evidence traceability review has no unexplained gaps.
- [ ] Human review confirms source faithfulness.

