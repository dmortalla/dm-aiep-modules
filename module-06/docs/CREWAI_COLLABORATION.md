# Deterministic CrewAI Collaborative Workflow

## Scope and Authority

Verified clean starting branch `feature/module-06-architecture`, HEAD
`00cbda2ac206adeb92dfd15baef28ec0584bd0d9`, subject
`feat: add deterministic langgraph coordinator worker`.
Reviewed AGENTS.md, the engineering SOP, all Module 6 functional/architecture,
security, cost, observability, status, traceability, runtime documents and ADRs
001–006. Architecture B+, all 26 source meanings, dependencies, and Modules 1–5
remain unchanged. The accepted LangGraph slice is preserved. This story adds
bounded local CrewAI collaboration, not the complete AI platform or labs.

## Genuine CrewAI Execution

The installed CrewAI 0.193.2 exposes an abstract BaseAgent execution interface.
The private adapter implements that interface with deterministic role behavior;
it does not instantiate Agent's LLM executor or supply a synthetic LLM. Real Crew,
Process.sequential, Task, TaskOutput and CrewOutput machinery remains intact:
Crew.kickoff initializes agents, selects task owners, schedules Task.execute_sync,
aggregates explicit Task.context outputs, runs validation callbacks, and assembles
the final CrewOutput. No entire workflow, scheduler, or task executor is replaced.

The three distinct application roles own three distinct native Tasks:

```text
Researcher -> validated research message
Analyst    -> explicit research context -> validated analysis message
Critic     -> explicit research + analysis context -> validated synthesis
```

Research counts bounded input characters. Analysis derives its count from the
validated research message. Critic derives its final count from validated analysis.
The bounded result is `Collaborative review accepted N characters.` Native Task
ownership, role, task name, execution order, and actual aggregated context must
match application expectations. This proves local collaboration/context exchange
with deterministic role executors, not AI inference or free-form research.

## Shared State, Validation, and Evidence

CollaborationState contains the original immutable request and at most three
messages, each at most 256 content characters. Each message has workflow/task IDs,
a closed collaborator role, strict sequence number, and up to two source roles.
Shared state is per-crew closure state containing immutable snapshots, never
global, persistent, or distributed application memory. CrewAI's built-in memory,
embeddings, knowledge, planning, tools, and dynamic delegation are disabled.

Every contribution crosses schema and semantic validation before insertion.
Identity, original context/limits, role ownership, source provenance, sequence,
and exact deterministic content must match the externally retained request.
Crew-aggregated context must equal the validated prior message serialization.
Completion checks all three native task outputs, final output, and zero token
usage. IPC output is untrusted and revalidated in CrewAIRuntime, then again in
execute_workflow before successful evidence is constructed by the application.
Nested model_construct/model_copy bypasses, unknown authority/policy/provider/
budget/evidence fields, corrupted messages, and alternate runtime IDs fail closed.

Evidence adds only bounded payload-free contribution records: identities, roles,
sequence, and source roles. It records explicit requested/actual CrewAI, completed
status, deterministic_offline mode, three consumed steps and configured limits,
zero retries, zero model calls, and zero external calls. It stores no raw task
instruction or message content. The existing evidence schema has no monetary
estimate field; zero provider execution is proven without inventing billing data.

## Offline Process and Resource Controls

Installed CrewAI imports can start install analytics; Crew construction can enable
tracing from ambient flags and always uses SQLite execution logs. The adapter
therefore checks availability without importing CrewAI in the parent and executes
each crew in a fresh local Python process. Native objects stay inside that private
runtime boundary. The child gets an allowlisted environment with temporary home,
AppData/storage paths, forced telemetry/tracing disablement, bundled local model
metadata, and no inherited credentials/provider configuration. CREWAI_TESTING
disables first-run trace collection/prompts; it does not replace orchestration.
Parent settings are untouched. CREWAI_STORAGE_DIR directs unavoidable SDK logs
into temporary storage; the parent deletes them only after the child is reaped.
Those SDK logs are not persistent application memory or trusted evidence.

The existing parent test guard is unchanged. A child-local socket/DNS guard also
denies/counts non-loopback attempts before SDK import and rejects success even
when SDK code swallows a denied attempt. Loopback remains available for Windows
asyncio internals. This is a fail-closed guard for the known local SDK path, not
an OS sandbox or protection against malicious trusted Python/native code.

ExecutionLimits retains existing strict step/deadline ceilings and adds strict
1–3 task/message ceilings, both defaulting to three. CrewAI requires at least
three steps/tasks/messages before spawning work. Every contribution independently
enforces remaining bounds. There are no retry loops or tools. The application
deadline includes child startup/import; timeout or caller cancellation kills and
reaps the child, including cancellation during process creation, before cleanup.
Insufficient deadlines fail rather than increase their own budget. Per-run bounds
do not provide global admission/concurrency controls.

