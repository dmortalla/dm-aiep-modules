# Live Observability Slice 2 — implementation candidate

Baseline: `de49101e219ad5809d0dcf16e740eee9e6bf1209`, on
`feature/module-06-architecture`. Architecture B+ and Slice 1 remain unchanged.
This additive capability supports M6-014/M6-016 evidence without changing any
source requirement, requirement status or accepted deterministic trace contract.
Independent acceptance remains pending.

## Operation and ownership

`live_langsmith.project_live_observation(terminal)` is pure offline projection.
It requires an exact terminal contract and revalidates nested facts and roles.
Projection alone does not establish finalization ownership or delivery.

Trusted application code may construct `LiveLangSmithDelivery` with the existing
explicit `LangSmithDeliveryConfig(mode="langsmith-live", max_traces=1)`.
After awaiting canonical workflow termination (including its cleanup), call
`deliver(observer, terminal.trace_id)`. Delivery selects and revalidates a record
from the exact application's finalized Slice 1 retention; it cannot accept an
arbitrary projection, vendor run, workflow result or active observation. A UUID
selects an existing observation; it never overrides its identity. Missing,
expired or malformed observations refuse before transport. Workflow/event
adapters do not invoke this delivery API. Operators must not install it inside
inference callbacks or invoke it while the canonical coroutine is running.

The root run is `module6.workflow`; its run ID and trace ID are the application's
existing nonzero trace UUID. Up to three children are `Researcher`, `Analyst`,
`Critic`, following validated canonical order. Child UUIDs are stable ordinal-tagged
derivations of that trace UUID and application span IDs. Child start/end times
are equal completion instants: no role latency is invented. No model-call spans
are added. Root failure text is only the closed outcome, never exception text.

Every `dotted_order` timestamp is the corresponding observed start/completion
at supported microsecond precision. The root uses the trusted trace UUID.
Children extend that exact parent path by one timestamp-plus-child-UUID segment.
The SDK's pure formatter constructs these segments. Equal observed times remain
equal; no logical timestamps, shifts or epoch substitution remain.

The UUID component provides the non-temporal tie break. Each child uses a
UUID5-derived namespace/span seed with its leading byte replaced by validated
sequence 01/02/03; the remaining 120 bits, including UUID version/variant form,
are retained. The UUID in the segment is exactly the emitted child run ID.
This necessarily changes the earlier candidate's projected child IDs: SDK
parsing treats the suffix as the run's identity, not an independent sort token.
The application trace UUID and application span IDs are unchanged. The same role
keeps its projected identity across partial/full prefixes regardless of neighbor
timestamps. No identity is randomly regenerated to obtain a favorable order.

Fixed `dotted_order_semantics` metadata is `observed_time_sequence_uuid`.
Observed start/end times, role/workflow duration and application evidence remain
unchanged. Each role run still has zero duration. The SDK's `trace_start_time`
equals the observed root start truncated to its microsecond precision, including
at the serialization boundaries. This is verified against the SDK property,
not inferred from a metadata label.

## Payload, security and authority

Every input/output is `{}` and every event list is empty. Only explicitly
constructed application fields are serialized: fixed runtime/topology, source
provenance, trusted IDs, closed outcome/category, bounded counters, nullable
usage, duration and cleanup. Tags are fixed; provider/model names are omitted.
No task/prompt/response/role content, exception text, internal reason, credentials,
environment values, paths, URLs or arbitrary metadata enters the batch.
Malformed nested instances and injected fields produce the existing sanitized
`LiveValidationError`, with no rejected-value diagnostics.

Application execution evidence, terminal observation, projection and delivery
result remain distinct. A projection cannot authorize execution, alter selection,
routing or budgets, change workflow outcomes or cause additional model calls.
Delivery failures return closed classifications and never log exceptions.
Synthetic execution provenance stays synthetic even if a later write succeeds.

## Transport and resource bounds

One batch contains one to four runs, at most 8,192 bytes. An adapter has one to
three lifetime write attempts and never retries an attempted trace, even after
failure. Its locked attempt set retains at most three UUIDs and is never evicted.
No completed payload/result cache or background queue is added. Up to three
active/stalled workers retain their bounded batches until exit; terminal
retention remains Slice 1's 32 records. Concurrent calls cannot bypass the budget.
`write_attempts` counts claimed application attempts, including admission failures;
it does not claim a network request occurred.

