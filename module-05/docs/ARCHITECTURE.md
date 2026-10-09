# Module 5 — AI Agent Engineering Architecture

## Status

**APPROVED AND FROZEN; IMPLEMENTED.** Stories 1-10 are accepted. Story 11
reconciliation is complete and awaits independent acceptance and human
release approval.

This document was first written as a proposal with the status "PROPOSED —
HUMAN APPROVAL REQUIRED BEFORE IMPLEMENTATION". Approval is recorded in
sections 25 and 27. The design text below is the approved baseline and has
not been rewritten. Differences between this design and what was built are
recorded in section 28.

This architecture is subordinate to `SOURCE_REQUIREMENTS.md`.

The supplied Module 5 screenshot is the sole authoritative course source.

---

# 1. Architectural Goal

Build the smallest standalone system that completely demonstrates Module 5:

**A stateful autonomous AI agent that accepts a goal, performs bounded
multi-step reasoning and execution, dynamically selects validated tools,
maintains multiple forms of memory, and safely handles failures.**

The working demonstration concept is a:

**Stateful Research & Task Agent**

"Research" means a bounded tool-using demonstration workload. It does not imply
unrestricted Internet access or autonomous privileged action.

A single primary agent is sufficient. A multi-agent architecture is not
introduced because the source does not require one.

---

# 2. Architectural Principles

1. Source faithfulness is the hard invariant.
2. Module 5 is completely standalone.
3. Module 5 must not import from, reuse, modify, or depend on another module.
4. Use the smallest architecture that satisfies all requirements.
5. Agent execution is finite and bounded.
6. Application-owned state is explicit and typed.
7. Tool calls are validated before execution.
8. Model, tool, external, and memory output is untrusted data.
9. Memory supplies context, never authority.
10. Provider integrations sit behind explicit adapters.
11. Failures are observable and recoverable where appropriate.
12. Deterministic, mocked, adapter, and live evidence remain distinguishable.
13. The UI demonstrates core behavior but does not contain core domain logic.
14. No arbitrary shell execution or arbitrary Python evaluation is available
    to the autonomous agent.

---

# 3. System Boundary

## Inputs

The user may supply:

- a goal;
- optional context;
- provider/runtime selection where applicable;
- optional session-only provider credentials for live demonstrations.

## Agent responsibilities

The autonomous agent:

1. receives the goal;
2. initializes typed workflow state;
3. retrieves relevant memory;
4. determines the next bounded action;
5. dynamically selects an authorized tool;
6. validates the proposed call;
7. executes the tool;
8. validates and records the observation;
9. updates state and memory;
10. determines whether another step is required;
11. retries or falls back when permitted;
12. terminates explicitly.

## Outputs

The system exposes:

- final result;
- execution trace;
- selected tools;
- validated observations;
- memory events;
- retry/fallback events;
- terminal workflow state.

---

# 4. Standalone Module Structure

module-05/
    app.py
    README.md
    docs/
        SOURCE_REQUIREMENTS.md
        ARCHITECTURE.md
        TRACEABILITY.md
        VERIFICATION.md
    src/
        ai_agent_engineering/
            __init__.py
            models.py
            errors.py
            agent/
                __init__.py
                lifecycle.py
                react.py
                runner.py
            tools/
                __init__.py
                registry.py
                schemas.py
                builtins.py
            memory/
                __init__.py
                short_term.py
                long_term.py
                episodic.py
                mem0_adapter.py
            providers/
                __init__.py
                openai_tools.py
                anthropic_tools.py
            integrations/
                __init__.py
                langchain_agent.py
            resilience/
                __init__.py
                retry.py
                fallback.py
    tests/

This is a logical architecture. Story implementation may consolidate files
where a smaller design remains clearer and preserves responsibilities.

---

# 5. Agent Lifecycle

The workflow uses explicit finite lifecycle states:

RECEIVED
    |
INITIALIZED
    |
CONTEXT_READY
    |
REASONING
    |
TOOL_SELECTED
    |
VALIDATED
    |
EXECUTING
    |
