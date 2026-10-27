# Live-Model Vertical Slice

Current follow-on work is documented in
[Live Runtime Enforcement](LIVE_RUNTIME_ENFORCEMENT.md). The Story 1 sections
below record the historical contract milestone; they do not claim that the
follow-on runtime has executed a real model.

## Purpose and Standing

Before Module 6 closes, one real model-backed multi-agent workflow must run end
to end through the production architecture. This is an additive portfolio and
production Definition-of-Done requirement. It is **not** a course-source
requirement: M6-001 through M6-026 are unchanged and all remain Planned.

Architecture B+ stays frozen and needs no amendment. The Model Gateway and the
local execution mode are already part of it. The live path is additive: the
accepted deterministic contracts, services and tests are not modified, because
their literal zero-call and exact-output semantics are intentional claims.

Decisions carried by this slice: the canonical live topology will be the
accepted LangGraph sequential plan (researcher, analyst, critic); a model may
supply content only; application code owns routing, authorization, provider and
model selection, budgets, validation, acceptance and evidence classification;
agents have no tools; the critic's verdict is advisory; one malformed-output
repair per run is allowed inside the hard call total; hosted execution is not
required for closure.

## Story 1: Typed Safety Envelope

Starting state: `feature/module-06-architecture` at
`36b520072f49676d31fbd7e329a17219de35074a`, clean worktree.

Story 1 adds types and pure validation only. **No model has executed.** There
is no adapter, HTTP client, SDK call, credential lookup, LangGraph live
workflow, live service or console change. Nothing in these modules can reach a
model, a provider or the network, and none reads the environment.

| File | Contents |
| --- | --- |
| `src/multi_agent_orchestration/live_errors.py` | `LiveFailureCategory` (12 closed execution categories), fixed wording, `LiveExecutionError`, fixed `LiveValidationError` |
| `src/multi_agent_orchestration/live_contracts.py` | Authorization, selection, budget, model-produced schemas, accounting, evidence, result and failure contracts |
| `src/multi_agent_orchestration/live_validation.py` | `validate_live_data`, `parse_role_output`, `check_analysis` |
| `src/multi_agent_orchestration/model_gateway.py` | `ModelRequest`, `ModelReply`, the one-method `ModelGateway` protocol, `checked_reply` |
| `tests/test_live_contracts.py` | 479 offline tests |

### Authority

`LiveAuthorization(mode, selection, budget)` is the only way to express a live
run. `mode` is the required literal `live-model`; no field has a default.
Its absence is deterministic execution.

**Authority comes from application-owned validation, not from object
identity.** `require_live_authorization` treats its argument as untrusted. It
copies the declared fields of the candidate, its selection and its budget out
as plain data, passes that data through normal `LiveAuthorization` validation,
discards the candidate and returns only the newly validated instance. The exact
semantics are:

- An object made with `model_construct` is neither trusted nor refused for how
  it was made; Pydantic offers no supported way to tell. It is accepted only
  when every copied value passes full validation, exactly as if an operator had
  supplied those values, and it is refused otherwise. The returned authorization
  is always a different, validated object.
- Subclasses, mappings, JSON text, objects holding undeclared state, objects
  missing a declared field and every other value are refused, even when their
  values would be valid. The same rule applies to the nested selection and
  budget.
- Refusal is `authorization_refused`, or `budget_refused` when only the budget
  is not an exact, valid `LiveBudget`. Neither carries any input value.

The function takes no environment, credential or availability input, so a
running model service, an installed model, a configured provider or model name
and a present credential cannot authorize anything. A future service calls it
before any gateway exists. `WorkflowRequest` gains no field.
`ModelSelection(execution_class, provider, model)` is application-owned.
`execution_class` admits only `local_model_inference`; hosted execution is not
representable and would need a deliberate, human-approved contract change.
`provider` and `model` are bounded identifiers and cannot hold a URL. No
contract has a credential, header, secret or free-form metadata field.

### Budget

`LiveBudget` requires every value explicitly; there are no defaults.

| Field | Bound | Basis |
| --- | --- | --- |
| `max_model_calls` | 3 to 4 | Three roles of the accepted sequential plan plus the one repair |
| `max_repair_attempts` | 0 to 1 | One repair per run by design |
| `max_concurrency` | exactly 1 | The sequential plan's concurrency |
| `deadline_ms`, `call_timeout_ms` | 1 to 300,000 | Provisional ceiling; see limitations |
| `max_input_chars` | 1 to 4,096 | Existing `TaskInput` ceiling |
| `max_output_tokens` | 1 to 4,096 | Requested from a provider; not application-enforced |
| `max_reply_bytes` | 1 to 16,000 | Application-enforced read bound; matches the existing child-process output cap |