The production path is lazy and available only through explicit configuration
and finalized selection. It uses the already-installed Requests transport and
the existing fixed LangSmith batch endpoint/project. It sends one POST with
zero retries, redirects disabled, environment routing/netrc/proxies disabled,
5-second connect and 10-second read socket timeouts plus a separate 15-second
application deadline covering DNS and complete transport cleanup, streamed reply
disposal and no reply-body access. Credential lookup/format validation occurs only inside that
explicit path; neither presence nor projection authorizes a write. No dependency,
SDK client startup, environment discovery or default exporter is introduced.
Projection lazily imports only the installed SDK's pure dotted-order formatter;
it does not construct a client or use SDK-produced metadata as the batch payload.

An injected `LiveBatchTransport` is trusted bounded test infrastructure and is
always classified `synthetic_transport`. Production write responses are labelled
`unverified_write`: a 2xx is only transport acceptance, not proof of persisted
runs or live vendor verification. Results never claim service readback. Optional
readback is deferred; any future verification API must require separate explicit
invocation with fixed trace identity, bounded requests/bytes/time and sanitized
response validation. No automatic readback or inference retry exists here.

## Maintained evidence and Definition of Done

`tests/test_live_langsmith.py` verifies topology, correlation, empty payloads,
nested injection rejection, malformed IDs/roles, truthful partial outcomes,
nullable usage, explicit authorization, finalized ownership, bounded retention,
concurrency, safe transport failures and the fixed intercepted production request.
Actual canonical LangGraph execution against synthetic gateway replies verifies
cleanup before delivery and unchanged execution evidence/model-call accounting.
Existing tests verify fresh per-invocation IDs and deterministic compatibility.

- Requirements: additive projection/delivery candidate; no source reinterpretation.
- Product experience: typed post-workflow API; UI reviewer projection is deferred.
- Real functionality: guarded transport path implemented; only offline/intercepted
  evidence is obtained in this story.
- Reliability: bounded batches, attempts, retention and failure classifications.
- Security: owned finalized lookup, closed projection, credential/payload exclusion.
- Cost: no implicit activity; no additional inference calls/retries; explicit
  operator delivery budget. Local tests consume compute only.
- Evidence: native gates recorded below; independent acceptance pending.
- Deployment: no deployment or live vendor verification claimed. Later authorized
  service compatibility/readback and integration remain unverified.

This slice does not change Streamlit, OTel, runtime/provider code, Modules 1–5,
deterministic LangSmith or the existing Slice 1 contract/lifecycle.

## Verification

Python: repository `.venv`, Python 3.12.14. Native gate results are recorded
after the fail-fast sequence completes.

The first sandboxed focused run had 63 passing tests and two pytest temp-directory
setup errors. A retry using documented ignored `build/` basetemp storage stalled
at the subprocess integration cases and was interrupted. The identical focused
suite outside the sandbox passed all 65 tests in 12.18 seconds with the maintained
network/default-provider guards enabled. No test assertions or deadlines were
changed to accommodate the sandbox. This is environment verification evidence,
not a candidate repair or live service verification.

The first full Module 6 run reported 2,469 passed and one failure in 643.59 s:
the unchanged CrewAI console demonstration timed out. The repository already
documents this same timing issue in `LIVE_MODEL_SLICE.md`. That exact test passed
unchanged in isolation (9.16 s). Ruff and focused tests were then restarted:
Ruff passed and all 65 focused tests passed in 3.62 s. The full gate was restarted
with `-x`; no deadline, code, assertion or quality rule was weakened.

The restarted full gate stopped after 1,723 passes in 344.08 s at the unchanged
`test_stalled_parent_repeatedly_reaps_before_timeout_propagates[hang]` test.
The worker did not dispatch within its 2,000 ms budget, so the test's synchronized
dispatch precondition failed. This exact test also failed unchanged in isolation
in 8.34 s; it had passed in the first full run. This is evidence of baseline
runtime/harness timing instability, not evidence that Slice 2 altered runtime
behavior. The isolated test imports no Slice 2 adapter and all tracked baseline
source/test files remain unchanged. The Module 6 gate is nevertheless failing;
no successful full-suite gate is claimed. No further repeated full runs or
unrelated runtime/test repairs were performed.

