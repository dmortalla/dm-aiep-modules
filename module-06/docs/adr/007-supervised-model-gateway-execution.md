# ADR-007: Supervised Model Gateway Execution

- Status: Accepted
- Decision authority: Explicit human HITL approval of supervised process isolation
- Recorded: 2026-10-13
- Scope: Live Runtime Enforcement; accepted Story 1 contracts and Architecture B+ runtime ownership remain intact

## Context

A ModelGateway coroutine can suppress cancellation or block its event loop.
Cooperative in-process cancellation cannot enforce the application's execution
deadline in those cases. The human approved a minimal application-owned process
boundary, consistent with the repository's existing supervised-process patterns.
This decision authorizes that boundary; independent acceptance of the runtime
candidate and actual model verification remain separate.

## Decision

The application supervises one gateway worker for a workflow. The native
LangGraph researcher -> analyst -> critic sequence remains in the parent, which
owns canonical authorization, role sequencing, validation, call accounting,
per-call deadlines, the overall deadline, and final evidence. The worker executes
trusted application-injected gateway code. Exactly one bounded gateway operation
may be outstanding; concurrency is exactly 1.

Use private bounded JSON IPC: request packets are capped at 60,000 bytes and reply
packets at 110,000 bytes. Validate requests and replies against application-owned
contracts. IPC carries the role request/reply needed for execution; process-control
diagnostics and evidence never contain prompts, raw replies, credentials, provider
exception text, or arbitrary metadata. Child failures cross the boundary only as
closed, sanitized application-owned categories. Worker stdout/stderr noise is
discarded rather than promoted into evidence.

The parent charges a call at dispatch, permits three normal role calls and at
most one application-owned malformed-output repair, and never retries transport
failures. Transport retries remain 0. Worker startup failure or termination ends
the workflow; process restart is not an implicit retry. No restart path, pool,
broker, remote worker, or distributed infrastructure is introduced.

Use parent monotonic execution deadlines and reserve bounded overall time for
termination and reaping. Refuse budgets too small to support the supervision
reserve before starting a worker. After issuing the kill, use an independent
supervisor allowance of at most two seconds for pipe draining and process wait,
even if the execution deadline is already exhausted. This allowance can delay
terminal propagation; it cannot authorize another operation, restart, retry,
continued gateway execution or acceptance of late output. Terminate and reap the
worker when its allowed execution time
expires, on cancellation, and on workflow success or failure. Acquire process
ownership even if cancellation races startup; shield cleanup against repeated
cancellation. Return no successful result until cleanup and final deadline checks
complete. A late reply or a result whose cleanup exceeds the deadline cannot
become authoritative evidence. No owned worker survives workflow completion or
failure.

Launch the actual worker interpreter directly, including on Windows, so the
supervised PID is the process executing gateway code. Pass an explicit minimal OS
environment allowlist and fixed tracing/dotenv-disable flags; do not inherit
ambient credentials or provider configuration. The injected factory is trusted
application code and must not spawn independent descendant processes. This is a
lifecycle boundary, not an arbitrary-code security sandbox. Termination/reaping
depends on a responsive operating system; this is not a hard real-time OS claim.

## Alternatives Considered

- Cooperative async cancellation alone: insufficient when gateway code blocks or
  suppresses cancellation.
- Thread execution: Python cannot forcibly stop an uncooperative worker thread.
- Pools, brokers, or remote workers: unnecessary infrastructure for concurrency 1
  and a bounded local workflow.

## Consequences and Evidence

Process startup and bounded serialization consume the execution budget. Cleanup
normally uses its existing reserve inside that budget. If the parent wakes after
the deadline, the independent bounded supervisor allowance still permits the
completed subprocess wait before terminal propagation. Successful evidence must
still pass the original deadline check after cleanup; that deadline is unchanged.
Factories must be importable, source-backed, zero-argument trusted callables;
closures and shared mutable parent gateway instances are unsupported. Provider
adapters must be reviewed for this lifecycle and environment contract before use.

[Live Runtime Enforcement](../LIVE_RUNTIME_ENFORCEMENT.md) records the candidate,
limits, synthetic process tests, gate results, and remaining work. Offline tests
exercise actual child processes and native LangGraph with synthetic gateways;
they establish no real inference or provider compatibility claim. This decision
does not authorize model/provider/Ollama/LangSmith activity, credential or `.env`
inspection, dependency changes, deployment, or Git publication. All 26 source
requirement statuses remain Planned.
