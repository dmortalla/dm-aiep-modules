# Live Runtime Enforcement — Offline Candidate

## Scope and standing

This additive milestone starts from the clean accepted Story 1 foundation,
`feature/module-06-architecture` at
`a5ca8c8817c7d5742939acd25d2ea6919ff3c1e3`
(`feat: add live-model safety contracts`). Architecture B+ and the accepted
contracts remain unchanged. The human explicitly selected supervised process
isolation for deadline/cancellation enforcement. The explicit HITL decision is
recorded in [ADR-007](adr/007-supervised-model-gateway-execution.md).

`live_execution.execute_live_workflow` now compiles and invokes a real fixed
LangGraph sequence: researcher -> analyst -> critic. All role content comes
through an injected `ModelGateway`. No provider implementation, default model,
HTTP client, credential lookup, console integration or hosted mode is added.

**Evidence in this milestone is deterministic offline runtime verification with
synthetic gateways. No real model has executed through this path.** Returned
`LiveEvidence` instances in these tests are synthetic instances of the accepted
local-model contract; they are not receipts proving actual inference. The
`local_model_inference` literal describes the authorized execution class and
cannot establish adapter provenance or genuine inference by itself. A future
application must inject reviewed local-provider code and obtain separate live
verification before presenting an actual inference claim.

## Application API

```python
result = await execute_live_workflow(
    instruction,
    authorization=explicit_authorization,
    gateway_factory=trusted_application_factory,
    workflow_id=workflow_uuid,
    task_id=task_uuid,
)
```

The factory is a trusted, importable, zero-argument application callable, passed
as a code dependency, never selected from request/model text. It executes only
after `require_live_authorization` returns a new canonical authorization. Local
closures and lambdas are unsupported. A trusted standalone source module can
also supply the factory; its source location is taken from the injected
callable, not from a task, authorization field or reply.

The gateway lives in one supervised child for the complete run. Parent object
mutations are not shared across that boundary. The child
receives only an explicit OS-variable allowlist and fixed tracing/dotenv-disable
flags; ambient parent credentials and configuration are not inherited.
The injected application code
must not spawn independent descendant processes. Isolation here is lifecycle
supervision of trusted adapter code, not a sandbox for arbitrary Python code.
The factory must not own authorization, routing, budgets, retries or fallback.

Invalid task content or identifiers produces fixed `LiveValidationError`.
Execution refusal/failure produces `LiveRuntimeError`, a `LiveExecutionError`
with a canonical `LiveFailure` in `.failure`. Its message/category are closed;
its failure contains only application identity, selection and call counts.
Caller cancellation propagates a fresh `CancelledError` after cleanup and
does not retain the caller's cancellation message. No success result is returned
on timeout, cancellation, malformed output, identity mismatch or gateway failure.
The outer application boundary explicitly clears exception cause/context before
propagation, including when async cleanup or an active caller exception would
otherwise create implicit context. Suppressed rendering alone is insufficient.

## Runtime ownership and limits

The parent owns the validated authorization snapshot, fixed graph edges, role
order, prompts, monotonic clocks, call/repair counters, acceptance and evidence.
LangGraph state contains only an application-created phase integer. Task text
and serialized, previously validated role content enter bounded prompts; prompts
identify that data as untrusted. This instruction is guidance, not a security
control: typed schemas and application code enforce authority separation.

Every request crosses `validate_live_data(ModelRequest, ...)`. The accepted
8,192-character prompt ceiling is enforced without silently truncating content;
tasks whose JSON/context rendering cannot fit fail closed. Invalid rendered
requests do not consume a gateway call. Each reply is revalidated and checked
against the exact authorized provider/model before its content is parsed by
`parse_role_output`. Analyst citations also cross `check_analysis`.

One call is charged when dispatched to the initialized gateway, including a
dispatch that subsequently fails. The successful normal plan makes exactly
three calls. A run can spend its one optional fourth call on one malformed
role-output repair, including invalid analyst citations. The repair repeats
that same role using the same selected model, original context and fixed repair
instruction. Rejected text/diagnostics are not fed back into the prompt.

The repair allowance is global, not one per role. A second malformed response,
a failed repair, or later malformed output after a repair stops the run.
Provider claims of malformed output do not initiate repairs. Transport errors,
timeouts, reply identity mismatches, oversize replies, policy failures and
exhausted budgets never trigger repair, retry, fallback or model substitution.
Concurrency is one and transport retries are zero.

## Deadlines, cancellation and cleanup