OBSERVED
    |
    +--> REASONING
    +--> COMPLETED
    +--> FAILED
    +--> TIMED_OUT
    +--> BUDGET_EXHAUSTED

Transitions are application-owned and validated.

Model output cannot invent privileged lifecycle transitions.

This directly supports:

- M5-T01 — Agent lifecycle
- M5-T02 — Agent architectures
- M5-T04 — Goal-oriented systems
- M5-T05 — Execution loops
- M5-T14 — State management

---

# 6. Bounded ReAct Execution

The primary autonomous execution model follows a bounded ReAct-style pattern:

Goal
    |
Retrieve Context
    |
Reason
    |
Select Action / Tool
    |
Validate
    |
Act
    |
Observe
    |
Update State + Memory
    |
Continue or Finish

The implementation exposes application-visible decision records sufficient to
demonstrate reasoning/action/observation behavior.

It does not depend on exposing private model chain-of-thought.

The loop has:

- an explicit maximum step count;
- explicit terminal states;
- validated tool calls;
- timeout boundaries;
- bounded retry behavior.

This supports:

- M5-T03 — ReAct framework
- M5-T04 — Goal-oriented systems
- M5-T05 — Execution loops
- M5-T09 — Dynamic tool selection
- M5-T10 — Multi-step execution
- M5-L03 — Create multi-step reasoning systems

---

# 7. Tool Architecture

Tools use application-owned explicit contracts.

Each tool definition includes:

- stable name;
- purpose;
- typed/schema-validated inputs;
- output contract where appropriate;
- execution handler;
- authorization/safety metadata.

The initial deterministic teaching tools should remain small.

Proposed tools:

1. Calculator
2. Bounded local knowledge lookup
3. Structured note/context lookup

The tool registry owns the allowlist.

Before execution:

1. the tool must exist;
2. the tool must be authorized;
3. arguments must satisfy its schema;
4. execution must remain within its allowed boundary.

This supports:

- M5-T06 — Function calling
- M5-T07 — Tool schemas
- M5-T08 — Tool orchestration
- M5-T09 — Dynamic tool selection
- M5-T19 — Validation
- M5-T20 — Safe execution patterns
- M5-L01 — Build tool-using AI agent

---

# 8. Required LangChain Agents Integration

Module 5 includes a genuine LangChain Agents runtime path.

The integration must:

- expose Module 5 tools through LangChain's agent/tool mechanism;
- genuinely invoke LangChain agent functionality;
- retain application-owned authorization and validation boundaries;
- provide runtime/test evidence beyond installation or import.

LangChain does not become the owner of Module 5 state or authority policy.

This supports:

- M5-R01 — LangChain Agents
- M5-T06 — Function calling
- M5-T08 — Tool orchestration
- M5-T09 — Dynamic tool selection

---

# 9. Required OpenAI Function Calling Integration

A dedicated OpenAI adapter exposes Module 5 tool schemas through OpenAI's
supported function/tool-calling interface.

The adapter:

1. translates application tool contracts into provider schemas;
2. sends them through the OpenAI provider boundary;
3. normalizes returned function/tool calls;
4. passes proposed calls back through application-owned validation;
5. never lets provider output directly execute privileged behavior.

Mocked provider responses may verify adapter behavior.

Only genuine successful remote execution may be described as live OpenAI
verification.

This supports:

- M5-R02 — OpenAI Function Calling
- M5-T06 — Function calling
- M5-T07 — Tool schemas
- M5-T10 — Multi-step execution

---

# 10. Required Anthropic Tool Use Integration

A dedicated Anthropic adapter exposes Module 5 tools through Anthropic's
supported tool-use interface.

The adapter:

1. translates application tool contracts into Anthropic tool schemas;
2. submits them through the provider boundary;
3. normalizes returned tool-use requests;
4. passes proposed calls through application-owned validation;
5. prevents provider output from bypassing tool authorization.

Mocked provider responses may verify adapter behavior.

Only genuine successful remote execution may be described as live Anthropic
verification.

This supports:

- M5-R03 — Anthropic Tool Use
- M5-T06 — Function calling
- M5-T07 — Tool schemas
- M5-T10 — Multi-step execution