| Gate | Latest result |
| --- | --- |
| `.venv/Scripts/python.exe -m ruff check module-06` | PASS |
| Focused pytest, `tests/test_live_langsmith.py`, `-q -x` | 65 passed, 3.62 s |
| Full Module 6 pytest, `-q -x` | FAIL: 1 failed, 1,723 passed, 344.08 s |
| Root pytest | Not run: earlier gate failed |
| Relevant compileall | Not run: earlier gate failed |
| Security/isolation | Focused boundary tests passed; maintained standalone test passed in first full run; baseline tracked files unchanged |

Candidate implementation is available for review, but required validation is
incomplete. Acceptance, release and production readiness are not declared.
No external network calls, real model inference or vendor calls occurred.
Native tests used synthetic gateways, intercepted HTTP, and test-owned loopback
IPC/HTTP. No real credential values were inspected or reported. Test credential
values were synthetic and overwritten by the maintained tests.

Final candidate consists of this document, `src/multi_agent_orchestration/live_langsmith.py`
and `tests/test_live_langsmith.py`, all new files under Module 6. Nothing was
staged or committed; branch and HEAD remain at the required baseline.
All evidence is deterministic/synthetic offline evidence. No model inference,
Ollama, OpenAI, LangSmith or other external service calls are authorized here.

## Independent rejection and bounded ordering repair (2026-10-18)

Independent review rejected the original candidate for a real ordering defect.
Distinct role completions at 2, 3 and 4 nanoseconds all projected to the same
microsecond. `dotted_order` then sorted their UUID suffixes, allowing the trace
`00000000-0000-0000-0000-000000000001` to show Researcher, Critic, Analyst.
The earlier test checked list construction order, not downstream dotted-order
sorting, and missed the defect. Earlier green gates are historical evidence of
that insufficient test suite, not acceptance or proof of correct ordering.

The repair changes only the child's logical sort clock and adds the fixed
metadata needed to explain its semantics. It does not regenerate or reshape
child IDs, alter observed timing, add latency, change validated roles, or touch
execution contracts/runtime code. Sorting timestamps are strictly increasing
within the validated prefix, independent of UUIDs. Missing roles are not added.

The maintained regression has 18 cases: two time origins (small nanoseconds and
realistic epoch), three completion patterns (distinct submicrosecond instants,
equal instants, and adjacent microsecond buckets), and one/two/three-role
prefixes. Each case exercises eight fixed UUIDs including the reviewer's UUID,
plus eight fresh UUIDs. It finalizes the observation through owned retention,
uses the real projection, sorts root and children by `dotted_order`, and checks
the canonical prefix, empty payloads, unchanged zero-duration observed times,
correlation, deterministic repeat projection and unchanged retained evidence.
The old implementation fails the sorted-order assertion for the reviewer's
collision; the new clock prevents UUID-based tie ordering.

Post-repair validation uses the repository Python 3.12 environment, native
pytest, existing offline guards and fresh ignored `build/` basetemp locations.
Only these three untracked candidate files are within repair scope. All earlier
red gates above remain red historical results. The supplied controlled timing
A/B evidence (candidate present 1 PASS / 2 FAIL; absent 2 PASS / 1 FAIL) concerns
the unrelated stalled-parent test, not this confirmed projection defect.

| Post-repair gate | Result |
| --- | --- |
| Ruff, Module 6 | PASS |
| Ordering regressions | 18 passed, 65 deselected, 0.39 s |
| Full Slice 2 maintained tests | 83 passed, 4.25 s |
| Slice 1 observation tests | 102 passed, 40.60 s |
| Full Module 6 pytest | RED: 2 failed, 2,486 passed, 456.24 s; exact known baseline timing nodes below |
| Root pytest | Not run: full Module 6 prerequisite failed |
| Relevant compileall | PASS, exit 0; independent syntax check, not an override of the red pytest gate |

The post-repair full gate failed at these exact nodes:

- `module-06/tests/test_console_app.py::test_actual_accepted_demonstrations_run_through_ui[CrewAI collaboration]`:
  expected `Outcome.COMPLETED`, received `Outcome.TIMED_OUT` at line 55.
- `module-06/tests/test_live_execution.py::test_stalled_parent_repeatedly_reaps_before_timeout_propagates[hang]`:
  `assert not task.done(), "Workflow ended before synchronized dispatch"` at
  line 572 failed because `task.done()` was `True`; the task held
  `LiveRuntimeError('The live run exceeded its deadline.')`.

