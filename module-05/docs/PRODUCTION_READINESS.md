# Module 5 Production-Readiness Upgrade

## Status

Module 5 satisfied its authoritative academic requirements and was released as
`v0.5.0-module-5`.

Under the repository-wide production-grade engineering standard, that release is
the verified functional baseline rather than the end of engineering work.

This document governs the additive production-readiness upgrade. The release tag
remains immutable.

## Assessment Standard

Production readiness is evaluated across:

**Requirements -> Product Experience -> Real Functionality -> Reliability ->
Security -> Cost -> Evidence -> Deployment**

A passing academic requirement set and runnable UI do not, by themselves,
establish production readiness.

## Verified Baseline

The released implementation already provides:

- 30/30 authoritative Module 5 requirements with traceability;
- a bounded application-owned ReAct lifecycle;
- allowlisted tools with JSON Schema validation;
- short-term, long-term, and episodic memory;
- OpenAI Function Calling integration;
- Anthropic Tool Use integration;
- LangChain Agents integration;
- Mem0 adapter and genuine local Mem0 evidence;
- bounded provider request/tool-call budgets;
- retry, timeout, and fallback primitives;
- adversarial tests around tool authority and untrusted provider output;
- a standalone Streamlit application;
- deterministic, mocked-SDK, local-integration, and UI evidence.

These capabilities remain protected during the upgrade.

## Verified Production-Readiness Gaps

### PR-01 — Live credential UI

The approved architecture requires a public zero-key-safe application in which a
user may explicitly authorize their own OpenAI or Anthropic credential for the
current Streamlit session.

The released application does not implement this path.

### PR-02 — Genuine live OpenAI execution

Implemented on the production-readiness feature branch. The feature-branch
application provides a separate, explicitly user-initiated OpenAI live path using the
session-only credential boundary introduced by PR-01. The live path constructs
the genuine OpenAI SDK client only after the live button is pressed, disables
SDK retries, applies a finite request timeout, and reuses the existing bounded
`run_openai_function_calling` loop and application-owned `ToolRegistry`.

The deterministic mocked-transport OpenAI demonstration remains separate and
zero-cost. Normal automated tests replace the OpenAI constructor and provider
runner with local stand-ins and therefore make no remote provider calls.

Implementation alone is **not live provider evidence**. The UI records an
attempted live run separately from successful LIVE evidence, and failure
messaging distinguishes failures before tool execution from failures after an
allowlisted tool has already run. A LIVE claim still requires a successful real
OpenAI request under explicit human authorization, as governed by PR-06.

### PR-03 — Genuine live Anthropic execution

Implemented on the production-readiness feature branch. The feature-branch
application provides a separate, explicitly user-initiated Anthropic live path
using the session-only credential boundary introduced by PR-01. The live path constructs
the genuine Anthropic SDK client only after the live button is pressed, disables
SDK retries, applies a finite request timeout, and reuses the existing bounded
`run_anthropic_tool_use` loop and application-owned `ToolRegistry`.

The deterministic mocked-transport Anthropic demonstration remains separate and
zero-cost. Normal automated tests replace the Anthropic constructor and provider
runner with local stand-ins and therefore make no remote provider calls.

Implementation alone is **not live provider evidence**. The UI records an
attempted live run separately from successful LIVE evidence. A LIVE claim still
requires a successful real Anthropic request under explicit human authorization,
as governed by PR-06.

### PR-04 — Integrated reliability

The feature-branch primary `run_agent` path now composes the existing bounded
retry and explicit fallback primitives at the synchronous decision-provider
boundary. Retry is restricted to explicitly configured transient exception
types, attempts are finite, retry consumption is recorded in `retry_count`,
and the safe default retries only `ConnectionError`. Ambiguous synchronous
timeouts are not replayed automatically because completion may be unknown,
and an optional application-owned fallback is invoked only after retry
exhaustion. Fallback use is recorded in `fallback_history`.

Fallback decisions remain untrusted proposals: schema validation, tool
authorization, execution budgets, lifecycle authority, and actual tool
execution remain application-owned. A fallback therefore cannot expand the
`ToolRegistry` allowlist or gain shell, eval, or filesystem authority.

The current `DecisionProvider` contract is synchronous. PR-04 intentionally
does not wrap that call in an uninterruptible worker thread and mislabel it as
genuine timeout cancellation. The existing `run_with_timeout` primitive
continues to provide real cancellation for awaitable operations, while the
live provider integrations retain their finite SDK request timeouts. A future
primary-runtime timeout may be added only at a genuinely cancellable boundary.

PR-05 remains responsible for reconciling terminal lifecycle state when
authorization, validation, tool execution, retry exhaustion, or other runtime
failures escape the runner.

### PR-05 — Runtime state reconciliation