`max_model_calls` must equal 3 plus `max_repair_attempts`, and one call cannot
outlast the run. Transport retries are the literal 0 in `LiveAccounting`, so no
unbounded retry is representable. No monetary amount is representable anywhere.

### Model-Produced Content

| Role | Schema | Fields |
| --- | --- | --- |
| Researcher | `ResearchOutput` | `findings`: 1 to 3 strings of 1 to 160 characters |
| Analyst | `AnalysisOutput` | `assessment`: 1 to 400 characters; `supports`: 1 to 3 distinct one-based finding indices |
| Critic | `CritiqueOutput` | `advisory_verdict`: `sound` or `needs_revision`; `rationale`: 1 to 240 characters |

Unknown fields are rejected and text must be visible single-line characters.
Public parsing failures never echo rejected input. `parse_role_output` takes the role from the
application, enforces the byte bound before parsing, requires exactly one JSON
object without duplicate keys, and fails closed as `malformed_output` or
`output_too_large` with no reply text and no chained cause. `check_analysis`
and `LiveWorkflowResult` require every cited finding to exist.

### Gateway Boundary

`ModelGateway.complete(request) -> ModelReply` is the whole interface. A
request carries the selection, a planned role, a bounded prompt and explicit
output, reply-size and timeout bounds; it has no credential, tool, fallback or
retry field. `checked_reply` rejects anything that is not an owned reply, a
reply naming a different provider or model than was selected, and text over
the request's byte bound. The gateway neither authorizes nor budgets.

### Evidence and Failure

`LiveEvidence` is application-built and payload-free: identities, the fixed
classification `local_model_inference`, runtime and topology, selection,
budget, `LiveAccounting` (calls, repairs, zero transport retries,
provider-reported usage or `None` for unavailable, and the cost status
`no_provider_charge_local_compute`), duration, the three plan records and an
optional trace identifier. It must match the plan and stay within its budget.
Each plan record is canonicalized at this boundary: a supplied `GraphRecord`
instance is never retained. Only an exact `GraphRecord` is read, only its
declared fields are copied out as plain data and validated normally, and the
result is rebuilt from its own JSON, so subclasses are refused and undeclared
state, primitive subclasses and custom behavior do not survive. The plan
comparison uses canonical JSON text, never a supplied object's equality.
`LiveWorkflowResult` carries the validated content separately; no evidence
field depends on the critic's verdict. `LiveFailure` records a closed category
and truthful call counts with no remote text.

### Non-Disclosure and Nested Trust

Every Story 1 contract derives from one base, `LiveContract`, which is closed
(`extra="forbid"`), frozen, sets `hide_input_in_errors=True` and sets
`revalidate_instances="always"`. Hidden input values are defense in depth:
raw Pydantic error locations can still contain attacker-controlled field names.
A nested contract instance is always revalidated, so a constructed selection,
budget, usage, accounting or content object cannot enter an authorization,
request, reply, evidence or result unchecked. The accepted `GraphRecord`
contract is unchanged and does not carry that configuration, so `LiveEvidence`
canonicalizes its plan records itself, as described above.

**Raw Pydantic construction and validation are internal typed-model primitives,
not the public untrusted-input API.** Raw `ValidationError` objects are untrusted
diagnostics and must never be logged or exposed through `str`, `repr`, `.errors`,
`.json`, exception chaining or other serialization. Structured accessors include
rejected input by default; `include_input=False` still leaves untrusted locations.
It is not a universally safe public format.

Application/service code uses `validate_live_data(schema, data)` for Python data
that will become a concrete non-authority live contract: role content, selection,
budget, usage, accounting, request, reply, evidence, result or failure. The
application chooses the schema; unsupported types and subclasses are refused.
Validation returns a typed, revalidated object or raises `LiveValidationError`
with category `invalid_live_data` and the fixed message
`Live data failed application validation and was discarded.` No rejected values,
locations, diagnostics, payloads or metadata are attached. The raw exception is
not retained as a cause or context.

This data boundary cannot validate `LiveAuthorization` and cannot authorize a
run. Use `require_live_authorization` for canonical authority, `parse_role_output`
for duplicate-key-safe bounded model JSON, `check_analysis` for citations, and
`checked_reply` for the application-request/reply identity and byte-bound check.
Those dedicated boundaries retain their existing sanitized `LiveExecutionError`
categories. Invalid application-selected roles or bounds retain their fixed
`ValueError` programmer-error contract. Raw JSON is not accepted by
`validate_live_data`; provider text must pass the role parser.