These are the previously evidenced unrelated timing cases, not failures of the
new ordering regression. The committed baseline records the CrewAI timeout in
`LIVE_MODEL_SLICE.md:309–313`; the supplied controlled A/B evidence reproduces
the exact stalled-parent failure with the candidate absent. No tracked Python
code imports the new projection, and these tests do not execute it. All 83
Slice 2 tests and all 102 Slice 1 observation tests passed in the full run as
well as their focused runs. No timeout, assertion, test selection or baseline
runtime code was changed. The red full-gate result is preserved without retries
to obtain a green full gate. Root pytest was not run. Compileall was the
independent non-execution gate continued under the prior authorization for
known baseline instability; its success does not make full pytest green.

Final scope remains exactly the three untracked Slice 2 files, on the required
branch and HEAD, with no tracked/staged changes or commits. No real inference,
LangSmith delivery/readback, Ollama/OpenAI contact or external/vendor call was
performed. Maintained tests used synthetic gateways, intercepted transport and
test-owned loopback only. The ordering regression is repaired; overall test
validation retains the known baseline instability and the root gate is pending.

Live service compatibility/readback remains unverified. No independent acceptance
or production readiness is declared; the repaired candidate requires a new
independent adversarial review.

## Second independent rejection and boundary-safe repair (2026-10-18)

Historical second repair: subsequently rejected for false SDK trace start time.
Its parsing/sorting checks below were insufficient; the current design is the
SDK-supported third repair described at the end of this document.

The first ordering repair above was independently rejected at datetime's upper
representable boundary. The exact valid observation starts at
`253402300799999999000` ns, completes roles at +1/+2/+3 ns, and ends at +4 ns.
All observed timestamps serialize to `9999-12-31T23:59:59.999999+00:00`.
The first child succeeded, but adding one microsecond for the next logical key
overflowed datetime. Two/three-role projections failed and delivery refused as
`invalid_observation`. The first repair's green focused gates did not cover
that case and do not establish independent acceptance.

The replacement sets the root sort component to epoch ordinal 0 and uses only
the validated sequence for child ordinals 1/2/3 at that same epoch. It never
advances, clamps, subtracts
from, or otherwise modifies an observed timestamp. There is no accumulated
clock or UUID-dependent tie break. All root/child identities are unchanged.
The root's timestamp-shaped sort component changes to ordinal 0, keeping the
entire logical path parent-before-child, consistent with the installed SDK's
ordering convention. One-, two- and three-role prefixes retain exact membership.
Observed timing serialization and its pre-existing range are unchanged.

`test_dotted_order_datetime_boundary_projects_and_delivers` adds six cases:
three nonempty prefixes at the exact upper reproduction and at the minimum
admitted start stamp of 1 ns. Each uses reviewer UUID 1, fixed UUID 2 and two
fresh UUIDs. It finalizes the observation, sorts the real projected records,
checks canonical names and exact unchanged observed times, verifies zero role
duration and unchanged workflow duration, parses the logical timestamp/UUID
components using the installed SDK's grammar, checks deterministic repeat
projection, and fake-delivers one batch. It checks synthetic classification,
replay refusal and unchanged retained evidence. The 18 earlier collision cases
remain unchanged and passing. No production/test baseline file is modified.

The ordinal construction is total over every sequence admitted by the contract.
A separate existing representability mismatch remains: `Stamp` has no upper
bound, whereas observed datetime serialization and the existing
`test_pure_projection_refuses_mappings_and_unbounded_timing` reject dates beyond
datetime.max. The human explicitly authorized preserving that existing observed
serialization range for this ordering repair. No range restriction is introduced,
and no support for unrepresentable observed dates is claimed.

Validation uses native offline tests with fresh ignored build basetemp storage.
Initial Ruff found a shadowed test import and an overlong assertion; both were
corrected without changing test requirements. Ruff passed before the restarted
boundary regression gate. Earlier rejection and failed-gate history is retained.

| Second-repair gate | Result |
| --- | --- |
| Ruff, Module 6 | PASS |
| Exact upper/lower boundary regression | 6 passed, 83 deselected, 0.25 s |
| Existing collision ordering regressions | 18 passed, 71 deselected, 0.39 s |
| Full Slice 2 tests | 89 passed, 3.31 s |
| Slice 1 observation tests | 102 passed, 41.30 s |
| Full Module 6 pytest | RED: 1 failed, 2,493 passed, 527.10 s |
| Root pytest | Not run: Module 6 prerequisite failed |
| Relevant compileall | PASS, exit 0; independent syntax gate only |

