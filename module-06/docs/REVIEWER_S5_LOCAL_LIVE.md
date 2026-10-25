# S5 candidate: secure private-local live presentation

Baseline: clean `feature/module-06-architecture` at
`5e61cf2bac766eb9c642cf2dd7dbd364ce3ee3e6`, empty index. S1–S4 are accepted;
this candidate implements S5 only, not S6 guidance/closeout or S7 reconciliation.

## Composition and trust

The unchanged default `app.py` entry point has no local execution capability.
Rendering any tab, changing widgets, credentials, environment flags, installed
models and localhost connectivity never create one. Demo remains available with
no live dependencies. A trusted **private-local embedding**, outside visitor
control, may construct `TrustedLocalRuntime(posture="trusted-private-local")`
and supply it via `trusted_local_context(runtime)` around each cockpit render.
The context resets after use and is not Streamlit session state or an environment
variable. Reuse one runtime for that private embedding's lifetime; its
nonblocking lock prevents simultaneous operations. The constructor performs no
readiness probe, credential lookup, inference or authorization.

This seam asserts an already trusted caller/runtime; it does not authenticate
public visitors or implement a deployment-compatible authority boundary. The
embedding must restrict access to trusted private operators. Do not expose such
an embedding as a public app. No automatic launcher enables it. The stock/public
entry point never supplies it, regardless of server credentials or model access.
Missing provider/model prerequisites fail at the accepted execution boundary;
rendering does not fabricate readiness.

`app.py` derives its S1 `LiveCapability` per render from
`console.local_live_capability()`: `local_live_available` is true only while an
injected trusted runtime is present. S1's descriptive
`deployment_compatible_authority_verified` field is preserved for
compatibility, but its boolean no longer enables public availability. Public
live is always unavailable in the currently accepted architecture. Implementing,
independently verifying and explicitly enabling a future public identity/secret/
fresh-authorization boundary requires separate work; setting flags is insufficient.
The two S1 test assertions that formerly equated that boolean with availability
are deliberately strengthened to enforce this requested S5 follow-up. The local
availability semantics remain unchanged.

## Fresh execution-scoped authority

Only the explicit **Run authorized local live workflow** action invokes
`ConsoleSession.run_authorized_local`. The application chooses a fixed bounded
task; there are no local provider/model/budget/endpoint/task/secret input widgets.
The caption states that this action authorizes one execution with the displayed
NORMAL profile. No sticky checkbox, prior confirmation or historical success is
authority. The UI itself constructs neither authority nor orchestration.

The application boundary issues a new `LiveAuthorization` at the action's call
site. ADR-008's `live_policy.py` remains immutable policy data with no factory or
default authority. The S5 mechanism binds its ephemeral grant to an exact runtime
owner and newly generated workflow/task UUIDs. It permits at most one outstanding
grant, expires it after 30 monotonic seconds, and requires exact object identity;
a copied/foreign/stale/replayed grant refuses. Consumption clears the pending
reference and grant's authorization **before** validation/execution. Failed,
timed-out or cancelled execution cannot reopen it. A second action creates fresh
authority. No grant, nonce, authorization, credential/client or approval is ever
put in Streamlit session state. This is an in-process private-operator mechanism,
not a durable or distributed authorization system.

The exact values are explicitly stated at the execution authorization call site;
production code does not import/consume the named policy object. Offline tests
compare the newly constructed budget with accepted `NORMAL_REAL_LOCAL_BUDGET`:
200,000 ms overall; 45,000 ms per call; 3 expected / 4 maximum model calls;
1 repair maximum; 0 transport retries; concurrency 1; 4,096 input characters;
4,096 output tokens; 16,000 reply bytes. Selection is fixed Ollama /
`qwen2.5-coder:7b`. No provider/model escalation or automatic retry/rerun exists.
These are accepted tight bounds, not a runtime availability or SLA promise.

## Workflow, evidence and failure

With no injected test executor, the service calls the accepted
`execute_canonical_workflow` without a gateway override, preserving its existing
local-model gateway, role validation, supervisor budgets and cleanup. No second
workflow or secret manager exists. BYOK is explained as runtime-supplied
connectivity; S5 never asks for, discovers or uses a credential. S5 deliberately
does not compose optional external delivery: no write authority is requested or
implied by the execution action.

Receipts are revalidated, correlated with application-owned IDs and checked for
local provenance and exact profile/selection. Success also requires a correlated
finalized terminal observation with matching trace/call/repair facts. Model prose
never becomes presentation evidence. Only counts, timings, token availability,
role-validation count, cleanup, correlation IDs, outcome and local projection
states enter the closed `CurrentLocalRun` model. Unknown values remain unknown.
Canonical failures keep the accepted closed `LiveFailureCategory` verbatim
(`category`) beside a coarse closed `failure` value; the page renders the
accepted fixed `failure_text` plus fixed actionable guidance
(`failure_guidance`), never diagnostics. `budget_exhausted` is reported as
itself, not as a provider failure. Unexpected errors
are sanitized at the presentation boundary. Raw diagnostics/cause objects are
not retained or rendered. Failure replaces the prior current attempt; historical
records cannot fill the gap. Demo and specialist tabs remain independently usable.

The console retains one JSON presentation packet and revalidates it on every
read; malformed/extra fields or an invented `service_read` claim clear it.
`clear()` removes it. Rerenders display this packet without executing again.
The view uses S1 taxonomy: `canonical_real_local`, `local_provider_execution`,
`fresh_execution`, `not_sent`; unavailable intent carries no execution provenance.
Current packets have no operational classification or service-read confirmation.

Finalized observations may pass through accepted local LangSmith formatting,
OTel projection and live metric collection only. Each projection is failure
isolated and its provider/window closes locally. There is no LangSmith delivery,
OTLP delivery, readback, Prometheus/Grafana query or inferred current health.
S3 and S4 retain their separate explicit inspection semantics.