Story 2 must consume these boundaries before exposing/logging results. For
example: validate a provider reply with `validate_live_data(ModelReply, data)`,
then call `checked_reply(request, reply)`, then `parse_role_output`. Build
application-owned evidence/failure inputs through the same safe data boundary.
Trusted internal construction may use raw typed primitives, but its raw errors
must remain internal. No live service or runtime enforcement is added here.

### Repair After Independent Rejection (2026-10-13)

Independent review rejected the first candidate for two defects, both repaired
within Story 1.

1. **Authority.** The first report and this document said constructed
   authorization objects were refused. They were not: a `model_construct`
   object with valid values was accepted, and the only test used an invalid
   mode. The boundary also rebuilt the result from nested instances that normal
   construction did not revalidate, so a nested constructed budget with
   self-consistent but out-of-bound values was accepted by the ordinary
   constructor. The boundary now validates plain data only, the semantics above
   are stated exactly, and nested instances are always revalidated.
2. **Disclosure.** `LiveFailure`, `LiveEvidence`, `LiveAccounting`,
   `LiveWorkflowResult` and `ModelUsage` used the accepted base configuration,
   which echoes rejected input in error text. All live contracts now share a
   defense-in-depth base.

82 tests were added and one existing case renamed; none was removed or
weakened. No accepted source or test file, dependency or numeric ceiling
changed.

### Second Bounded Repair (2026-10-13, Independent Acceptance Pending)

Re-acceptance demonstrated that a secret-bearing extra field name appears in
ordinary Pydantic error rendering even with hidden input values. The previous
claim of universally non-disclosing `ValidationError` text was incorrect.
`validate_live_data` and fixed `LiveValidationError` now establish an
application-owned sanitized data boundary. Dedicated authority, role parsing,
citation and gateway boundaries also discard raw exception context. Tests pin
the raw library limitation and check key/value/mixed/nested canaries at safe
boundaries. Accepted deterministic contracts, authority semantics, numeric
ceilings and architecture remain unchanged. This is repair verification, not
independent acceptance or live execution evidence.

75 tests were added; the existing 319 remain and none was weakened. Focused
repair tests: 75 passed. The raw-library reproduction intentionally demonstrates
the limitation; the safe-boundary tests prove sanitized failure behavior across
all 12 supported schemas, including nested data and dedicated boundaries.

Harness notes: one Module 6 run stopped at 266 passed because the synthetic
Windows profile lacked application-data directories needed by CrewAI. One root
run stopped at 545 passed because the restricted PATH omitted Git needed by an
existing Module 3 baseline check. Both were harness/environment issues; complete
reruns used an isolated profile with those directories, an explicit local Git
path, and ignored `build/` basetemp storage. No candidate change accommodated
either failure. Initial repair Ruff findings (generic syntax and test formatting)
were fixed without changing test assertions or quality rules.

### Third Bounded Repair (2026-10-13, Independent Acceptance Pending)

Independent acceptance of the second repair confirmed the sanitized data
boundary and rejected the candidate for one defect: `LiveEvidence` trusted
nested `GraphRecord` instances. `GraphRecord` is an accepted contract without
nested revalidation, and the evidence validator only compared the supplied
records with the expected plan and kept the caller's objects. A constructed
record with correct values kept undeclared state through pickling, copying and
revalidation, and a subclass whose equality always agreed entered evidence with
an off-plan role and sequence and an added payload field.

The repair is additive in `live_contracts.py`; `contracts.py` is unchanged.
Each contribution passes a wrap validator that refuses any model instance that
is not exactly a `GraphRecord` with every declared field, copies only declared
fields out as plain data, runs normal `GraphRecord` validation, and rebuilds
the validated record from its own JSON. Plain data takes the normal validation
path and keeps its ordinary internal error locations. The plan comparison now
compares canonical JSON text.

23 tests were added; the existing 394 remain and none was weakened. They
reproduce both rejected cases through the constructor, `validate_live_data`
and a nested result, and cover invalid constructed values, a missing declared
field, accepted and behaviorless subclasses, equality that must never run,
unchanged plain-data behavior and the unchanged accepted contract.

Reported after the third repair, before the human decision below: Pydantic keeps a `UUID`
subclass instance supplied for the top-level identifier fields of
`LiveEvidence` (`workflow_id`, `task_id`, `trace_id`) and `LiveFailure`
(`workflow_id`, `task_id`). Its true value is validated and serialized, and it
can no longer influence the plan comparison, but the object and any custom
behavior it defines are retained. This was outside the plan-record path and was
not changed by the third repair.