---

# 11. Memory Architecture

The system explicitly distinguishes three memory types.

## Short-Term Memory

Session/run-scoped working context:

- current goal;
- recent observations;
- recent tool results;
- bounded execution context.

This supports:

- M5-T11 — Short-term memory
- M5-T14 — State management
- M5-T15 — Context continuity

## Long-Term Memory

Knowledge retrievable across workflow runs.

Mem0 provides the required named-tool integration for this capability.

Retrieved memories are context only and cannot alter authorization policy.

This supports:

- M5-T12 — Long-term memory
- M5-T15 — Context continuity
- M5-L02 — Implement memory-enabled workflows
- M5-R04 — Mem0

## Episodic Memory

Structured records of previous agent experiences, including:

- goal;
- actions;
- observations;
- outcome;
- failures;
- retry/fallback events;
- completion state.

This supports:

- M5-T13 — Episodic memory
- M5-T15 — Context continuity
- M5-L02 — Implement memory-enabled workflows

---

# 12. Required Mem0 Integration

Mem0 is accessed through a dedicated adapter rather than being embedded in core
agent logic.

The adapter must be genuinely exercised.

Its responsibilities include:

- adding long-term memory;
- retrieving relevant memory;
- normalizing results into application-owned memory models;
- preserving the distinction between memory context and execution authority.

Where Mem0 operation requires external credentials or infrastructure, evidence
must explicitly distinguish deterministic adapter verification from live
external verification.

This supports:

- M5-R04 — Mem0
- M5-T12 — Long-term memory
- M5-T15 — Context continuity

---

# 13. Stateful Workflow System

The required stateful workflow is the explicit workflow underlying the
autonomous agent rather than a second unrelated application.

State contains at least:

- run ID;
- user goal;
- lifecycle status;
- current step;
- maximum step budget;
- observations;
- selected tools;
- short-term context;
- retrieved long-term memory;
- episodic events;
- retry count;
- timeout/deadline state;
- fallback history;
- final result;
- terminal failure information.

The workflow preserves state across valid transitions.

This directly implements:

- M5-T14 — State management
- M5-T15 — Context continuity
- M5-D02 — Stateful workflow system

---

# 14. Reliability Architecture

## Retry

Retries are:

- bounded;
- limited to retryable failures;
- observable;
- counted;
- unable to exceed the overall execution budget.

Supports:

- M5-T16 — Retry strategies

## Timeout

Provider/tool execution receives explicit timeout or deadline handling.

A timeout becomes a typed event/state instead of hanging indefinitely.

Supports:

- M5-T17 — Timeout handling

## Failure Recovery

Recoverable failures return execution to a valid state.

Non-recoverable failures terminate explicitly.

No exception is silently converted into success.

Supports:

- M5-T18 — Failure recovery

## Fallback

A failed primary path may use an explicitly configured fallback where safe.

Fallback use is visible in state and execution history.

Supports:

- M5-L04 — Build retry/fallback mechanisms

---

# 15. Validation and Safe Execution

Safety remains application-owned.

Required controls:

- allowlisted tool registry;
- schema validation;
- typed state;
- finite lifecycle transitions;
- bounded execution steps;
- bounded retries;
- timeouts;
- explicit fallback policy;
- no arbitrary shell execution;
- no arbitrary Python evaluation;
- no model-controlled filesystem paths;
- no implicit credential persistence;
- model output remains untrusted;
- tool output remains untrusted;
- external output remains untrusted;
- memory output remains untrusted;
- deterministic terminal failure states.

This supports:

- M5-T19 — Validation
- M5-T20 — Safe execution patterns

---

# 16. Autonomous Agent Deliverable

The autonomous AI agent integrates:

- goal-oriented execution;
- ReAct-style progression;
- dynamic tool selection;
- function/tool calling;
- multi-step execution;
- memory;
- validation;
- retry;
- timeout;
- fallback;
- explicit completion/failure.

This implements:

- M5-D01 — Autonomous AI agent

---

# 17. Stateful Workflow Deliverable