The released `run_agent` path does not fully populate the reliability-related
state already represented by the architecture, including retry/fallback
evidence, and does not exercise the timeout lifecycle during normal integrated
execution.

### PR-06 — Live evidence

Deterministic, mocked, local, and live evidence must remain explicitly
distinguished.

A live provider claim may be made only after an actual provider call succeeds
under the approved live-test or user-authorized UI path.

## Credential and Authority Invariants

The Module 1 public credential pattern is the precedent for Module 5.

The production-grade upgrade must preserve all of the following:

1. Public startup requires zero credentials.
2. Entered credentials are session-only.
3. Credentials are masked in the UI.
4. Credentials are never committed or persisted by the public application.
5. Credentials are never printed, logged, traced, returned in tool output, or
   exposed in user-visible errors.
6. Entering a credential alone does not make a paid provider call.
7. A potentially billable live call requires an explicit user action.
8. Provider selection is application allowlisted.
9. Prompt/model/tool/memory/external data has no credential authority.
10. Possession of a credential grants access only to the selected provider path.
11. Provider output remains untrusted data.
12. Provider output cannot register tools or expand tool permissions.
13. Every proposed tool call still passes the application-owned ToolRegistry.
14. No arbitrary shell, eval, or filesystem authority is introduced.
15. Automated live tests require both a credential and
    `RUN_LIVE_LLM_TESTS=1`.
16. Normal tests remain zero-cost and make no paid remote calls.

## Fiscal Guardrails

Production quality must protect the project's war chest.

Live execution must therefore remain bounded by application-owned limits,
including:

- finite provider request counts;
- finite tool-call counts;
- finite agent execution steps;
- explicit user initiation;
- conservative defaults;
- deterministic/mock testing for normal CI and development;
- no automatic live calls during import, startup, testing, or credential entry.

No production-readiness change may replace deterministic verification with
unbounded paid verification.

## Upgrade Sequence

The implementation sequence is:

1. Add session-only OpenAI/Anthropic credential authorization to Streamlit.
2. Add explicit Demo / OpenAI Live / Anthropic Live execution modes.
3. Connect live modes to the existing provider integrations without bypassing
   ToolRegistry.
4. Integrate bounded reliability behavior into the primary agent execution path.
5. Reconcile lifecycle and reliability state.
6. Add security, cost, failure-path, and live-opt-in tests.
7. Update Streamlit evidence labels and user guidance.
8. Update traceability, verification, README, and user-guide evidence.
9. Run the complete fail-fast quality gate.
10. Perform live provider verification only with explicit human authorization
    and user-supplied credentials.
11. Perform deployment verification.
12. Reassess the complete production-readiness chain before making any
    production-grade or production-ready claim.

## Definition of Done

The production-readiness upgrade is complete only when:

- [ ] Existing 30/30 source coverage remains intact.
- [ ] Existing deterministic behavior remains available without credentials.
- [ ] Public UI supports session-only OpenAI credential authorization.
- [ ] Public UI supports session-only Anthropic credential authorization.
- [ ] Credentials cannot persist through the public application.
- [ ] Credential material cannot appear in logs, traces, errors, or output.
- [ ] Live calls require explicit user initiation.
- [ ] OpenAI live mode uses the existing application-owned tool boundary.
- [ ] Anthropic live mode uses the existing application-owned tool boundary.
- [ ] Provider/model output cannot expand application authority.
- [ ] Agent execution has bounded integrated retry behavior where appropriate.
- [ ] Agent execution has a real bounded timeout/deadline where appropriate.
- [ ] Fallback behavior is explicit, bounded, and observable where appropriate.
- [ ] Reliability state accurately records the behavior that occurred.
- [ ] Request, tool-call, and execution budgets remain finite.
- [ ] Normal automated tests make zero paid remote calls.
- [ ] Live automated tests require explicit opt-in.
- [ ] Deterministic/mock/local/live evidence remains distinguishable.
- [ ] Expected security and failure paths have automated coverage.
- [ ] Streamlit explains Demo and Live modes clearly.
- [ ] Streamlit explains potential provider cost before live execution.
- [ ] Documentation matches verified implementation.
- [ ] Ruff passes.
- [ ] pytest passes.
- [ ] compileall passes.
- [ ] Module 5 remains standalone.
- [ ] Modules 1-4 and Module 6 remain unmodified by Module 5 implementation.
- [ ] Deployment is verified after implementation.
- [ ] Production-readiness claims match actual evidence.

## Stop Conditions

Return to human review rather than silently changing architecture if the upgrade
would require:

- weakening a security or credential boundary;
- changing authoritative source requirements;
- introducing cross-module runtime dependencies;
- materially expanding external authority;
- making an unbounded or unexpectedly expensive provider call;
- weakening tests or quality rules;
- changing the approved provider/credential authority model.

Otherwise implementation proceeds automatically under the approved architecture
and repository engineering workflow.