An earlier full Slice 2 attempt stopped at 86 passed / 1 failed in 16.24 s:
`test_after_actual_synthetic_workflow_failure_cannot_change_execution[happy]`
observed zero synthetic gateway calls instead of three. This happened during
workflow execution, before projection. The exact unchanged test passed in
isolation (3.47 s). Its runtime precondition failure is separate from the
confirmed ordering overflow; a specific infrastructure root cause was not
established. After the root ordinal refinement, Ruff and both ordering gates
were restarted and all 89 Slice 2 tests passed without changing the integration
assertion or its deadline. The earlier red result remains recorded.

The final full Module 6 run failed only at
`module-06/tests/test_console_app.py::test_actual_accepted_demonstrations_run_through_ui[CrewAI collaboration]`:
line 55 expected `Outcome.COMPLETED` but received `Outcome.TIMED_OUT`.
This matches the timing symptom already recorded in committed
`LIVE_MODEL_SLICE.md:309–313` and earlier runs, but the exact cause of this
occurrence was not independently established. It is not relabelled PASS or
automatically excused. No tracked Python file references/imports this candidate,
and this console path does not execute the live projection. All 89 Slice 2 and
102 Slice 1 observation tests passed in the full run, including the synthetic
workflow test that failed earlier. No current evidence implicates the ordinal
construction in the console timeout. No test was skipped, weakened, given a
longer deadline or repeatedly rerun to obtain a green full gate. Root pytest
remains unrun. Compileall checks syntax independently and does not override the
red full pytest gate.

Final repository state remains the required branch and HEAD with exactly the
three untracked candidate files, no tracked/staged changes and no new commits.
The exact upper-bound observation now projects and fake-delivers successfully
for every nonempty canonical prefix without changing observed timing. The
minimum boundary and earlier UUID/collision tests also pass. The candidate is
prepared for fresh independent adversarial review with the red baseline-pattern
gate and pending root gate explicitly retained, not production acceptance.

All transport evidence here is synthetic/intercepted. No real vendor delivery,
readback, inference or external service operation is authorized or claimed.
Fresh independent adversarial review remains required.

## Third independent rejection and SDK-supported repair (2026-10-18)

Independent review rejected the fixed-epoch representation. An observed root
start of `2026-10-14T17:46:40+00:00` produced SDK `trace_start_time` in 1970.
Metadata cannot override this property. The second repair solved syntax,
ordering and arithmetic bounds but falsified downstream temporal semantics.
Its positive tests and prior red gates remain historical, not acceptance.

### Installed SDK evidence (LangSmith 0.14.3)

The installed package source was inspected locally before implementation:

- `.venv/Lib/site-packages/langsmith/run_trees.py`,
  `_create_current_dotted_order`: emits `%Y%m%dT%H%M%S%fZ` plus the actual run UUID.
  `%f` emits six microsecond digits; nanoseconds are not representable here.
- `RunTree.ensure_dotted_order`: constructs the segment with that helper and
  prefixes a child with the parent's exact dotted path plus `.`.
- `_parse_dotted_order`: splits on dots; parses the timestamp before the final
  36 characters and parses those 36 characters as a UUID. There is no independent
  arbitrary sequence-suffix field. `RunTree.from_headers` uses the first UUID as
  trace identity, the last as run identity and the penultimate as parent identity.
- `RunTree.trace_start_time`: parses the FIRST timestamp and attaches UTC. The
  root timestamp must therefore be its observed start at microsecond precision.
- `RunTree.create_child`: accepts an explicit run UUID and prevents an observed
  child start earlier than the parent. No UUID version restriction to random
  UUID4 is imposed; the SDK itself otherwise generates UUID7-based identities.
- `.venv/Lib/site-packages/langsmith/client.py`, `Client._load_child_runs`:
  sorts children by their full `dotted_order` strings and groups them by actual
  parent IDs; the UUID component participates in lexical ties.

With equal supported timestamps, retaining both existing randomly ordered child
UUIDs and truthful temporal components cannot guarantee canonical sibling order.
An arbitrary suffix would violate the parser, and a different UUID in only the
path would contradict run identity. Extra dot segments would invent hierarchy.
The contract-compatible solution is to change the projected child UUIDs, as
explicitly permitted when required by actual SDK semantics. No frozen baseline
contract or application span identity needs to change.

### Current construction and invariants