The overall monotonic execution clock begins at API entry and includes validation,
LangGraph import/compilation, process startup, all calls and parsing. Successful
result acceptance also requires cleanup to complete within the original deadline.
The runtime reserves up to 250 ms, at most one quarter of the represented budget,
inside that deadline for reaping and final result validation. Budgets of 250 ms
or less are refused before child allocation because they cannot fund the
supervision reserve; this does not alter Story 1's representational bounds.

Each dispatched call is limited by the smaller of its configured timeout and
remaining work time. The request receives the corresponding bounded timeout
hint; the parent independently enforces elapsed time. Buffered and validated
late replies are rejected. A final deadline check after cleanup prevents a late
successful result from escaping.

The parent kills the gateway child on every exit path, including success, and
then uses a separate, supervisor-owned allowance of at most two seconds to
discard pipe tails and complete the asynchronous subprocess wait. That allowance
does not depend on remaining execution time: a parent that wakes after its
execution deadline still needs to reap its terminated worker. The existing
reserve remains in place, but its exhaustion cannot collapse reaping to 1 ms.
Terminal failure/cancellation propagation may therefore occur after the execution
deadline, within the independent cleanup bound on a responsive OS. No success
result can cross the original deadline.

Cleanup only kills, closes, discards and waits. It dispatches no gateway work,
does not restart/retry a child, never parses its tail as a result, and cannot
reopen acceptance after timeout or cancellation. This also removes child-owned tasks that
ignore cooperative cancellation or remain running after a valid reply. Spawn
ownership and cleanup are shielded against repeated caller cancellation. There
is no detached parent execution task or thread waiting on gateway code.
On Windows the launcher uses the actual base interpreter with this venv's site
directory activated, avoiding an unowned interpreter behind a venv redirector.
Tests require the gateway's actual PID to equal the supervised process PID.

OS process creation, termination and scheduler responsiveness remain operating
system prerequisites; this is not a hard real-time guarantee against a broken
or indefinitely stalled OS. Cleanup errors fail closed with sanitized wording.
The runtime does not claim to supervise independently spawned descendants.

## Transport, accounting and disclosure

Private stdin/stdout pipes carry bounded JSON, never pickle. The request packet
cap is 60,000 bytes; the reply envelope cap is 110,000 bytes to accommodate JSON
escaping around the unchanged 16,000-byte reply ceiling. Oversize/malformed
envelopes fail closed. The worker suppresses unsolicited stdout/stderr and emits
only validated replies or closed failure categories. Provider exception text
and raw Pydantic diagnostics never cross the pipe as errors.

The parent revalidates replies independently. Only content that passes the
accepted role and citation boundaries can enter the result. The critic's
`sound`/`needs_revision` verdict does not change routing, acceptance, calls,
selection, capability or evidence classification.

Final `LiveAccounting`, `LiveEvidence`, `LiveWorkflowResult` and `LiveFailure`
cross the accepted sanitized data boundary. UUIDs and plan records retain the
accepted canonicalization protections. Evidence contains no prompts, raw
replies, exception text or arbitrary metadata. LangSmith tracing is explicitly
disabled around native graph invocation; no tracing delivery is added.

Token counts remain bounded provider-reported values. Successful-run totals
include validated malformed replies that consumed a repair call. A total is
`None` if any constituent value is unavailable or its sum cannot fit the
accepted token-count ceiling. Missing usage is never invented as zero.
No monetary amount is introduced. The accepted cost status describes the local
execution class, not free compute or measured resource cost.

## Verification and remaining work

The original 48 focused tests exercise real process ownership and native graph execution,
authorization refusal, role order, concurrency, all repair positions and a
failed fourth call, mismatch/transport/policy failures, accounting, usage,
noncooperative/blocking gateways, late results, repeated cancellation during
spawn, cleanup failure sanitization and deadline exhaustion during cleanup.
Caller authorization mutation and hostile identifier instances are also tested
through the runtime boundary, together with maximum task/content prompt bounds
and invalid Unicode rejection.
Active-caller exception contexts and cleanup-context disclosure are covered.
A synthetic parent-secret canary verifies the explicit child environment.
The 479 accepted Story 1 adversarial tests are unchanged.

Original implementation verification before independent rejection
(Python 3.12.14, offline; superseded for the repaired candidate below):

| Gate | Result |
| --- | --- |
| `uv run ruff check module-06` | PASS |
| Complete Module 6 pytest | 1,831 passed (1,783 accepted baseline + 48 new) |
| Complete root pytest | 3,946 passed, 6 skipped; 3 existing ChromaDB deprecation warnings |
| compileall: Module 6 source, tests, app and all four command paths | PASS |