## UI and bounded follow-ups

The Live / BYOK tab states what Live does, how it differs from deterministic
no-key Demo, the trusted-operator-only and public-unavailable postures,
credential = connectivity only, fresh authority per click, the expected
evidence and what a completed run demonstrates. The default unavailable notice
is a caption, not a warning, so accepted page-wide warning semantics are
unchanged. A collapsed "Recorded historical real-local runs (not current)"
panel shows Runs 3–5 with their exact accepted classifications, `source:
recorded_historical`, and inert reference text (Run 4: `none recorded`); it is
separate from, and never substitutes for, the current attempt.

All dynamic current facts are closed values rendered with native text/JSON;
no model HTML, commands, tools or raw output is rendered/executed. Accepted Run 4
still has no curated identifier. Run 5 remains historical `unverified_write` with
its exact accepted classification, now displayed without truncation. The static
LangSmith project/destination facts are inert text. "Holder-service" wording was
replaced by "service observation". Unavailable inspection wording now explicitly
states that this page supplies no read capability, so no read was attempted
and the state is not a failed read (true for `app.py`, which never passes a
provider); no S4 data field changed. The `TraceReadProvider` docstring now says
explicitly that it is a trusted-caller seam, never reviewer input. The unused
`Exploding` helper in the untouched S4 test is deferred to S6. Status
chronology is clarified without requirements/traceability reconciliation.

## Offline tests and A–AF coverage

`test_cockpit_local_live.py` uses only a fake canonical-boundary executor. Its
hostile but schema-valid model prose is never rendered/retained. The production
canonical function and external delivery methods are blocked by an autouse guard,
except the specific default-composition test that replaces canonical with a fake.
Existing Module 6 network/provider guards remain active. A separate isolated
AppTest blocks live-family imports to verify deployable default rendering.

| Test group (function suffix) | Requirements attacked |
| --- | --- |
| `default_render_and_credentials_never_enable_live` | A–H, O, Q, AF: no render execution/discovery, Demo/default/public posture, no secret/control fields |
| `explicit_click_once_rerender_second_click_and_clear` | H–K, N, P, R–V: one call, distinct fresh authority, profile, clear, safe current state |
| `stale_replayed_forged_authority_is_rejected` | L–M, S–T: stale, consumed, copied, foreign and altered authority |
| `intent_required_context_not_hostname_and_no_authority_at_construction` | D–H: explicit trusted caller context, no inferred connectivity authority |
| `failed_attempt_replaces_success_without_retry_and_demo_survives` | T, W–X: bounded errors, no stale/historical substitution, Demo usable |
| `profile_display_and_public_verified_flag_fail_closed` | E, Q–R: exact NORMAL display and no boolean public authority |
| `projection_failure_never_changes_workflow_or_claims_delivery` | U–V, AC: projection errors isolated, no service-read/delivery upgrade |
| `canonical_failure_taxonomy_is_sanitized_and_never_retried` | W: timeout, authorization/budget refusal, malformed output, service/connection failure |
| `default_runtime_reuses_canonical_service_without_gateway_override` | I, S: production composition calls accepted default gateway boundary once |
| `historical_exact_classes_and_no_unsupported_run4_identifier` | X–AB, AE: immutable historical vocabulary, Run 4 absence, S3/S4 controls, no unsafe HTML |
| `corrupted_current_state_cannot_create_delivery_or_keep_payload` | N, P, V, AC: independent payload and delivery-forgery attacks |
| `deployed_render_imports_without_live_dependencies` | A, AD, AF: actual isolated default AppTest render with live imports blocked |
| `real_trusted_embedding_seam_enables_only_explicit_once` | D, H–K, N, P, AF: real `trusted_local_context` embedding script around `app.py`, no monkeypatched discovery |
| `session_state_never_holds_authority_after_success_or_failure` | N, P, V: object-graph walk of session state finds no authorization, grant, runtime or payload |
| `live_tab_offers_one_action_and_no_execution_configuration` | O, Q: no input widget of any kind in the Live tab; one action button |
| `no_combination_of_capability_flags_enables_public_live` | E–G: every flag combination keeps public live unavailable |
| `failure_keeps_accepted_category_and_renders_fixed_guidance` | W, V: accepted category verbatim, fixed text and guidance rendered |
| `every_closed_failure_has_fixed_guidance` | W: bounded guidance for each closed failure |
| `busy_runtime_refuses_concurrent_consumption` | I, T: concurrent attempt runs nothing |
| `current_result_never_claims_service_read_or_operational_health` | AC, X, Z: local projection only; Run 4 has no identifier; S3/S4 state untouched |

Compatibility suites additionally exercise S1–S4 and the existing console/live
boundaries unchanged, except the explicitly strengthened S1 public-flag assertions.

## Validation and limits

Fail-fast gates (2026-10-25): Ruff `check .` clean; focused S5 **36 passed**;
S1–S4 cockpit **65 passed**; live runtime/observability/canonical/local
gateway **1,069 passed**; console/app/console-live compatibility **134
passed**; complete Module 6 **2,764 passed**; compileall clean; candidate
whitespace/line-ending checks clean. A non-gate diagnostic run before the
formal sequence showed one CrewAI demonstration `timed_out` under concurrent
load (the established environment timing flake); it did not recur in the
formal console or full-suite gates.

No real inference/provider/LangSmith/telemetry/query/credential/container activity
has been performed by the Builder. No root full-suite closeout, S6 or S7 work is
included. No deployment, release, completion or requirement advancement is claimed.
Actual live verification requires separate fresh human authorization after
independent review. The S5 candidate is not independently accepted.