Public exceptions are typed and payload-free. Unexpected child failures retain
bounded internal exception/traceback summaries as chained causes; crossing a
process boundary cannot preserve the original Python exception object. Causes
may contain sensitive validation data and must not be exposed/logged unredacted.
There is no live telemetry, provider selection, model/API call, or fallback to
fixture/LangGraph. Google ADK remains construction-only.

## Operation

Use the synchronized Python 3.12.14 environment. Explicitly choose CrewAI and a
deadline that includes SDK startup; the original one-second default is preserved
and can be insufficient for a fresh CrewAI process. For example:

```python
import asyncio
from uuid import UUID
from multi_agent_orchestration.contracts import (
    ExecutionLimits, RuntimeId, TaskInput, WorkflowRequest,
)
from multi_agent_orchestration.execution import execute_workflow

request = WorkflowRequest(
    workflow_id=UUID(int=1), runtime=RuntimeId.CREWAI,
    task=TaskInput(task_id=UUID(int=2), instruction="bounded context"),
    limits=ExecutionLimits(
        max_steps=3, max_tasks=3, max_messages=3, timeout_ms=30000,
    ),
)
result = asyncio.run(execute_workflow(request))
print(result.model_dump_json())
```

Expect `Collaborative review accepted 15 characters.` and three ordered
payload-free contribution records. No key/network or service is needed. Fixed
identities/input produce equal semantic result/evidence. Native UUIDs/timestamps
are private and do not affect application determinism.

## Test and Quality Evidence

test_crewai_collaboration.py spies on real Crew.kickoff, Crew._execute_tasks,
Task.execute_sync, native owners/context and completion without replacing their
implementations. Tests forbid BaseLLM/LLM calls, execute real isolated processes,
verify credential/tracing-independent zero-call evidence, concurrent isolation,
cleanup, timeout/cancellation/spawn races, strict task/message/step budgets,
injection-like input, forged provenance/state/evidence, Pydantic bypasses,
sanitized chained failures, and swallowed child network attempts. Existing
fixture/LangGraph/ADK regression and network controls remain.

Final verification — 2026-10-11, Python 3.12.14:

| Gate | Result |
| --- | --- |
| Root Ruff | PASS; safe import fixes/formatting only; no unsafe fixes |
| Focused Module 6 | 184 passed, zero skips/warnings, 36.53 seconds |
| New CrewAI cases | 56; replace one obsolete construction-only case, net +55 |
| Root collection | 2,305 tests, 8.26 seconds; includes all 184 Module 6 cases |
| Complete root pytest | 2,299 passed, 6 skipped, 3 existing ChromaDB warnings, 110.46 seconds |
| compileall | PASS over established Modules 1–6 source/test/app/example paths |
| uv consistency | Lock check, locked offline sync check, installed dependency check PASS; sync would make no changes |
| Installed imports | All six application packages imported under isolated Python (-I) |
| Whitespace/scope | git diff --check PASS; Module 6 source/tests/docs only; new file whitespace reviewed |
| Integrity | Modules 1–5, pyproject.toml, uv.lock, architecture, ADRs, source requirements, original network guard unchanged |
| Offline proof | Zero guarded non-loopback attempts on genuine paths; zero native tokens/model calls/external calls; explicit denial test confirms swallowed attempts cannot yield success |

The six skips retain existing optional Mem0/live-provider conditions. The three
warnings are existing ChromaDB embedding-configuration deprecations. The first
focused process test exposed missing temporary home/Windows known-folder paths;
bounded environment/directory repairs fixed SDK startup without relaxing controls.
The repaired focused gate and complete fail-fast Ruff -> root pytest -> compileall
sequence passed. No quality/security gate or accepted regression was weakened.

Exactly these 13 Module 6 files changed:

- Source: `src/multi_agent_orchestration/adapters.py`, `contracts.py`,
  `execution.py`, `collaboration.py`, `_crewai_adapter.py`, `_crewai_worker.py`.
- Tests: `tests/test_crewai_collaboration.py`, `tests/test_registry.py`.
- Docs: `docs/CREWAI_COLLABORATION.md`, `PROJECT_STATUS.md`, `TRACEABILITY.md`,
  `RUNTIME_FOUNDATION.md`, `LANGGRAPH_COORDINATOR_WORKER.md`. Historical milestone
  documents receive only superseding references; their accepted evidence remains.

## Definition-of-Done Assessment and Limits

Requirements: partial evidence for M6-007, M6-008, M6-011, M6-022, M6-025 and
M6-026; all 26 statuses remain Planned because source/lab/platform acceptance is
pending. Product: a runnable service example, no UI/human lab review. Functionality:
genuine CrewAI orchestration with deterministic agent roles, no AI inference.
Reliability: bounded local tasks/messages, deadline and process cleanup; no retry,
recovery, persistent/shared distributed memory, or scale evidence. Security:
validated output/provenance and offline guards; authentication/deployment controls
unverified. Cost: zero model/provider execution; local CPU/storage still consume
resources. Evidence: deterministic local orchestration only. Deployment: none;
no production-readiness or complete Module 6 claim.
