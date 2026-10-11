# Deterministic Local Distributed Orchestration and Processing

Verified starting branch: `feature/module-06-architecture`; clean HEAD
`9bbea291d93a1169d4fd8dd0f1541b964af6c5a1`, subject
`feat: add deterministic langgraph orchestration topologies`.
AGENTS/SOP, frozen architecture/source requirements, security/cost/observability,
status/traceability and accepted ADRs were reviewed. Architecture B+ and its
Google ADK distributed-lab responsibility are preserved. No dependencies,
packaging, historical modules or accepted runtime implementations are changed.

## Actual execution boundary

An explicit application service, `execute_distributed_workflow`, launches exactly
two independent local worker interpreters. Each receives one authorized fragment
and executes one custom BaseAgent through installed ADK 2.11.0 Workflow,
InMemoryRunner and in-memory session. The coordinator runs application semantics;
ADK owns native
worker scheduling/events behind a private boundary. There is no LlmAgent, model,
tool, remote service, framework fallback or in-process replacement.

```text
Application coordinator process
    | serialized assignment / release       | serialized assignment / release
    v                                        v
Independent left interpreter                 Independent right interpreter
    ADK left_counter agent                       ADK right_counter agent
    | ready / started / validated result      | ready / started / validated result
    +-------------------> coordinator <------+
                    validation -> ordered aggregation -> trusted evidence
```

The coordinator splits the bounded instruction into two disjoint fragments.
Workers count characters locally, and the coordinator verifies each result
against its retained assignment before summing in canonical left/right order.
This is genuine local multi-process distribution and processing, not a sandbox
around an otherwise single-process multi-agent workflow. It proves neither
remote-host nor cluster/cloud distribution.

On Windows, the existing venv launcher was observed to start another interpreter:
its launch PID differed from `os.getpid()` and became the worker's parent. The new
transport directly launches the current interpreter's base executable under `-I`
and activates only the current installed venv site directory. This preserves
editable package ownership and makes the held process PID equal the native
worker PID, with the actual coordinator as parent. Task fragments are never
command-line arguments. This path is verified on Windows/Python 3.12.14;
the POSIX branch is not platform-verified here.

## Serialized protocol and authority

Each worker's private stdin/stdout pipes carry newline-framed UTF-8 JSON:

1. Worker sends `ready`: closed worker identity, PID and actual coordinator PID.
2. Coordinator sends `assignment`: workflow/task/assignment IDs, worker, role,
   sequence, fixed parent/capability/runtime, bounded limits and assigned fragment.
3. Inside the native ADK agent, worker sends `started` with bound identity and PID.
4. After both native roles have started, coordinator sends each matching `release`
   and closes stdin. Worker checks release identity/parent and rejects extra input.
5. Worker sends one result and exits. Coordinator rejects extra/replayed output,
   verifies exit success, synchronizes both results and validates again.

There are ten protocol packets per successful run. These transport frames are
distinct from the three budgeted logical task/messages: two worker contributions
and coordinator synthesis. Four work steps are dispatch, two native worker
executions and aggregation. The service checks budgets before spawning.

Contracts are immutable and reject unknown fields. Both sides freshly validate
schemas and semantics, including nested constructed Pydantic objects. JSON
decoding rejects invalid UTF-8, malformed/trailing data, duplicate keys and
non-finite values. Protocol version, sequence, PID/count/limit fields use strict
numeric types. Worker/task/workflow identity, role, parent, capability, limits,
runtime and result ownership must match application-retained context.

Every run creates two fresh assignment UUIDs, even for repeated workflow/task
IDs. A launcher-provided SHA-256 digest binds exact assignment bytes; worker
also verifies bootstrap worker identity and its actual OS parent. The digest is
integrity for this private local launch boundary, not remote authentication.
Only `count_characters` is authorized; workers cannot select providers, alter
routing/policy/budgets, delegate tasks, or supply trusted evidence. Prompt
injection remains bounded fragment data. Native ADK session context, event author,
state delta and final session/result are validated; transfers, tool/auth actions,
partial results and unexpected state fail closed.