Projection lazily invokes the SDK's pure `_create_current_dotted_order` helper
with validated observed timestamps and UUIDs. It does not create an SDK client,
use routing defaults, export SDK-inferred metadata, call a vendor, or read back
a run. This private formatting helper is version-coupled; maintained checks
against public automatic RunTree construction guard its actual semantics.

The root retains its trusted application trace UUID and observed start. Each
child retains its application span ID; its projected UUID consists of the
validated sequence byte 01/02/03 followed by the last 15 bytes of the original
namespace/span UUID5 seed. UUID form/version/variant bits remain intact. The
same new UUID is used in the body and its dotted segment. This is a deterministic
UUID5-derived identity, not a claim that the altered value equals unmodified
UUID5 output. Its 120 remaining namespace/span-derived bits isolate traces.

Since observed times are nondecreasing, distinct microsecond timestamps already
sort in validated order. For equal timestamps, the leading UUID byte strictly
orders roles 1, 2, 3 regardless of the hash suffix. All valid prefixes retain
their membership and stable identities independent of neighbor timestamps.
Root and child segments still follow actual SDK timestamp+UUID path grammar.
There is no fake epoch, time adjustment, overflow/underflow arithmetic, UUID
search, latency fabrication or workflow retry. Observed dates outside the
previous serialization range retain their existing rejection behavior, as
previously authorized by the human.

### Maintained regression evidence

`test_sdk_dotted_order_preserves_observed_trace_time_and_identity` adds 16 cases:
four starts (minimum 1 ns, exact reviewer 2026 start, a submicrosecond offset
crossing a precision bucket, and the exact maximum reproduction) times all
prefixes 0/1/2/3. Each uses UUIDs 1, 2, 32 and a fresh UUID. The tests instantiate
actual SDK RunTrees from emitted records, verify `trace_start_time`, compare the
output with SDK automatic construction, call the SDK's actual parser, and check
each temporal component, suffix/body identity, parent link, unchanged role
times/durations, stable application span identity and unchanged retained snapshot.
The SDK client fields remain None and no SDK network method is invoked.

The 18 original collision cases remain; the six exact upper/lower fake-delivery
cases now require observed timestamp components instead of false logical epochs.
They still verify all nonempty prefixes, ordering across UUIDs, deterministic
projection, replay refusal, empty inputs/outputs and successful synthetic writes.
The unsupported-date rejection test and all other Slice 2 protections remain.

| Third-repair gate | Result |
| --- | --- |
| Ruff, Module 6 | PASS |
| New SDK-semantic regressions | 16 passed, 89 deselected, 0.57 s |
| All ordering/boundary regressions | 40 passed, 65 deselected, 0.46 s |
| Full Slice 2 maintained tests | 105 passed, 11.58 s |
| Slice 1 observation tests | 102 passed, 48.82 s |
| Full Module 6 pytest | Observed failure marker at 11%; last captured progress 14%; final result unavailable after session loss |
| Root pytest | Not run: passing Module 6 prerequisite not established |
| Relevant compileall | PASS, exit 0; independent syntax gate only |

The full Module 6 command was:

```powershell
if (Test-Path -LiteralPath 'build/module06-slice2-sdk-module-20261018-a') { throw 'Test temp path already exists' }; .venv/Scripts/python.exe -m pytest module-06/tests -q --tb=short --basetemp=build/module06-slice2-sdk-module-20261018-a
```

Its session was 42531. Captured output showed `......F..... [ 11%]` and
subsequently reached 14%. Resuming the existing handle returned
`write_stdin failed: Unknown process id 42531`. Read-only recovery inspected
local process metadata and this chat's captured tool output: no pytest process
remained, and the captured progress ended at 14%. No final node ID, assertion,
traceback, duration, totals or exit code was recoverable. The exact original
failure evidence is no longer available. The observed red marker is preserved;
it is not attributed to a known timing failure or relabelled PASS. Whether the
run completed normally or was interrupted is unknown. The suite was not
restarted, and no completed passing gate was repeated during this recovery.
Root pytest was not run because its prerequisite was not established.

The previously completed Slice 1 command used
`pytest module-06/tests/test_live_observation.py -q -x` with fresh basetemp
`build/module06-slice2-sdk-slice1-20261018-a`; it passed 102 tests in 48.82 s.
The remaining authorized syntax check was completed with
`.venv/Scripts/python.exe -m compileall -q module-06/src module-06/tests`
(exit 0). This does not override the red/incomplete Module 6 evidence.
Validation remains incomplete; full failure diagnostics and any subsequent
root gate remain outstanding. No independent acceptance is declared.

