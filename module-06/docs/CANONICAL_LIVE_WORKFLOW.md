# Canonical Researcher → Analyst → Critic candidate

> **Status note (S7).** Dated historical record. Where it says "Planned", "candidate" or "pending", that was true when written; current requirement status is in [TRACEABILITY.md](TRACEABILITY.md) and engineering status in [PROJECT_STATUS.md](PROJECT_STATUS.md). The body below is unchanged.

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

**Verified later:** one bounded real local Researcher → Analyst → Critic
execution (Run 2, below). One run is not general reliability evidence.

**Not yet verified:** repeated or general live Researcher → Analyst → Critic
reliability, live verification of the prose-completeness candidate, actual
model quality, live LangSmith tracing, live Streamlit execution,
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
capabilities. No CLI or console control enabling live inference is added. The
operations console exposes one synthetic demonstration that uses this exact
factory substitution with the module-level synthetic gateway; see
[Operations Console](OPERATIONS_CONSOLE.md#canonical-live-workflow-demonstration-synthetic).

## Content and authority

Each prompt explicitly declares its role, a concise natural-language role
contract with one schema-valid example (see the Item 46 section below), no tools,
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
schemas enforce types and field bounds, and their prose fields require terminal
punctuation (see the completeness section below). Analyst citations must refer
to actual research findings. Unknown authority/tool/routing fields fail validation. The
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

## First authorized live run and Item 46 remediation candidate

### First live run (2026-10-14): failed closed

One human-authorized canonical run used the committed path at
`e0dcb54f50060a264c240a3c1fdbc09468ce49b2`, local Ollama and the exact
`qwen2.5-coder:7b`. The Researcher's first reply failed `ResearchOutput`
validation; the single authorized repair also failed. The workflow failed closed
with `malformed_output`: 2 real calls, 1 repair, 0 retries, no Analyst or Critic
call, worker reaped, no completed evidence, repository unchanged. Raw output is
intentionally not retained, so **the exact historical malformed cause is
unknown**. Offline diagnosis identified several plausible modes (Markdown fences
or prose around JSON, extra comparison/critique fields from the broader task,
bound violations, length truncation) without proving any one of them.

### Approved remediation (offline candidate, not live-verified)

Human decision: "Approved. Implement Item 46 with reason codes internal only."

1. **Prompt contracts.** Each role prompt now requires exactly one bare JSON
   object, prohibits Markdown fences and prose before or after it, forbids
   unlisted fields, states the role's fields, types and bounds in plain language,
   and carries one schema-valid application-authored example. The full machine
   schema is no longer duplicated in the prompt. The Researcher is told that
   comparison, critique and other deliverables in the task belong to later
   roles, resolving the conflict with the findings-only `ResearchOutput`.
   Worst-case prompts (maximum task, maximum prior content, longest repair
   wording) remain within the accepted 8,192-character bound.
2. **Application-owned structured output.** `LocalModelGateway` sends Ollama's
   top-level `format` equal to `role_schema(request.role).model_json_schema()`,
   derived from the authoritative closed Pydantic contract for the
   application-chosen request role. `ModelRequest` and the `ModelGateway`
   protocol are unchanged: no format, schema or provider-option field exists for
   a caller or model to supply. This only constrains generation. Strict JSON
   parsing, duplicate-key refusal, closed-schema Pydantic validation and the
   Analyst citation check remain authoritative; nothing is stripped, extracted,
   relaxed or coerced.
3. **Provider length stop.** `done_reason` remains optional (absence preserves
   the previously accepted envelope), but when present it must be exactly
   `"stop"` (normal) or `"length"` (the `num_predict` limit was reached). A length
   stop maps to the existing `output_too_large` category: closed, no repair, no
   retry, no next role, no limit increase. Any other value or type is an
   `unexpected_provider_failure`. Synthetic fixtures previously used placeholder
   `done_reason` strings; they now use `"stop"`, matching the stricter contract.

**Internal reason codes.** `live_validation` classifies malformed replies into a
closed internal set derived from actual parser/validator boundaries: `not_json`,
`not_object`, `duplicate_key`, `extra_field`, `missing_field`, `wrong_type`,
`bounds`, `invalid_value`, `incomplete_prose` (added by the completeness
candidate below) and `semantic` (Analyst citation). The reason only
selects one fixed application-authored repair sentence. It never appears in
exception text or args, `LiveFailure`, the canonical receipt, live events or any
UI value; `parse_role_output` and `check_analysis` keep their coarse public
behavior. Repair feedback never includes model output, exception text or provider
data, and the repair keeps the same role, selection, task, prior context,
provider schema and single-repair ceiling.

Unchanged: Architecture B+, `LiveAuthorization`, explicit selection, fixed
Researcher → Analyst → Critic topology, process isolation, bounded IPC, minimal
child environment, concurrency 1, zero retries, three normal calls, at most one
repair, never a fifth call, application budgets/deadlines, advisory Critic,
sanitized public failures and evidence classification. Synthetic runs remain
`synthetic_offline`; prior real provider evidence remains separately classified.

## Second authorized live run and prose-completeness candidate

### Run 2: LIVE SUCCESS

Classification: **real local canonical multi-agent execution, post-Item-46,
live success.** One bounded run on the default committed canonical application
path used Ollama 0.40.4 and the exact `qwen2.5-coder:7b`. Researcher, Analyst
and Critic each validated on the first call: 3 real calls, 0 repairs, 0 retries,
49.8 seconds, 1,026 input and 150 output tokens. The worker was reaped and the
repository was unchanged. This is one real Researcher → Analyst → Critic
execution, not evidence of general reliability or model quality.

**Analyst caveat.** The Analyst assessment was exactly 400 characters, its
schema maximum, and visibly ended mid-sentence. The cause is **not proven**; no
provider truncation is claimed, and the text is intentionally not retained here.
Run 2 remains a live success: every authoritative check that existed then passed.
Offline diagnosis showed that validation represented structure and bounds but
not this narrow completeness invariant.

### Approved completeness hardening (offline candidate, not live-verified)

Human decision: a prose role output that ends without accepted terminal
punctuation is repairable through the existing single global repair.

1. **Covered fields.** Each `ResearchOutput.findings` item,
   `AnalysisOutput.assessment` and `CritiqueOutput.rationale`: the prose fields
   the prompts ask to be sentences. Excluded: `AnalysisOutput.supports`
   (integer citations), `CritiqueOutput.advisory_verdict` (closed label) and all
   application-owned identifiers, selections, budgets and evidence.
2. **Check.** `live_contracts._complete_prose` runs after the existing
   visibility check. After skipping any trailing closing quotes/brackets
   (`" ' ) ]` and their common Unicode forms), the last character must be a
   terminal mark: `. ? !` or a small subset of Unicode Sentence_Terminal
   (`‼ ‽ ⁇ ⁈ ⁉`, ideographic/fullwidth `。 ！ ． ？ ｡`). Nothing is stripped:
   trailing whitespace, commas, colons, semicolons, ellipsis characters and
   dangling openers all fail. Reaching exactly the schema maximum is not itself
   a failure; a value below the maximum without a terminal mark still fails. It
   is a deterministic, bounded, provider-neutral invariant with no inference,
   grammar checking or scoring, and it is **not** proof of semantic correctness,
   factual or grammatical quality, or overall answer completeness.
3. **Classification and repair.** The failure is a Pydantic custom error type
   mapped to the internal-only reason `incomplete_prose`, which selects one fixed
   repair sentence: "The previous response ended prose without terminal
   punctuation; write complete sentences." It competes for the same single
   global repair as every other malformed reply. A failed repair, or an
   incomplete later role after the repair was used, fails closed. Publicly it
   remains `malformed_output`; no category, retry, repair, call or fallback is
   added, and three normal calls, at most four calls and no fifth call remain.
4. **Prompt headroom.** Each prose role now asks for concise, complete
   sentences (the Analyst for one concise, complete one-line conclusion) of
   about 75% of the field maximum: about 120 of 160, 300 of 400 and 180 of 240
   characters, finishing well before the maximum. This is guidance only; no
   validator enforces it, and the schema maxima and provider `format` schema are
   unchanged.

**This candidate was offline at acceptance and has since been exercised live
once, in the out-of-policy Run 3 recorded below: all three prose roles passed
the invariant on their first real calls.** All M6-001 through M6-026 statuses
remain Planned. Any further live run requires fresh HITL under the ADR-008
deviation policy.

## Slice 1: application-owned live observation foundation

The uncommitted Slice 1 candidate adds `live_observation.py`, a sibling contract
family separate from deterministic `RunTrace` and its zero-call `Accounting`.
It adds no SDK construction, exporter, transport, metric projection or UI mode.
Independent acceptance remains pending. Verification is offline only; gate
results are recorded below when complete.

The canonical service generates a fresh nonzero trace UUID and root span ID for
each invocation with validated workflow/task linkage. No public trace-ID argument
exists. The ID is bound to lifecycle events and successful `LiveEvidence.trace_id`.
The service rejects runtime results with substituted workflow/task/selection/budget
or a preexisting trace identity. Workflow/task identifiers never authorize work.
Uncorrelatable invalid identifiers remain sanitized input errors, without invented
observations.

`LiveTerminalObservation` contains only fixed runtime/topology, application
identity/provenance, timestamps, monotonic duration, closed outcome/public category,
validated canonical selection, ordered role-completion instants, supervisor
accounting/nullable usage and closed cleanup state. Completion instants are not
role latency. Dispatch counts are not proof of provider completion. Cumulative
role snapshots are never summed. Incomplete usage aggregates remain unavailable;
known per-component totals include repair calls. No-call runs have unavailable
provider usage, not fabricated zeros.

The owning runtime reports supervisor facts only after its existing bounded
cleanup. `reaped` requires a settled process; `not_started` requires no acquired
worker, `failed` represents cleanup failure, and `unknown` preserves unavailable
supervisor evidence. Completion observations require all three validated roles
and confirmed reaping. Cancellation and the existing cleanup/deadline precedence
are preserved. Successful evidence retains the existing runtime duration;
observation duration measures the canonical service boundary, including local
observation overhead. Failure observation has a 302-second representational
ceiling (300-second work ceiling plus 2-second independent supervisor allowance);
values outside it are dropped, never clamped into evidence of bounded success.
OS scheduling remains outside hard real-time guarantees.

The existing observer owns opaque live handles, separate from deterministic
handles. It admits at most 16 active live observations, retains the last 32
terminal observations and the existing last 32 lifecycle events, and returns
fresh revalidated snapshots. Identity linkage is checked before finalization;
forged, cross-observer, substituted and already finalized/abandoned handles are
rejected. Retained/active trace replay is refused. Historical trace tombstones
are not stored without bound: canonical invocation identities are always fresh,
and a stale opaque handle remains unusable after retention eviction.

Local observation construction/serialization/retention failures cannot authorize
execution, alter selection/budgets/validation, create a repair or retry, or replace
execution outcome. Missing or inconsistent observation evidence is dropped with
bounded loss bookkeeping rather than invented success. Missing supervisor facts
on a failure retain established sanitized failure counters but unknown cleanup
and usage. No content-bearing canonical receipt is sent to a sink.

Contracts and explicit projection exclude tasks, prompts, responses, citations,
credentials, environment, endpoints, paths, process details, raw exceptions,
Pydantic diagnostics, internal malformed reasons and arbitrary tags/metadata.
`incomplete_prose` remains internal-only; public classification remains
`malformed_output`. `output_too_large` remains non-repairable. The global repair
limit is one, the absolute model-call ceiling four, transport retries zero.
Injected gateways remain `synthetic_offline`, regardless of selection strings.

This foundation does **not** provide LangSmith live RunTree construction/delivery,
OTel live projection or Streamlit live mode. Those are later integration slices.
Run 2 remains **LIVE SUCCESS**; the out-of-policy Run 3 below has since
completed the workflow on this path. All M6-001 through
M6-026 remain **Planned**. Architecture B+ and dependency files are unchanged.
No end-to-end observability, independent acceptance, release or deployment
readiness is claimed.

### Slice 1 candidate verification (2026-10-16)

Independent acceptance remains pending. Required final offline gates passed:

| Gate | Result |
| --- | --- |
| `uv run --offline --no-sync ruff check module-06` | PASS |
| Complete Module 6 pytest | 2,402 passed, no skips/warnings, 430.08 s |
| Complete root pytest | 4,517 passed, 6 existing skips, 3 existing ChromaDB legacy-embedding-config deprecation warnings, 609.81 s |
| compileall | PASS: Module 6 source/tests, app and all four command paths |

The maintained `test_live_observation.py` contributes 99 new cases over the
accepted 2,303 / 4,418-pass baselines. Tests exercise actual native graph/child
execution with synthetic gateways, strict/frozen contracts, partial role facts,
owned correlation, replay/substitution rejection, bounded retention, call/repair
ceilings, nullable usage, cleanup, cancellation, safe failures, payload exclusion,
and observation isolation. Existing deterministic LangSmith/OTel and semantic
completeness coverage remains in the complete gates. No live evidence is created.

Self-review additionally required completed counters to match the final role
snapshot, rejected fabricated zero provider usage on no-call records, and bound
canonical results to the invocation's workflow/task/selection/budget before
assigning its trusted trace identity. The binding-only runtime stub previously
replayed seeded IDs; it was corrected to return the requested workflow/task IDs
and an uncorrelated runtime result. Its assertions were retained, and dedicated
substitution rejection tests were added. The security-contract inventory now
includes all four sibling contracts with the same mandatory security assertions.

Gate/harness history is retained rather than attributing every failure to the
candidate. The sandbox prevented uv cache persistence and even a minimal asyncio
socketpair from completing; test-owned IPC worked outside it. The initial 81-case
focused run passed there. The expanded focused run stopped at the stale-ID stub
(1 failed, 151 passed), repaired as above. A first complete run stopped at an
unchanged deterministic CrewAI UI timeout (1 failed, 282 passed); the exact test
passed unchanged in 10.98 s under its original 30-second deadline. This supports
an intermittent timing failure, without proving its precise cause. The next run
stopped when the temporary launcher's hard guard intercepted a transitive SDK
`dotenv_values` read before content access (1 failed, 342 passed). The launcher
was corrected to suppress real-path `dotenv_values` as well as `load_dotenv`,
while retaining its read guard. A targeted follow-up exposed missing Windows
AppData folders in the isolated home; creating those test-owned folders resolved
it (the unchanged CrewAI context test passed in 6.98 s). No timeout, assertion,
security control, dependency or source requirement was weakened. The final
complete gates above passed against the unchanged implementation.

The temporary launcher supplied only allowlisted OS variables plus test-owned
home/temp paths and fixed offline flags. It blocked real dotenv reads, external
DNS/connections and known real model/observability ports. Test-owned fixtures,
in-memory transports and ephemeral loopback IPC remained permitted. No real
credential-variable presence was inspected and no real model, Ollama, LangSmith,
Collector, Prometheus, Grafana or hosted-provider request was performed.

SOP assessment, in required order: Requirements—Slice 1 contract implemented,
all source statuses still Planned; Product Experience—typed application API and
retrievable curated records, UI deferred; Real Functionality—actual supervised
native execution with synthetic gateways only; Reliability—bounded execution,
cleanup and local observation isolation tested; Security—closed payload-free
projection and authority/correlation controls tested; Cost—zero added inference,
no billable verification; Evidence—offline gates passed, independent/live
acceptance pending; Deployment—unchanged and unverified by this slice.

## NORMAL budget profile (ADR-008) and evidence-ledger protocol

[ADR-008](adr/008-real-local-canonical-budget-profile.md), human-approved on
2026-10-22, records the named NORMAL budget profile for this canonical
real-local workflow, instance `NORMAL_REAL_LOCAL_BUDGET`: a 200,000 ms
workflow deadline, 45,000 ms per-call timeout, three planned calls, at most
one repair, zero retries and concurrency 1, with the accepted real-local
contract content ceilings unchanged: 4,096-character task text, 4,096-token
provider output limit and a 16,000-byte reply bound. With the output limit at
the contract ceiling, a verbose but schema-valid reply is judged by the
accepted repairable `malformed_output` taxonomy instead of being forced
prematurely into the non-repairable provider-length `output_too_large`
classification; only genuine overshoot of 4,096 tokens or 16,000 bytes stays
closed. The profile is immutable `LiveBudget` data in
`../src/multi_agent_orchestration/live_policy.py`, is imported by no
execution path, and is strictly separate from execution authority: every real
run still requires fresh explicit HITL and explicit `LiveAuthorization`
construction with every budget value stated. The generic 300,000 ms schema
ceiling remains provisional and unchanged, the synthetic console authority
remains 30,000 ms / 5,000 ms with its own separate content envelope, and
timeout remains fail-closed — a timed-out run is never retried or rerun
automatically; another attempt consumes fresh authorization. Deviations from
NORMAL need fresh explicit HITL for that deviation.

Future real-local runs must produce a complete evidence-ledger record that
represents, separately and with nothing left to reconstruction:

1. **Runtime/schema validity** of the supplied budget pair.
2. **Execution consistency**: completion within the actually supplied runtime
   values; actual total duration; calls; repairs; retries; token accounting;
   cleanup/reaped state; per-segment role timing where observable.
3. **Human-authorized budget**: the complete `LiveBudget` the human
   authorized, with the HITL authorization reference/date; if the authorized
   values cannot be established, the record says so instead of inferring them.
4. **Actually-used budget**: the complete `LiveBudget` the runtime enforced
   (identical to the supplied one; recorded explicitly).
5. **Human-authorization match**: a `within_human_authorization` verdict —
   `true`, `false` or `unverified` — with the reason when negative or
   unverified. Runtime budget compliance is never substituted for this
   verdict.
6. **Policy classification**: `authorized_live_success`,
   `out_of_policy_observation`, or a NORMAL-deviation label when applicable.

Runtime/provider version, model identifier and local projection statuses
round out the record. Sensitive recording stays excluded: no prompts, raw
replies, credentials, provider diagnostics or payloads. This ledger lives
here rather than in the runtime schema because the accepted live contracts
are frozen evidence planes, while HITL references, version strings and ledger
classifications are authority/documentation metadata, not runtime-produced
data.

## Run 3: out-of-policy real-local technical observation

Run 3 was performed under an instruction to execute one bounded real-local
canonical run, but the accepted evidence does **not** establish that its
supplied bounds were themselves human-authorized. Its record is separated
below into runtime validity, execution consistency, human authorization and
later NORMAL comparison. The runtime was local Ollama 0.40.7 with the exact
`qwen2.5-coder:7b`.

**A. Runtime/schema validity.** The actually supplied runtime pair was
300,000 ms / 120,000 ms. That pair is schema-valid (`LiveBudget` bounds).

**B. Execution consistency.** The run completed within those supplied values:
one bounded Researcher → Analyst → Critic execution on the committed path;
live record `612ab93b-368f-4775-af2b-ec2338c48bf6`; every role validated on
its first call; 3 real calls, 0 repairs, 0 retries, 1,051 input and 107
output tokens (`no_provider_charge_local_compute`); 64,531 ms result
duration and ~65,125 ms terminal-record duration; worker `reaped`; local
LangSmith, OTel and metric projections all `recorded` with observation
`local`; no external delivery, credential access or hosted provider contact;
repository unchanged.

**C. Human authorization.** The human authorization used to justify the run
did not state numeric deadline or per-call values; the operator applied
300,000/120,000 ms as an interpretation. Human authorization of exactly
those numeric values before Run 3 is **not established** by the available
accepted evidence; there is no invented authorization reference or date, and
none is constructed. `within_human_authorization: unverified`. Runtime and
schema budget compliance (A/B) is **not** proof of human authorization, and
the forensic conclusion stands: Run 3 cannot be accepted as an authorized
live success.

**D. Later NORMAL policy.** Under ADR-008, Run 3 is outside NORMAL because
300,000 ms > 200,000 ms and 120,000 ms > 45,000 ms.

Classification, unchanged: factual real-local technical observation;
`out_of_policy_observation`; not retroactively authorized; not an authorized
live success; no requirement or acceptance advancement. The run is retained
as valid factual evidence whose calibration measurements informed the NORMAL
sizing, as the human-approved derivation itself records. No percentile, SLA
or reliability claim is made; n = 2 real workflow runs and only n = 1 with
per-segment timing.

Corrected derivation note (supersedes the raw segment reading): the
38,622 ms per-call floor included child spawn outside `call_timeout_ms`; the
single observed in-scope call floor is approximately 37.6 s, and the NORMAL
45,000 ms call bound therefore provides approximately 19.6% headroom over
that one in-scope observation. That headroom does not cover the ~31.6%
aggregate cross-run token-rate difference (37.6 × 1.316 ≈ 49.5 s > 45 s); a
sufficiently slower future cold call may honestly time out, fail closed and
require fresh HITL for any further attempt. Run 2's numeric budget was never
recorded and remains permanently unreconstructable; its ~49.8 s aggregate
remains valid while its per-call split is unknown. These limitations are
what force the explicit deviation/HITL and recalibration rules in ADR-008.


## Run 4: Authorized current-path real-local verification

**Evidence classification:** Authorized current-path real-local verification.

Run 4 was one explicitly human-authorized canonical real-local execution on commit `be1edd50e73af12646f48d894bf511800b0030bf` using local Ollama 0.40.8 and `qwen2.5-coder:7b` (observed digest prefix `dae161e27b0e`). The authorization was consumed by this single attempt; no automatic rerun occurred.

| Evidence field | Run 4 observation |
| --- | --- |
| Workflow | LangGraph Researcher -> Analyst -> Critic |
| Terminal outcome | `completed` |
| Human authorization | Explicit in-session one-shot human authorization on 2026-10-22; no separate repository-persisted authorization artifact/reference |
| `within_human_authorization` | `true` |
| Policy classification | NORMAL real-local profile |
| Deadline | 200,000 ms |
| Per-call timeout | 45,000 ms |
| Maximum / actual model calls | 4 / 3 |
| Maximum / actual repairs | 1 / 0 |
| Transport retries | 0 |
| Maximum concurrency | 1 |
| Content bounds | 4,096 input chars / 4,096 output tokens / 16,000 reply bytes |
| Result duration | 48,407 ms |
| Approximate role segments | Researcher 23.11 s / Analyst 12.37 s / Critic 12.61 s |
| Token accounting | 1,104 input / 145 output |
| Role validation | Researcher, Analyst, and Critic validated on first call |
| Prose completeness | Passed for all three role outputs |
| Worker cleanup | `reaped` |
| Terminal observation | `recorded` / trusted local-provider evidence |
| Local LangSmith projection | `recorded`; no external delivery |
| Local OTel trace projection | `recorded`; no external delivery |
| Local operational metrics | `recorded`; no external delivery |
| Provider charge classification | `no_provider_charge_local_compute` |
| Repository integrity | At execution completion, HEAD unchanged; working tree and index clean |

The executed budget exactly matched `NORMAL_REAL_LOCAL_BUDGET`. Runtime/schema compliance is recorded separately from human authority: human authorization was established by the explicit pre-run one-shot authorization, not inferred from successful execution or budget validation.

This evidence does **not** establish production, deployment, hosted-provider, external-observability, reliability/SLA, portability, release, or Module 6 completion claims. Observations remain sparse (three real runs total and two with per-segment timing), Ollama versions differ across runs, the live repair path remains unexercised, and structural/bounds/prose validation is not proof of semantic correctness.

## Run 5: live-model current-path LangSmith delivery verification

**Evidence classification, exactly as independently approved:** "One-run
live-model current-path LangSmith projection and delivery verification
(`unverified_write` receipt); authority-consumption status operator-attested
and not independently confirmed." The word "Authorized"/"authorized" is
deliberately **not** used for this event.

### Recorded successful composition (2026-10-22)

| Evidence field | Run 5 observation |
| --- | --- |
| Runtime | Python 3.12.14; local Ollama 0.40.9; `qwen2.5-coder:7b` only |
| Workflow | LangGraph sequential; Researcher -> Analyst -> Critic |
| Trusted application trace UUID | `e48944ac-1e67-4562-b6e7-e3cab5abbb4c` |
| Workflow / task IDs | `407928fa-2b8e-4ee6-991e-6720db8b922d` / `90b4a3f4-1c17-4623-a3c4-9295578856ad` |
| Root span | `4a64b981459a44c6` |
| Terminal outcome | `completed`; `evidence_source: local_provider_execution` |
| Finalized observation | validated `LiveTerminalObservation` |
| Model calls / repairs / retries | 3 / 0 / 0; concurrency 1 |
| Total duration | 48,438 ms |
| Role segments | Researcher ~27.66 s / Analyst ~9.44 s / Critic ~11.24 s |
| Provider-reported tokens | 1,049 input / 124 output |
| Cost status | `no_provider_charge_local_compute` |
| Role validation | all three roles validated on first calls |
| Worker cleanup | `reaped` |
| Projection trace UUID | `e48944ac-1e67-4562-b6e7-e3cab5abbb4c` — equals the trusted application trace UUID |
| Projected runs | 4 (root + 3 role runs; payload-free) |
| Delivery status / evidence class | `accepted` / `unverified_write` |
| Delivery accounting | planned_runs 4; write_attempts 1 for the recorded successful composition; failure null; external LangSmith requests 1 for the recorded successful composition; read-back requests 0 |
| Delivery destination / project | `https://api.smith.langchain.com` / `module6-verification` |
| Confirmation contract | committed `unverified_write` / HTTP 2xx write contract; **no service-read confirmation exists** for this event |

Credential provenance for the delivery (facts only): source Windows
Credential Manager target `LangSmith-Module6`; process-local
`LANGSMITH_API_KEY` exposure inside the execution composition; credential
value undisclosed; not intentionally persisted elsewhere; process-local value
cleared after the recorded successful composition; no external
OTel/Collector/Prometheus/Grafana delivery in the recorded successful
composition; repository unchanged by Run 5.

### Pre-execution compositions A2 and A6 (authority history)

Two earlier operator compositions preceded the recorded successful one. The
independent Reviewer qualifies the event's authority on their account:

**A2 (PowerShell stdin-mode composition).** Returned zero retained
stdout/stderr: no traceback, no report, no wall-clock timestamp. The exact
failure point cannot be determined. Pre-effect status: **NOT ESTABLISHED.**
The retained evidence does **not** establish that `execute_canonical_workflow`
was unentered, does **not** establish that no model dispatch occurred, does
**not** establish that `deliver()` was unentered, and does **not** establish
that no `POST /runs/batch` occurred. **Therefore a prior model dispatch
and/or a prior LangSmith batch write cannot be excluded.**

**A6 (missing-import composition).** Direct retained traceback:
`NameError: name 'Observability' is not defined`, at the top-level statement
`observer = Observability()` (frame `File "<string>", line 80`). Recovered
source ordering places `execute_canonical_workflow` strictly after that
statement; LangSmith delivery follows only a successful workflow/projection.
Pre-effect status: **ESTABLISHED.** No model inference occurred in A6; no
LangSmith write occurred in A6; the credential was cleared.

**Authority conclusion.** Run 5's authority-consumption status is
**operator-attested and not independently confirmed.** The one-inference and
one-write global bounds are **not independently confirmed**, because A2's
effects are indeterminate. Do **not** claim the recorded successful
composition was necessarily the only effectful composition, and do **not**
claim the LangSmith project contains exactly one Run 5 trace/batch.

### Population and limitations (floor accounting)

Four real runs are **recorded**; four recorded runs is a **floor, not a
proven total**, because an additional undescribed real execution in
composition A2 cannot be excluded. Three recorded runs carry per-segment
timing. Recorded Ollama versions across runs: 0.40.4 / 0.40.7 / 0.40.8 /
0.40.9. The live repair path remains unexercised. No percentile, SLA, or
reliability claim is made, and structural/bounds/prose validation is not
proof of semantic correctness.

### Non-claims

Run 5 does **not** establish service-read confirmation, LangSmith
service-side persistence/visibility, production readiness, production
verification, deployment acceptance, hosted-provider verification,
reliability/SLA performance, portability, release acceptance, M6-014 closure
(M6-014 remains Planned), or Module 6 completion.