The stateful workflow owns:

- lifecycle state;
- execution progress;
- context;
- observations;
- memory references;
- retry/fallback history;
- terminal state.

The two deliverables therefore form one coherent system:

Stateful Workflow
        |
Autonomous Agent
        |
Reason -> Tool -> Observe -> Memory
        |
Retry / Fallback / Continue / Finish

This implements:

- M5-D02 — Stateful workflow system

---

# 18. Hands-On Lab Mapping

## Lab 1 — Tool-Using AI Agent

Demonstrate an autonomous goal that requires dynamic tool selection and
validated tool execution.

Covers:

- M5-L01
- M5-D01

## Lab 2 — Memory-Enabled Workflow

Demonstrate short-term, long-term, and episodic memory with context continuity.

Covers:

- M5-L02
- M5-T11
- M5-T12
- M5-T13
- M5-T15
- M5-R04

## Lab 3 — Multi-Step Reasoning System

Demonstrate a bounded goal requiring multiple reason/action/observation steps.

Covers:

- M5-L03
- M5-T03
- M5-T05
- M5-T10

## Lab 4 — Retry/Fallback Mechanisms

Demonstrate controlled failure followed by bounded retry and/or safe fallback.

Covers:

- M5-L04
- M5-T16
- M5-T17
- M5-T18

---

# 19. Streamlit Demonstration Layer

Module 5 includes a standalone Streamlit interface.

The interface provides four major demonstration areas.

## Autonomous Agent

User:

- enters a goal;
- executes the bounded agent;
- observes lifecycle and tool selection;
- inspects the final result.

## Memory

User:

- observes short-term context;
- adds/retrieves long-term memory;
- inspects episodic history;
- observes context continuity.

## Required Tool Integrations

User can inspect or exercise:

- LangChain Agents;
- OpenAI Function Calling;
- Anthropic Tool Use;
- Mem0.

Credential-dependent live paths remain optional and session-only.

## Reliability

User can trigger controlled demonstrations of:

- retry;
- timeout;
- fallback;
- terminal failure/recovery.

Each major UI area explains:

1. what to do;
2. what result to expect;
3. what engineering capability the result demonstrates.

---

# 20. Requirement-to-Architecture Traceability

| ID | Source requirement | Architecture evidence |
| --- | --- | --- |
| M5-T01 | Agent lifecycle | Explicit lifecycle state machine |
| M5-T02 | Agent architectures | Standalone layered single-agent architecture |
| M5-T03 | ReAct framework | Bounded Reason/Action/Observation loop |
| M5-T04 | Goal-oriented systems | Goal-driven state and execution |
| M5-T05 | Execution loops | Finite runner and step budget |
| M5-T06 | Function calling | Tool contracts plus provider integrations |
| M5-T07 | Tool schemas | Typed/schema-validated tool definitions |
| M5-T08 | Tool orchestration | Registry plus execution runner |
| M5-T09 | Dynamic selection | Runtime tool selection |
| M5-T10 | Multi-step execution | Repeated validated execution transitions |
| M5-T11 | Short-term memory | Session working context |
| M5-T12 | Long-term memory | Long-term interface plus Mem0 |
| M5-T13 | Episodic memory | Structured run history |
| M5-T14 | State management | Typed workflow state |
| M5-T15 | Context continuity | State propagation plus memory retrieval |
| M5-T16 | Retry strategies | Bounded retry policy |
| M5-T17 | Timeout handling | Explicit execution deadlines |
| M5-T18 | Failure recovery | Typed recovery and fallback transitions |
| M5-T19 | Validation | Tool, argument, state, and result validation |
| M5-T20 | Safe execution patterns | Allowlist, authority, and budget boundaries |
| M5-L01 | Build tool-using AI agent | Agent/tool lab and UI |
| M5-L02 | Implement memory-enabled workflows | Memory lab and UI |
| M5-L03 | Create multi-step reasoning systems | ReAct execution lab and UI |
| M5-L04 | Build retry/fallback mechanisms | Reliability lab and UI |
| M5-R01 | LangChain Agents | Genuine LangChain runtime integration |
| M5-R02 | OpenAI Function Calling | Genuine OpenAI tool/function adapter |
| M5-R03 | Anthropic Tool Use | Genuine Anthropic tool-use adapter |
| M5-R04 | Mem0 | Genuine Mem0 memory adapter |
| M5-D01 | Autonomous AI agent | Integrated autonomous agent |
| M5-D02 | Stateful workflow system | Explicit typed stateful workflow |

