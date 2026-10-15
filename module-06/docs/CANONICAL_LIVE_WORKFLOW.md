# Canonical Researcher → Analyst → Critic candidate

## Scope and evidence

This is an offline implementation candidate on the accepted Architecture B+.
It requires independent offline acceptance and fresh human HITL before real
execution. No source requirement is declared complete: M6-001 through M6-026
remain Planned. No staging, commit, push, deployment, dependency update, model
request, real credential inspection, or live telemetry delivery belongs to this
implementation task.

**Verified before this slice:** the committed adapter at
`5108b65160ee7f4d0418b16268b2e6167ced2c72` successfully processed one post-repair
real Ollama response for `qwen2.5-coder:7b`: HTTP 200, exact model identity,
40 input / 6 output tokens, validated/discarded `prompt_eval_cached_count`,
zero retries, repairs, or redirects. That evidence covers one provider response,
not this graph, role-output quality, or a three-role live workflow. It was not
repeated for this slice.

**Verified by this slice:** synthetic model behavior through the canonical
application entry point, actual LangGraph StateGraph, supervised child, bounded
IPC, and reviewed provider parser with `httpx.MockTransport`. These are offline
integration and adversarial regression tests, not real inference.

**Not yet verified:** actual live Researcher → Analyst → Critic execution,
actual model quality, live LangSmith tracing, live Streamlit execution,
hosted-provider compatibility, or production deployment readiness.

## Application path

`canonical_workflow.execute_canonical_workflow` is the application API. It accepts
bounded task data, the existing explicit `LiveAuthorization`, optional application
UUIDs, and optional local `Observability`. It revalidates authorization using the
accepted boundary and requires the canonical explicit selection:
`local_model_inference` / `ollama` / `qwen2.5-coder:7b`. Absence or invalidity
refuses before provider construction or process allocation. Availability,
credentials, configuration, and model content cannot supply authorization.

The default source-backed factory constructs the existing `LocalModelGateway`
inside the accepted gateway child, after authorization. The service delegates
all orchestration, policy, budgets, output validation, accounting, deadlines, and
process ownership to the accepted `execute_live_workflow`. There is no second
graph, security policy, transport, fallback, tool runner, or UI business logic.
The graph remains fixed:

```text
START → Researcher → Analyst → Critic → validated application result → END
```

For offline tests, trusted application/test code supplies a source-backed
`gateway_factory`. That factory is the only substituted dependency; the same
canonical API, graph, role parser, supervisor, and completion boundary execute.
Factories and observers are trusted infrastructure, never model-supplied
capabilities. No CLI or console control enabling live inference is added.

## Content and authority

Each prompt explicitly declares its role, the strict role JSON schema, no tools,
no environment/file/network access, and no authority. Researcher derives up to
three bounded findings from the task and existing knowledge, with no external
research. Analyst assesses validated findings and cites their one-based indices.
Critic receives validated research and analysis and supplies an advisory verdict
and rationale. `needs_revision` is valid content; it does not reject the graph,
authorize more calls, or cause another workflow.

Task text is length-labeled in `TASK_DATA`, enclosed by an application-selected
delimiter absent from that text. This preserves the accepted full input bound
without JSON-escaping expansion. Prior roles are JSON-serialized from validated
content contracts into `PRIOR_CONTENT`, never raw provider envelopes. Both are
explicitly labeled untrusted data. Task text cannot close its own chosen frame;
it is not a claim that model-level prompt
injection is universally solved. Routing and authority never consult these texts.

The existing closed `ResearchOutput`, `AnalysisOutput`, and `CritiqueOutput`
schemas enforce types and field bounds. Analyst citations must refer to actual
research findings. Unknown authority/tool/routing fields fail validation. The
application determines completion from all three validated outputs and accepted
runtime invariants, not a model's claim of acceptance.

## Execution controls

Every budget value remains explicit in `LiveBudget`; none is inferred or raised.
Normal success consumes exactly three calls. Only malformed role content may
consume the sole optional repair, preserving role, selection, original task,
validated prior context, and application-owned instructions. A failed repair or
second malformed role fails closed. No fifth call is possible. Provider,
transport, envelope, and process failures never qualify as repairs; retries stay
zero. There is no provider/model fallback.