Verification used `UV_OFFLINE=1`, `UV_NO_SYNC=1`, synthetic process profiles and
environment, disabled dotenv auto-loading and guards against external/model
connections and real `.env` reads. Pytest ran via `uv run python -m pytest`
with the installed asyncio plugin explicitly enabled. Windows process IPC ran
outside the filesystem/network sandbox because sandboxed asyncio socket-pair
creation is unavailable. Existing suites use test-owned loopback telemetry
receivers; no external/model/Ollama/LangSmith/provider request was made.

Development verification found and repaired candidate defects: the forbidden
direct LangSmith import (replaced with the established lazy tracing-control
pattern), and cleanup exceptions retaining raw implicit context (fixed at the
outer public boundary). Self-review also corrected repeated-cancellation spawn
ownership, cleanup reserve/tail draining, Windows redirector PID ownership,
request escaping overhead, and ambient environment inheritance. Regression
assertions were retained or added; accepted tests/contracts were not weakened.
An early wall-clock deadline test incorrectly assumed fast process startup;
that test/evidence defect was replaced by controlled monotonic accounting,
with factory-startup timeout tested independently. The complete fail-fast
sequence above was rerun after the final repair.

This is implementer offline verification. The uncommitted candidate awaits
independent acceptance; no real-model or deployment evidence is claimed.

### Bounded reaping repair

Independent acceptance rejected the candidate after the complete Module 6 gate
observed an unreaped worker in the overall-deadline test. A separate real-clock
reproduction confirmed it: after a two-second execution deadline and a 2.1-second
parent event-loop stall, 10/10 failures propagated with subprocess `returncode`
still `None`, although Windows reported execution had terminated. The same
reproduction was confirmed again before this repair. This was incomplete parent
reaping, not evidence of continued gateway execution.

The shared cleanup path now uses `REAP_TIMEOUT_SECONDS = 2.0` after issuing the
kill, instead of deriving its wait allowance from an exhausted execution clock.
All exit paths retain the existing cancellation shield and sanitized boundary.
No role, contract, gateway worker, authorization, accounting, repair policy,
execution deadline, dependency or accepted Story 1 test changes.

Eleven additional focused cases cover repeated real-clock stalls with hanging
and delayed gateways, completed Windows process waits before propagation,
unchanged deadlines/call counts, the independent cleanup bound and its expiry,
expired-budget cleanup on success/timeout/startup/child failure, and repeated
cancellation during the wait on success/cancellation/IPC/child-failure paths.
They preserve existing returncode and no-fifth-call assertions. All 59 focused
runtime cases passed. The unchanged external reproduction then passed: all ten
real-clock stalled-parent runs returned `timed_out` with completed subprocess
wait state (`returncode = 1` after the Windows forced kill), and independent
Windows queries found no running owned worker. This is repair verification,
not independent acceptance. Current full gate results are recorded after running
the required fail-fast sequence.

Repair gate results (offline, guarded noncredential environment):

| Gate | Result |
| --- | --- |
| `uv run --offline --no-sync ruff check module-06` | PASS |
| Complete Module 6 pytest | 1,842 passed in 274.19 s |
| Complete root pytest | 3,957 passed, 6 skipped, 3 existing ChromaDB deprecation warnings in 369.83 s |
| compileall: Module 6 source, tests, app and all four command paths | PASS |

The test launcher explicitly supplies a noncredential environment, suppresses
dependency dotenv loading for real paths, and blocks real `.env` reads and
external connections; test-owned synthetic files and loopback IPC remain usable.
The repair changes only this document, ADR-007, `live_execution.py` and
`test_live_execution.py`. The complete candidate remains ten files, unstaged and
uncommitted. All 26 source statuses remain Planned. Independent acceptance of
the repaired candidate remains pending.

The scoped SOP assessment is:

| Gate | Assessment |
| --- | --- |
| Requirements | Runtime requirements implemented; source matrix unchanged |
| Product Experience | Documented application API; live UI explicitly deferred |
| Real Functionality | Real native graph and supervised processes; synthetic gateway only |
| Reliability | Call/deadline/repair/cancellation/cleanup paths tested offline |
| Security | Accepted trust boundaries consumed; sanitized errors; no tools |
| Cost | Bounded calls, no retry/fallback, no billable operation or invented money |
| Evidence | Offline implementation verification; independent acceptance pending |
| Deployment | No live deployment or production-readiness claim |

Genuine model behavior,
model quality, Ollama compatibility, local-provider usage reporting, hosted
support, live Streamlit execution, live observation and deployment remain
unverified. All M6-001..M6-026 statuses remain Planned. Actual compatibility and
inference require a later explicitly authorized milestone.