The initial SDK-semantic command was not executed: automatic approval review
hit an account usage limit. After the human requested resumption, the same
approval was retried and succeeded. The approval gate was not bypassed. This
was an execution/review infrastructure interruption, not a test failure.

Only the three untracked candidate files change. No tracked production/test
file, deterministic LangSmith implementation, inference path, authority/budget
contract, UI or OTel integration is modified. No live LangSmith delivery/readback,
model inference, Ollama/OpenAI contact or external/vendor operation is performed
or claimed. Independent adversarial review and actual service compatibility
verification remain pending; no independent acceptance or production readiness
is declared.


## Fourth independent rejection: unbounded DNS (2026-10-19)

The independent reviewer demonstrated that Requests connect/read timeouts do
not bound DNS: urllib3 invokes `socket.getaddrinfo` before its socket timeout.
An offline resolver blocked on a test-owned event remained inside the production
write after 16 seconds despite `(5, 10)` timeout settings. The delivery/replay
lock was also held throughout I/O. This was a blocking reliability defect.
The independently reviewed SDK-grounded timestamp/UUID design is unchanged.

### Application deadline and surviving-resource semantics

`_bounded_write` now owns a monotonic 15-second deadline around the entire
transport operation, including DNS, Requests, response disposal and Session
cleanup. The caller waits only for its remaining deadline and refuses results
received after that deadline. Requests socket timeouts remain additional
transport safeguards, not the proof of the application bound. The same wrapper
bounds injected transports; they always remain classified synthetic.

A process-wide nonblocking semaphore admits at most three transport operations,
across all delivery instances. There is no pending queue and no replacement for
stalled work. Each admitted operation has one daemon thread; its permit is
released only when the operation actually exits. Python cannot safely cancel
arbitrary blocked I/O. A timed-out resolver may therefore survive indefinitely,
retaining its bounded batch and transport-local credential until exit, but it
continues occupying its slot. Saturation fails promptly with `transport_failed`
and cannot accumulate abandoned workers. A brief worker-exit epilogue follows
permit release; at most three blocking operations survive. No process-wide
thread killing or production DNS monkeypatch is used. Daemon workers do not
hold up interpreter shutdown. No automatic retries or queued future writes
are introduced. All three permanently stalled slots require process restart
or actual I/O completion to restore delivery availability.

This is the smallest repair that bounds callers and abandoned work without
adding process startup, IPC or credential transfer. Existing Module 6 execution
uses subprocess isolation for privileged inference plus kill/reap handling;
this observational one-shot HTTP path has no execution authority and can safely
fail closed on global capacity. OS scheduling remains outside a hard real-time
guarantee. The application deadline bounds transport waiting, not arbitrary
interpreter pauses or pre-transport observation projection.

Only the replay/budget check and irreversible attempt claim remain under the
sink lock. No transport work occurs under that lock. An in-flight or timed-out
trace remains attempted, preventing replay; independent traces may use other
available global slots. Saturation also consumes the claimed lifetime attempt
and does not imply an HTTP request was sent. `write_attempts` counts the
application delivery attempt, not proof of a remote write.

Workers receive only the write callable and bounded immutable batch. Their
completion cell contains only an integer status or fixed failure category.
They cannot access the delivery attempt set, observer, or returned immutable
result through the wrapper. Late status/failure is discarded by the returned
invocation and cannot change execution, replay state or another invocation.
Underlying I/O may still finish and perform the originally authorized single
write after timeout: timeout is not proof of remote cancellation or nonreceipt.
Remote outcome remains unknown, with no readback or live verification.

### Maintained offline regressions and validation

New regressions intercept actual Requests/urllib3 `socket.getaddrinfo` with an
event, prove timeout evidence while DNS is still blocked, exercise same-sink
replay and another eligible trace, verify unchanged retained workflow evidence,
and release/join the test worker. Two additional cases keep three fake writes
blocked across separate delivery instances, refuse 20 further attempts without
creating workers, release with either late success or late failure, verify
immutable terminal results/replay state and reclaim capacity. Test cleanup
releases events before joining even on assertion failure. No real DNS occurs.
Only the new deadline tests shorten the new application constant for speed;
existing test timeouts and assertions are unchanged.

Initial Ruff reported E501 at test line 639 and B905 at line 692. Mechanical
formatting and explicit `strict=True` corrected both; subsequent Ruff passed.
Initial focused regressions: 3 passed, 105 deselected in 1.25 s. Test cleanup
was then strengthened before restarting the required relevant gates.