The accepted runtime charges calls at dispatch, checks deadlines before and after
operations and after cleanup, enforces reply/IPC/prompt bounds and one operation
at a time, and supervises one child for the workflow. Complete prompts still
have to fit the accepted prompt bound. Provider token limits are requested, and the
application enforces reply bytes. Child environment remains minimal. Termination
and reaping retain the independent two-second supervisor cleanup allowance.
Cancellation is sanitized and reaped. Late results produce failure, not completed
evidence. No raw malformed output is included in a repair prompt or failure.

## Evidence and observations

`CanonicalWorkflowReceipt` wraps the unchanged accepted `LiveWorkflowResult`.
Its `evidence_source` is application-selected: every injected factory is
`synthetic_offline`; only the default reviewed adapter path is
`local_provider_execution`. That label identifies selected gateway provenance,
not quality or deployment acceptance. The accepted inner `execution_class`
describes the authorized target; by itself it is not proof of actual inference.
Tests using a stub solely to check default binding do not constitute real
execution evidence. Application code must retain the whole canonical receipt,
not present the inner execution class alone as a live-verification claim.

The runtime result includes selection, budget, topology, role contributions,
call/repair counts, zero transport retries, validated content, and representable
usage. Usage is accumulated only from validated replies. Missing usage remains
unavailable; cached prompt counts and duration metadata never become authoritative
usage or cost. There is no fabricated cost. `CanonicalWorkflowError` preserves
the accepted sanitized `LiveFailure` and adds the same provenance marker.

`Observability` has a separate bounded local live-event channel: at most two
trusted synchronous local sinks and 32 retained events. Events cover start,
validated roles, completion, failure, invalid input, and cancellation. They carry
only UUIDs, phase, optional role, application counts, failure category, and
provenance, never prompts or generated/provider content. Role events are
provisional; completion follows successful cleanup and final runtime checks.
Cancellation counts are unavailable rather than fabricated zeroes.

Each sink and reader receives a fresh revalidated event copy. Mutation or sink
failure cannot change workflow control, retained events, or another sink. Local
adapter failures/dropped events use existing saturated counters. No live event
is converted into the accepted deterministic `RunTrace`/zero-call accounting,
and no legacy SDK export or remote state publication is invoked by this channel.
Sinks must obey the existing trusted bounded synchronous infrastructure contract.

## Offline verification and operational limits

The source-backed synthetic fixture matches all 12 observed top-level Ollama
fields and both message fields, including validated/discarded cached count.
Canonical tests use real child IPC and the reviewed adapter with an in-memory
transport. They cover exact role progression, all three repair locations,
exhausted repairs, malformed envelopes, transport/provider errors, forged
authority, prompt-injection strings, unavailable usage, cancellation, late
cleanup, observer isolation, and child reaping. Existing runtime suites retain
the detailed budgets, process/protocol, and concurrency checks; existing
deterministic suites run unchanged.

The focused coverage maps to the requested offline matrix as follows; retained
runtime/provider suites supply the deeper existing boundary cases.

| Requested checks | Canonical tests / retained coverage |
| --- | --- |
| 1–7: graph, calls, roles, contracts, context | `test_real_graph_adapter_all_roles_context_and_advisory_critic`; native graph progression and child requests |
| 8–11: each repair location and four-call success | `test_one_repair_same_role_context_selection_four_calls`, parameterized over all roles |
| 12–16, 20: failed/consumed repair, no fifth call, zero retries | `test_failure_no_retry_no_fifth_no_disclosure`, including failure at call four and provider/transport errors |
| 17–18: budgets and deadline | `test_no_repair_budget_stops_first_malformed`, forged-budget refusal, timeout test, retained `test_live_execution.py` budget/deadline cases |
| 19, 21–27: model authority and prompt injection | closed-schema authority-field cases, explicit-selection refusal, framed user attacks and hostile prior research |
| 28–29: advisory Critic, application completion | valid `needs_revision` still completes; unknown acceptance/authority fields fail; late cleanup never completes |
| 30–31: validated and unavailable usage | happy path counts exclude cached metadata; absent and partially absent usage remain unavailable |
| 32–34: classification and sanitized failures | receipt/error provenance; canary checks on failures/events; source binding test is explicitly not live proof |
| 35–38: reap, late output, environment | autouse actual-child reaping assertion on every canonical case; late-cleanup and timeout/cancellation tests; child environment assertion |
| 39: concurrency one | one supervised PID, sequential requests, accepted strict budget and retained runtime concurrency cases |
| 40: deterministic regression | complete Module 6 and root suites; existing security assertions retained |