Trusted evidence is created only by the application after response validation.
It includes mode, identities, ordered payload-free provenance, actual observed
PIDs, limits/work/packet/barrier counts and zero call/retry counts. It excludes
fragments, private instructions, credentials and worker-supplied evidence.
Assignment IDs/PIDs vary between runs; aggregate output and role/provenance order
are deterministic, rather than claiming byte-identical process evidence.

## Concurrency, lifecycle and bounds

Both independent native agents must be active at the barrier before either is
released. Exactly two workers can be active per workflow; a reduced concurrency
budget fails before launch rather than silently running sequentially. Tests
observe both live processes at the barrier, force either worker to complete
first, and verify identical ordered aggregation. Concurrent workflows have
separate processes, assignment IDs, context and temporary directories. There
is no global active-workflow limiter or worker pool.

| Resource | Bound |
| --- | --- |
| Workers / concurrent workers per workflow | Exactly 2 / at most 2 |
| Authorized role tasks / contributions plus synthesis | 3 / 3 |
| Work steps | Exactly 4, within the existing hard ceiling 32 |
| Instruction / each fragment | 4096 / 2048 characters |
| Each protocol frame | At most 16384 bytes, including newline |
| Successful protocol frames | Exactly 10; extra input/output rejected |
| Deadline | Caller bound, at most 30000 ms; includes startup and execution |
| Model / provider / external calls / retries | 0 / 0 / 0 / 0 |

The async deadline encloses spawning, IPC, worker exit and cleanup. Spawn tasks
are retained and shielded so cancellation cannot lose a created child handle.
On any failure, timeout or cancellation, cleanup acquires outstanding spawns,
kills living workers, closes input, cancels/awaits coordinator operations,
discards pipe tails without accumulating/logging them and waits for every child.
Cleanup is shielded through repeated caller cancellation; temporary directories
are removed only after reaping. There are no unmanaged background jobs or worker
subprocess trees in the implemented deterministic role.

Failure is closed: one invalid or failed worker prevents success; no retry,
partial aggregation or runtime fallback occurs. Public typed errors are
sanitized. In-process diagnostic causes remain chained; cross-process failures
carry only a bounded category/exception type, never raw SDK traceback or payload.
Stderr is discarded and SDK stdout diagnostics are discarded without accumulating
them. Successful execution, native worker failure, malformed/oversize/duplicate
output, early exit, timeout, caller cancellation, repeated cancellation during
spawn, and sibling spawn failure have lifecycle coverage.

These are logical workload, transport, concurrency and deadline controls, not
OS CPU/memory quotas or a hostile-code security sandbox. The trusted installed
Python/SDK/application code and local user/host remain part of the trust base.
Remote authentication, host compromise/crash recovery and durable queues are
outside this slice.

## Offline operation

Each worker gets a fresh temporary profile and an allowlisted environment with
only required Windows system variables and forced telemetry-disable settings.
API keys, provider flags, remote endpoints and telemetry credentials are not
propagated. Imports and ADK execution run under a guard that denies/counts every
non-loopback socket/DNS attempt; a swallowed attempt still prevents success.
Loopback remains available for Python's local event-loop machinery, not a new
listening service. The unchanged Module 6 parent test guard remains active.

No inference/provider execution, paid verification or monetary estimate is
introduced. Counts remain zero. Local CPU/process resources still have costs;
zero billable inference is not a claim that process execution is free. No
LangSmith/OTel/Prometheus/Grafana delivery, UI or deployment is implemented.

## Operation

Use the existing synchronized environment from repository root:

```python
import asyncio
from multi_agent_orchestration.contracts import (
    ExecutionLimits, RuntimeId, TaskInput, WorkflowRequest,
)
from multi_agent_orchestration.distributed_execution import execute_distributed_workflow

request = WorkflowRequest(
    runtime=RuntimeId.GOOGLE_ADK,
    task=TaskInput(instruction="Bounded local distributed processing."),
    limits=ExecutionLimits(max_steps=4, timeout_ms=30000),
)
result = asyncio.run(execute_distributed_workflow(request))
print(result.output)
print(result.evidence.model_dump_json())
```

Existing `execute_workflow` and registry behavior are unchanged. Calling this new
service requires explicit Google ADK and the default coordinator-worker topology;
other runtime/topology selections fail. Missing/broken SDK or worker execution
cannot fall back to an in-process fixture.

## Files and evidence

Exactly ten intended Module 6 files:

- New source: `distributed_contracts.py`, `distributed.py`,
  `distributed_execution.py`, `_distributed_processes.py`, `_distributed_worker.py`,
  `_distributed_adk.py` under `src/multi_agent_orchestration/`.
- New tests: `tests/test_distributed_orchestration.py`.
- Documentation: this file, `PROJECT_STATUS.md`, `TRACEABILITY.md`.

The focused suite has **94 passing cases**. Native Workflow/Runner/BaseAgent,
session/event tests and normal child runs use real SDK execution. Failure
injection is trusted test instrumentation in real independent child interpreters;
it is not normal runtime behavior or live-provider evidence. Tests cover real
PID/parent separation, serialized assignments/results, live native-role barrier,
both completion orders, fragment/UTF-8 limits, concurrent isolation, forged
identities/context/authority/evidence, replay/duplicates, strict JSON, budget
denial, credential/tracing flags, swallowed-network denial and lifecycle cleanup.
Complete repository gate results are recorded below.

## Conservative acceptance

Requirements: partial M6-005/006/007/009/010/015/017/018/020/023/026 evidence;
all 26 frozen meanings/statuses remain Planned. Product experience: documented
service, UI and human-facing lab acceptance pending. Real functionality: local
independent ADK workers with real serialized IPC. Reliability/security/cost:
bounded lifecycle, fail-closed validation and zero-call deterministic evidence.
Evidence: local process/SDK/test results; deployment: unverified.

No production horizontal scaling, remote-host/cluster/cloud operation,
throughput improvement, load-tested capacity, live AI, persistent distributed
state, observability delivery, completed lab/platform or production readiness
is claimed. M6-017 is prerequisite evidence only.

## Validation record

- Focused distributed suite: **94 passed in 45.51 s**, no skips/warnings.
- Complete Module 6 suite: **459 passed in 96.02 s**, no skips/warnings.
- Root collection: **2580 tests**, exactly 94 above the accepted topology baseline.
- The documented guarded example returned 37 characters with coordinator PID
  **3112** and worker PIDs **31096 / 30800**. Native worker identities matched held
  process handles and actual parent identity; both processes were reaped before
  return. These are execution observations, not persistent worker identifiers.
- Complete root pytest: **2574 passed, 6 skipped, 3 warnings in 176.22 s**.
  Skips are existing conditional Module 5 cases; warnings are existing Module 3
  Chroma deprecations. No new cleanup warnings remain: adversarial test wrappers
  explicitly close their native event streams; four rejection cases also pass
  with unraisable-exception warnings treated as errors.
- `ruff check .` and `compileall` over all six module source/test directories pass.
- Offline `uv lock --check`, `uv sync --locked --offline --check` and `uv pip check`
  pass: 239 locked packages, 216 installed packages, no sync changes needed.
- All six installed packages import with isolated Python from outside the
  repository, resolve to their owning module source paths, and make zero network
  attempts under the import guard. Process/offline/adversarial guards pass.
- Scope is exactly the ten Module 6 files listed above; Modules 1–5, accepted
  runtime source/tests, dependencies, root configuration, governance, Architecture
  B+ and frozen source requirements are unchanged. Whitespace checks pass.
