# Deterministic LangGraph Coordinator-Worker Slice

## Scope and Authority

This records the accepted LangGraph milestone. Its CrewAI construction-only
limitation is superseded by [CREWAI_COLLABORATION.md](CREWAI_COLLABORATION.md).
Its ADK construction-only limitation is superseded by
[GOOGLE_ADK_ORCHESTRATION.md](GOOGLE_ADK_ORCHESTRATION.md).
[LANGGRAPH_TOPOLOGIES.md](LANGGRAPH_TOPOLOGIES.md) adds explicit topology
selection while preserving this default coordinator-worker flow.

Starting branch: `feature/module-06-architecture`; HEAD
`0294a3ef8a9ceb99a463ed2246288fbf03c68c4d`, subject
`build: integrate module 6 into root quality gate`; worktree clean.
Reviewed AGENTS.md, docs/ENGINEERING_SOP.md, SOURCE_REQUIREMENTS.md,
ARCHITECTURE.md, SECURITY.md, COST_GOVERNANCE.md, OBSERVABILITY.md,
TRACEABILITY.md, PROJECT_STATUS.md, RUNTIME_FOUNDATION.md, and ADRs 001–006.
Architecture B+, dependencies, and all 26 frozen source meanings remain intact.
This story implements one deterministic local workflow, not the full platform.

## Actual Graph and Application Boundaries

`LangGraphRuntime` constructs the locked SDK's real StateGraph. Each execution
compiles an isolated typed graph and awaits the compiled graph's `ainvoke`:

```text
START -> coordinator -> worker -> coordinator_validate -> END
```

The coordinator explicitly assigns the bounded task to `deterministic_worker`.
The worker receives the typed request/context and counts instruction characters;
it neither interprets instructions nor echoes their text. The coordinator checks
the worker result before accepting completion. Each node uses application-owned
`advance`/`validate_state` functions, immutable WorkflowState phases, and the
exact history `coordinator_delegated`, `worker_completed`, `coordinator_validated`.
Sequential graph edges enforce ordering; there are no loops or retries.

The original revalidated request is retained in per-run closures outside graph
output. Every transition and the final graph result must match that request's
workflow/task IDs, runtime, instruction, limits, delegation, phase, history, and
expected worker output. Nested Pydantic model_construct/model_copy bypasses are
revalidated. SDK objects stay private in adapters.py. Graph output cannot provide
policy, authority, evidence, alternate runtime, or additional budget.

`execute_workflow` separately revalidates the adapter result, IDs, exact output,
agent identity, and history before constructing ValidatedWorkflowResult and
ExecutionEvidence. Successful evidence contains application-owned identities,
requested/actual LangGraph, completed status, deterministic_offline mode, three
consumed steps/transitions, caller limits, and zero retries/model/external calls.
It excludes instructions, arbitrary metadata, credentials, and authority fields.
Failure returns a typed exception and no successful evidence.

Fixture remains the default, uses the same fixed output, and consumes one step.
Explicit LangGraph selection requires max_steps >= 3. CrewAI/Google ADK still
prove only construction and refuse execution. Missing or broken LangGraph never
falls back to fixture. Determinism concerns fixed identities/input; existing UUID
defaults still generate distinct identities when callers omit them.

## Bounds, Security, and Cost

ExecutionLimits remain strict: 1–32 steps and 1–30,000 milliseconds. Requests
with fewer than three graph steps fail before compilation; each node also checks
the remaining application budget. LangGraph receives a finite recursion bound
(max_steps + 1 accommodates its termination check). The application service's
async deadline cancels cooperative graph work; caller cancellation propagates.
No retries, provider objects, model callbacks, tools, or external work exist.
This deadline does not preempt arbitrary blocking Python or provide a sandbox;
the built-in synchronous nodes perform fixed work on at most 4,096 characters.
This slice supplies per-run bounds, not global admission/concurrency controls.

Ambient credentials are never read or selected. The adapter uses the already
installed tracing dependency's local `tracing_context(enabled=False)` around
graph invocation so even ambient LANGSMITH_TRACING/LANGCHAIN_TRACING_V2 flags
cannot activate remote tracing. No LangSmith account, client, delivery, or service
is required or verified. No Prometheus/Grafana/OTel integration is introduced.
The test network guard still blocks/counts all non-loopback DNS/connections,
including swallowed attempts; loopback is needed for Windows asyncio internals.