Gates use the installed environment without synchronization, a test-owned home
outside OneDrive, absent ambient credentials, disabled tracing/telemetry/dotenv,
and guards blocking real dotenv reads, external DNS/network, the provider port,
and live telemetry ports. Test-owned ephemeral loopback/IPC remains permitted.
No real provider or external telemetry is contacted. Gate results are recorded
below after completion.

The SOP review is scoped: requirements are implemented for this candidate, with
all 26 reconciliation statuses still Planned; product experience is a typed API,
with UI work deferred; the real adapter path exists but real graph behavior is
unverified; reliability/security/cost controls are exercised offline; evidence
remains explicitly synthetic; deployment remains unverified. This is not an
independent acceptance, release, or production-readiness declaration.

Before real execution: obtain independent offline acceptance, resolve any
findings, and obtain fresh HITL stating exact selection, task, explicit budget,
three expected calls/four maximum with at most one malformed-output repair,
zero retries, and no tools/external actions. Live quality, tracing, Streamlit,
and deployment are separate later verification milestones.

## Candidate review and gate history

Self-review repaired a candidate prompt-size regression: JSON-quoting the task
could overflow the accepted prompt envelope for maximum-length escaped input.
Length-labeled delimiter framing preserves task text and the existing bounds.
The retained maximum-task/maximum-role-content/repair regression passes unchanged.

The first complete Module 6 attempt stopped at **1 failed, 1,410 passed**:
`test_default_paths_load_no_live_module` detected an eager live-contract import
through the deterministic observer. This was a candidate defect, repaired using
type-only imports and lazy loading in the live channel. No existing assertion
was changed.

A subsequent focused attempt stopped at **1 failed, 37 passed** because a new
test supplied 4,096 newlines and expected success. That test fixture was invalid:
accepted validation correctly refuses blank text. The fixture now contains a
visible character while retaining 4,096 characters; blank-input refusal remains
unchanged. This was a test/harness defect, not an application defect.

After these repairs, **60 focused tests passed**: all 58 canonical cases and the
two retained startup-isolation and maximum-envelope regressions. Initial lint-only
issues were corrected; no unsafe auto-fixes, dependency changes, test weakening,
or authorized-boundary changes were used.

The next complete attempt stopped at **1 failed, 1,495 passed** because the
existing live-contract security test enumerated only the original contract names.
The new receipt and event types were absent from that expected inventory. The
test now imports and explicitly includes both additive types, with all existing
non-disclosure, closed-schema, frozen, and nested-revalidation assertions retained
and applied to them too. This is additive security coverage, not a relaxed check.

Final candidate Module 6 gate: `uv run --offline --no-sync ruff check module-06`
passed; the complete suite returned **2,023 passed** in 367.17 seconds, with no
skips or warnings. This is the accepted 1,965-test baseline plus 58 canonical
cases. The extended security inventory also passed in an isolated focused run.

The complete root suite returned **4,138 passed, 6 skipped, 3 warnings** in
479.98 seconds: the accepted 4,080-pass baseline plus the same 58 cases. The
conditional skips and three ChromaDB legacy-embedding-configuration deprecation
warnings are existing outcomes. No environment/infrastructure failure occurred
in either final complete run.

`compileall` passed over `module-06/src`, `module-06/tests`, `module-06/app.py`,
`run_console.py`, `run_langsmith.py`, `run_telemetry.py`, and `run_benchmark.py`.
Whitespace/scope checks passed. Dependency files are unchanged. The temporary
offline launcher and task-owned external test directory were removed after gates.
The final candidate contains only this document, README, canonical contracts and
service, role-prompt/observation-hook changes in the accepted runtime, the additive
local observer channel, synthetic fixture/tests, and the extended contract
security inventory. Branch and HEAD remain the specified baseline; nothing is
staged, committed, pushed, or deployed. Independent acceptance is still pending.