**Architecture mapping: 30/30 source requirements.**

---

# 21. Implementation Story Sequence

## Story 1 — Contracts and Lifecycle Foundation

Implement:

- typed workflow state;
- lifecycle states;
- transition validation;
- errors;
- execution budget.

Primary source coverage:

M5-T01, M5-T02, M5-T04, M5-T05, M5-T14, M5-T19.

## Story 2 — Tool Contracts and Safe Orchestration

Implement:

- tool schemas;
- registry;
- deterministic teaching tools;
- authorization boundaries;
- validation;
- dynamic selection primitives.

Primary source coverage:

M5-T06, M5-T07, M5-T08, M5-T09, M5-T19, M5-T20.

## Story 3 — Bounded ReAct Execution

Implement:

- reason/action/observation progression;
- finite execution loop;
- multi-step completion;
- deterministic initial runtime.

Primary source coverage:

M5-T03, M5-T04, M5-T05, M5-T09, M5-T10,
M5-L01, M5-L03, M5-D01.

## Story 4 — Native Memory Model

Implement:

- short-term memory;
- application-owned long-term interface;
- episodic memory;
- context continuity.

Primary source coverage:

M5-T11, M5-T12, M5-T13, M5-T14, M5-T15,
M5-L02, M5-D02.

## Story 5 — Mem0 Integration

Implement and genuinely exercise the Mem0 adapter.

Primary source coverage:

M5-T12, M5-T15, M5-R04.

## Story 6 — Reliability and Recovery

Implement:

- bounded retries;
- timeout behavior;
- fallback;
- explicit failure recovery.

Primary source coverage:

M5-T16, M5-T17, M5-T18, M5-T20, M5-L04.

## Story 7 — LangChain Agents Integration

Implement and genuinely exercise LangChain Agents using Module 5 tool contracts.

Primary source coverage:

M5-T06, M5-T08, M5-T09, M5-R01.

## Story 8 — OpenAI Function Calling

Implement OpenAI tool/function calling through the application validation
boundary.

Primary source coverage:

M5-T06, M5-T07, M5-T10, M5-R02.

## Story 9 — Anthropic Tool Use

Implement Anthropic tool use through the same application validation boundary.

Primary source coverage:

M5-T06, M5-T07, M5-T10, M5-R03.

## Story 10 — Integrated Streamlit Demonstration

Implement the guided UI for:

- autonomous execution;
- memory;
- multi-step reasoning;
- required integrations;
- retry/fallback behavior;
- evidence visibility.

Primary source coverage:

M5-L01, M5-L02, M5-L03, M5-L04,
M5-D01, M5-D02.

## Story 11 — Reconciliation and Release Verification

Complete:

- 30/30 source reconciliation;
- traceability;
- verification evidence;
- full quality gates;
- UI/runtime smoke testing;
- final documentation;
- release readiness.

Primary source coverage:

All Module 5 requirements.

---

# 22. Quality and Self-Healing Strategy

Each story adds tests appropriate to its behavior.

Formal fail-fast quality gate:

1. Ruff
2. pytest
3. compileall

Safe Ruff fixes may be applied mechanically before the formal gate.

Unsafe fixes must never be automatically applied.

On failure:

1. capture the exact diagnostic;
2. classify deterministic versus semantic failure;
3. apply safe deterministic repair when available;
4. otherwise use a bounded semantic repair attempt;
5. rerun the failed gate;
6. rerun the complete fail-fast sequence;
7. escalate only when safe bounded repair cannot resolve the issue or a genuine
   requirements/design decision is required.

Tests, requirements, security boundaries, or quality rules must never be
weakened simply to obtain green results.