This is repair verification by the agent that made the repair. It is not
independent acceptance.

### Fourth Bounded Repair: UUID Values (2026-10-13, Acceptance Pending)

The human decision treats UUID-subclass retention as the same object-trust root
cause and authorizes this repair. A normal UUID validator may return a caller's
UUID object unchanged; valid serialization alone does not remove subclass state
or behavior from authoritative evidence/failures.

The five fields `LiveEvidence.workflow_id`, `task_id`, `trace_id` and
`LiveFailure.workflow_id`, `task_id` now use a shared annotated UUID value type.
Its after-validator runs only after normal UUID input validation. It reads the
built-in UUID integer slot directly (not subclass attribute access), normalizes
the stored integer with the built-in integer operation, and constructs a fresh
exact `UUID`. No caller repr, string conversion, equality, hashing or pickle
method establishes trust. UUID value is preserved; caller identity, subclass
state and generation-safety metadata are not part of the identifier value.
Existing UUID text/byte syntax and optional `trace_id=None` remain unchanged.

62 tests were added; all previous 417 remain without weakening. They cover all
five fields through direct construction, safe validation and constructed-object
revalidation; ordinary and hostile UUID subclasses; copy/pickle/JSON behavior;
invalid identifiers; and the narrow evidence/failure scalar-retention check.
No additional same-mechanism field was found: numeric/text/container values
are already normalized, enum members are application-owned, live models are
revalidated, and plan records are already rebuilt from canonical JSON.

`model_copy(update=...)` and `model_construct` remain unchecked internal
primitives. They are not validation APIs; data created with them must cross
`validate_live_data` before becoming authoritative. Copying validated objects
preserves exact UUID values; revalidating an unchecked update removes caller
UUID behavior again. Raw Pydantic diagnostics remain internal and untrusted.

The GraphRecord repair, canonical JSON plan comparison, sanitized boundaries,
authority/budget/model-output controls and numeric ceilings are unchanged.
The previously reported 10,966-case plain-data fuzz result remains historical
evidence; this bounded repair does not claim to rerun that independent exercise.
This is implementer repair verification, not independent acceptance. Story 2
has not begun and all 26 requirement statuses remain Planned.

Verification note: the first Module 6 run stopped at 206 passed when an unchanged
CrewAI UI demonstration timed out. The same test passed in isolation (17.48 s),
then the complete fail-fast sequence was restarted without changing the code,
test assertions or deadlines. This is recorded as an environment/timing issue,
not repaired or hidden as a candidate change. The complete rerun results follow.

### Verification (2026-10-13, Python 3.12.14, offline)

| Gate | Result |
| --- | --- |
| Ruff, `module-06` | PASS |
| Module 6 pytest | 1783 passed (1304 existing, unmodified; 479 Story 1) |
| Root pytest | 3898 passed, 6 skipped, 3 existing ChromaDB warnings |
| compileall, Module 6 source, tests and commands | PASS |

Evidence class: deterministic offline repair verification only, independent
acceptance pending. The gateways in the tests are
in-memory doubles. No accepted source or test file was changed.

### Story 1 Limitations at Acceptance

- At Story 1, no model, adapter, live workflow, budget ledger, live observation,
  command or console exists yet; those are later stories.
- Ollama compatibility, token-usage reporting, structured-output support,
  model quality, pricing and hosted support are unverified and not claimed.
- The 300,000 ms deadline ceiling and the content length bounds are provisional
  engineering limits, to be confirmed against an authorized measurement. The
  approved `NORMAL_REAL_LOCAL_BUDGET` profile
  [ADR-008](adr/008-real-local-canonical-budget-profile.md)
  is a named per-policy configuration, not a default: real runs still require
  fresh explicit HITL and explicit authorization.
- The contracts state what a gateway must not do. The follow-on
  [runtime candidate](LIVE_RUNTIME_ENFORCEMENT.md) implements call/deadline
  enforcement with synthetic gateways; actual inference remains future work.

## Provenance Note: Architecture Reconnaissance Deviation

This is a design-process deviation. It is not implementation evidence and not a
candidate security defect. Before the complete architecture brief arrived, the
architecture agent checked whether credential-named environment variables were
present without printing or retaining values, read `.env` only to identify
which credential key names were set, and queried the local Ollama service with
`ollama list`. No model was invoked, no credential value was exposed and no
repository file was modified. The corrected architecture and Story 1 do not
depend on those observations, and Story 1 repeated none of them.