Outer application errors exclude task/output payloads; internal chained causes
may contain sensitive validation/SDK details and must not be exposed or logged
unredacted in a future UI or exporter. Schema validation is not authentication or
protection against hostile trusted Python code. Raw task text exists only in the
bounded in-memory context, not final evidence or telemetry.

## Operation

From the synchronized repository environment, no key or network is needed:

```python
import asyncio
from uuid import UUID
from multi_agent_orchestration.contracts import (
    ExecutionLimits, RuntimeId, TaskInput, WorkflowRequest,
)
from multi_agent_orchestration.execution import execute_workflow

request = WorkflowRequest(
    workflow_id=UUID(int=1),
    runtime=RuntimeId.LANGGRAPH,
    task=TaskInput(task_id=UUID(int=2), instruction="bounded context"),
    limits=ExecutionLimits(max_steps=3, timeout_ms=1000),
)
result = asyncio.run(execute_workflow(request))
print(result.model_dump_json())
```

Expected worker output: `Deterministic worker processed 15 characters.` Evidence
shows explicit LangGraph, all three ordered transitions, and zero calls/retries.
Changing task text changes only the count; injection-like instructions cannot
alter execution privileges. Reusing the fixed request produces equal output and
evidence. Run `uv run --locked --offline pytest module-06/tests` for focused tests;
root pyproject.toml remains authoritative for the complete gate.

## Test Evidence

`test_langgraph_workflow.py` observes real compilation/ainvoke, exact graph edges,
coordinator/worker/validation calls and context, deterministic repeatability,
concurrent isolation, step-budget exhaustion, real graph timeout/cancellation,
malformed state/output, forged IDs/bounds/history/authority/evidence, Pydantic
bypasses, credential/tracing independence, sanitized errors, and no fallback.
Existing fixture, missing-SDK, construction-only CrewAI/ADK, contract, and source
isolation tests remain. The obsolete LangGraph construction-only parameter case
is replaced by stronger real-execution assertions, not relaxed to pass.

Final verification, 2026-10-10, Python 3.12.14:

| Gate/evidence | Result |
| --- | --- |
| Root Ruff | PASS; safe import sorting and formatting only; no unsafe fixes |
| Root collection | 2,250 tests, 8.12 seconds; baseline 2,202 plus 49 new cases minus one obsolete construction-only case |
| Complete root pytest | 2,244 passed, 6 skipped, 3 existing ChromaDB warnings, 87.37 seconds |
| Module 6 coverage in root run | All 129 cases passed, including 49 new coordinator-worker cases; no new skips/warnings |
| compileall | PASS over Modules 1–6 source/test/application/example paths |
| Offline security | Existing unchanged guard passed with zero non-loopback DNS/connection attempts, including credential/tracing tests |
| uv consistency | uv lock --check --offline, uv sync --locked --offline --check, uv pip check passed; sync would make no changes |
| Installed package imports | All six application packages imported under isolated Python (-I) |
| Whitespace/scope | git diff --check passed; changes only under Module 6 source/tests/docs; new files reviewed for whitespace |
| Dependency/architecture integrity | pyproject.toml, uv.lock, Architecture B+, ADRs, source requirements, and Modules 1–5 unchanged |

The six skips retain their existing optional Mem0/live-provider conditions; the
three warnings are existing ChromaDB embedding-configuration deprecations.
The complete fail-fast Ruff -> root pytest -> compileall sequence passed after
safe formatting/import repairs. No tests or security gates were weakened.

## Definition of Done and Remaining Work

Requirements: partial evidence for the eight targeted IDs; no requirement/lab
is accepted complete and all statuses remain Planned. Product experience: a
runnable service example exists; human-facing lab/console review is pending.
Real functionality: genuine local LangGraph execution with deterministic worker
functions; no AI inference. Reliability: bounded transitions, deadlines,
cancellation, typed failures; no retry/recovery/persistence/distributed semantics.
Security: explicit trust boundaries and adversarial tests; deployment access and
full platform security remain unverified. Cost: zero provider/network paths;
no live cost optimization claim. Evidence: deterministic local graph evidence
only. Deployment: no deployment or production-readiness claim.

Next recommended story: expose this bounded flow and validated typed failure
outcomes in the application service/curated operations console with offline
guidance. Do not enable providers or remote telemetry without separate approval.