---

# 23. Definition of Done

Module 5 is complete only when:

- [ ] 30/30 source requirements have verified evidence.
- [ ] All four hands-on labs are implemented.
- [ ] All four labs are demonstrable.
- [ ] Autonomous AI agent exists.
- [ ] Stateful workflow system exists.
- [ ] LangChain Agents is genuinely exercised.
- [ ] OpenAI Function Calling is genuinely exercised.
- [ ] Anthropic Tool Use is genuinely exercised.
- [ ] Mem0 is genuinely exercised.
- [ ] Short-term memory is demonstrated.
- [ ] Long-term memory is demonstrated.
- [ ] Episodic memory is demonstrated.
- [ ] Context continuity is demonstrated.
- [ ] ReAct behavior is demonstrated.
- [ ] Dynamic tool selection is demonstrated.
- [ ] Multi-step bounded execution is demonstrated.
- [ ] Retry behavior is demonstrated.
- [ ] Timeout behavior is demonstrated.
- [ ] Fallback/recovery behavior is demonstrated.
- [ ] Validation boundaries are demonstrated.
- [ ] Safe execution boundaries are tested.
- [ ] Runnable standalone Streamlit UI exists.
- [ ] UI includes concise user guidance.
- [ ] UI runtime smoke test passes.
- [ ] Expected failure paths have automated coverage.
- [ ] Ruff passes.
- [ ] pytest passes.
- [ ] compileall passes.
- [ ] Traceability documentation is complete.
- [ ] Verification distinguishes deterministic/mock/adapter/live evidence.
- [ ] Module 5 remains standalone.
- [ ] No other module's contents were modified by Module 5 implementation.

---

# 24. Architecture Freeze

After explicit human approval, this architecture becomes the Module 5
implementation baseline.

Implementation may make small evidence-driven local refinements but must not
silently:

- alter the authoritative source contract;
- remove source coverage;
- weaken safety boundaries;
- introduce dependencies on another module;
- expand into unnecessary architecture.

A genuine architecture-level conflict returns to human review.

---

# 25. Human Approval Gate

**Current state: APPROVED AND FROZEN**

Human review is complete. The architecture is approved and implementation may
begin under the frozen architecture and source-faithfulness constraints.

# 26. Live Credential and Provider Policy

Module 5 is intended to be practically usable with genuine provider
credentials while remaining safe by default.

The credential model follows these requirements:

1. The public Streamlit application starts with zero automatically authorized
   provider credentials.
2. A user may explicitly enter their own provider credential for live use.
3. Credentials entered through the public UI are session-only.
4. The public UI must not persist provider credentials.
5. Local development may support explicitly configured local environment or
   `.env` credentials.
6. Local secret files must remain ignored by Git and must never be committed.
7. Secrets must never be printed, logged, included in traces, exposed in error
   messages, or returned in agent/tool output.
8. Credential/provider names accepted from configurable sources must be
   allowlisted where applicable.
9. Untrusted input must not be able to inject or select arbitrary credential
   names.
10. Prompt content, model output, tool output, retrieved memory, and external
    data have no credential authority.
11. Possession of a credential authorizes only the explicitly selected provider
    path. It does not expand agent tool permissions or execution authority.
12. Normal tests, imports, examples, and default demonstrations must make zero
    paid remote API calls.
13. Automated live-provider verification requires both:
       a. the required credential; and
       b. explicit live-test opt-in through `RUN_LIVE_LLM_TESTS=1`.
14. Merely having credentials in the environment must never trigger paid live
    tests.
15. Live checks must be intentionally small and bounded to minimize cost and
    unintended provider usage.
16. Deterministic/mock/adapter verification must remain clearly distinguishable
    from genuine live-provider verification.
17. Provider/tool calls remain subject to the Module 5 allowlist, schema
    validation, execution budget, timeout, retry, and safety boundaries.
18. Model/provider output cannot authorize new tools, persist credentials,
    modify the allowlist, or bypass application-owned validation.