| Fourth-repair gate | Result |
| --- | --- |
| Ruff | PASS after mechanical corrections and final test cleanup |
| New deadline regressions | 3 passed, 105 deselected in 0.91 s |
| Full Slice 2 | FAIL: 1 failed, 102 passed in 16.79 s; exit 1 |
| Slice 1 | Not run: full Slice 2 prerequisite failed |
| Full Module 6 | Not run: prior pytest gate failed |
| Root pytest | Not run: Module 6 prerequisite not established |
| Relevant compileall | PASS, exit 0; independent syntax check only |

The human supplied additional historical validation evidence: a full Module 6
run had 2509 passes and one CrewAI collaboration UI timeout; that exact node
then passed 3/3 unchanged, and root pytest passed 4625 with 6 skips and three
existing Chroma deprecation warnings. This is supplied historical evidence,
not reconstructed diagnostics from the previously lost session. New red gates
will not automatically be attributed to this timing history.

No production readiness or independent acceptance is claimed. Remote delivery
and readback remain unverified. Only the same three untracked files change;
no staging, commit, live inference or external/vendor operation is authorized.


### Fourth-repair red gate diagnostics

Full Slice 2 command (with stdout/stderr preserved in the ignored build log):

```powershell
.venv/Scripts/python.exe -m pytest module-06/tests/test_live_langsmith.py -q -x --basetemp=build/module06-slice2-deadline-slice2-20261019-a
```

Log: `build/module06-slice2-deadline-slice2-20261019-a.log`.
Exact node:
`module-06/tests/test_live_langsmith.py::test_after_actual_synthetic_workflow_failure_cannot_change_execution[happy]`.
Test path: `module-06/tests/test_live_langsmith.py`, line 571 at failure.

```text
>       assert original_calls == len(calls(log)) == 3
E       AssertionError: assert 0 == 3
E        +  where 0 = len([])
E        +    where [] = calls(WindowsPath('E:/ONEDRIVE-PERSONAL/TECHADEMY/dm-aiep-modules/build/module06-slice2-deadline-slice2-20261019-a/test_after_actual_synthetic_wo0/calls.jsonl'))

module-06\tests\test_live_langsmith.py:571: AssertionError
FAILED module-06/tests/test_live_langsmith.py::test_after_actual_synthetic_workflow_failure_cannot_change_execution[happy]
1 failed, 102 passed in 16.79s
```

The test sampled `original_calls` after synthetic workflow return and before
invoking delivery. No calls log was present in its temp directory. Thus its
zero-call precondition already held before this invocation's transport boundary;
this does not establish why startup/execution failed or rule out every possible
suite/environment interaction. It matches the previously documented symptom,
but this occurrence is not automatically classified as a baseline failure.
The established execution process was reaped (PID 17796 in pytest diagnostics).

One unchanged diagnostic isolation check, not a replacement full gate:

```powershell
.venv/Scripts/python.exe -m pytest 'module-06/tests/test_live_langsmith.py::test_after_actual_synthetic_workflow_failure_cannot_change_execution[happy]' -q -x --basetemp=build/module06-slice2-deadline-isolated-20261019-a
```

Result: `1 passed in 3.14s`, exit 0; exact output retained in
`build/module06-slice2-deadline-isolated-20261019-a.log`. All three candidate
files were present for both runs. No source, test or deadline was changed
between the failed full gate and diagnostic isolation. The full gate remains
red. Slice 1, full Module 6 and root pytest were not run, preserving fail-fast
ordering. No repeated full run was used to obtain green. All 40 prior
ordering/boundary/SDK regression cases passed before the integration failure
in the full Slice 2 gate; the focused three new cases passed separately.
The failed `-x` gate did not execute the five subsequent cases in that full run.

`.venv/Scripts/python.exe -m compileall -q module-06/src module-06/tests`
completed with exit 0 and does not override the red pytest gate. Final Git
status remains exactly the three untracked candidate files on
`feature/module-06-architecture` at
`de49101e219ad5809d0dcf16e740eee9e6bf1209`, with no tracked/staged change or new
commit. No real DNS/network/vendor/model activity occurred; resolver tests used
a blocked monkeypatch and production-success tests intercepted Requests. No
independent acceptance is declared; validation is incomplete with the red gate
and its unresolved cause explicitly retained.