The practical target is genuine live verification of credential-dependent
required integrations when suitable credentials are available, without making
live external access a prerequisite for safe local startup or the deterministic
test suite.

---

# 27. Architecture Approval Record

**ARCHITECTURE APPROVED AND FROZEN**

Human approval explicitly includes:

- the 30/30 source-requirement architecture;
- the 11-story implementation sequence;
- strict standalone Module 5 isolation;
- genuine use of LangChain Agents, OpenAI Function Calling, Anthropic Tool Use,
  and Mem0;
- a practically usable live-provider path;
- zero-key safe startup;
- session-only public UI credentials;
- explicit opt-in for automated live-provider testing;
- application-owned authority boundaries around all agent and provider actions.

Implementation may now begin with Story 1.

---

# 28. Implementation Reconciliation Record (Story 11)

Recorded 2026-10-08 after Stories 1-10 were accepted. This section records how
the built system differs from the approved design above. It does not change
the design or the source contract. Requirement-level evidence is in
`TRACEABILITY.md`; gate results are in `VERIFICATION.md`.

## Source coverage

All 30 source requirements have implementation and verification evidence.
None of the differences below removes source coverage.

## Structure

- Section 4 lists the files as a logical layout. As built, `resilience/` also
  has `timeout.py` (`run_with_timeout`), which section 14 called for.
- `README.md` and `docs/TRACEABILITY.md` were added in Story 11.
- Module 5 is not registered in the root `pyproject.toml` (packages, pytest
  `pythonpath` or `testpaths`). Its tests run with `PYTHONPATH=module-05/src`,
  and `app.py` adds its own `src/` to `sys.path`. Registering it is a root
  change outside Module 5 and was not made.

## Behaviour

1. **Reliability is composed, not wired into the runner.** Retry, timeout
   and fallback (section 14) are standalone, tested primitives demonstrated in
   the Reliability area. `run_agent` does not call them: it never enters
   `TIMED_OUT`, and `retry_count` and `fallback_history` in the state
   (section 13) are never written. There is no deadline field on the state.
   Section 3 step 11 ("retries or falls back when permitted") and section 16's
   list for the integrated agent are therefore only partly realised.
2. **Denied or failing tool calls stop the run with a typed exception.** When
   validation denies a call or a tool raises, `run_agent` raises and leaves
   the lifecycle where it stopped (for example `tool_selected` or
   `executing`) instead of moving to `FAILED`. The run is never reported as
   success. Budget exhaustion and invalid decision objects do reach terminal
   states.
3. **Memory is attached to runs by the presentation layer.** `run_agent`
   does not read or write memory. `app.py` loads long-term facts, short-term
   context and recent episodes into the state before a run and records the
   run afterwards. This was accepted in Story 10 alongside the other labelled
   demonstration stand-ins in `app.py` (keyword planner, scripted LangChain
   model, scripted provider responses, Mem0 stand-in backend).
4. **No live credential path was built.** Sections 19 and 26 allow a
   session-only credential and an opt-in live test gate
   (`RUN_LIVE_LLM_TESTS=1`). Neither exists. The UI and tests are zero-key
   only, and live OpenAI and Anthropic verification remains deferred, as
   accepted in Stories 8-10. Policy items 12 and 14 (no paid calls in normal
   tests, credential presence never triggers a call) are met.
5. **Mem0 runs genuinely only in an offline uv overlay.** `mem0ai` is not a
   declared dependency. The genuine path uses Story 5's cached
   `uv run --with mem0ai==2.2.1` overlay with `--offline --no-sync`, and
   refuses to start unless Mem0 telemetry is off and the Hugging Face hub is
   offline. `Mem0MemoryAdapter.from_default_mem0()` would build Mem0 with its
   remote defaults; nothing in Module 5 calls it.

## Definition of done (section 23)

Every item in section 23 is met on the evidence in `TRACEABILITY.md` and
`VERIFICATION.md`, with the qualifications in this section. "Genuinely
exercised" means: LangChain through its real runtime with a local scripted
model; OpenAI and Anthropic through their real SDKs over mocked transport (not
live); Mem0 through the real library locally and offline (not cloud).
