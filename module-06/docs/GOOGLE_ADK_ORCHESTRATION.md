# Deterministic Local Google ADK Orchestration

## Scope and feasibility

Starting branch: `feature/module-06-architecture`; clean HEAD
`d10529eb93054fdd7105bc3224e04f920d3fbe39`,
`feat: add deterministic crewai collaborative workflow`.

The installed Google ADK **2.11.0** source and an offline native execution probe
demonstrated that custom `BaseAgent._run_async_impl` implementations can run
without an LLM. The current `Workflow` API was selected rather than the installed
deprecated `SequentialAgent`. No dependency, source requirement, Architecture B+,
ADR, root configuration, or historical-module change is needed.

This is real **local deterministic multi-agent orchestration**. Three agents run
inside one isolated local child process. Parent/child IPC provides execution
isolation, not distributed workers, remote services, or distributed processing.
M6-005, M6-018, and M6-023 remain Planned/unverified. All 26 requirement statuses,
lab/deliverable acceptance, and platform readiness remain unchanged.

## Native flow and ownership

`_adk_adapter.py` constructs three custom native BaseAgents, connected by
`Workflow(name="bounded_adk", edges=[(START, coordinator, specialist, validator)],
max_concurrency=1)`. A fresh `InMemoryRunner(node=workflow)` and
`InMemorySessionService` session execute through `Runner.run_async`. The native
Workflow/NodeRunner machinery schedules agents and transports `Event` /
`EventActions.state_delta` updates through invocation context and session state.

| Role | Application-owned behavior | Validated upstream context |
| --- | --- | --- |
| adk_coordinator | Assign the bounded input to adk_specialist | Original request; no prior messages |
| adk_specialist | Consume the assignment and report the character count | Exactly the coordinator message |
| adk_validator | Validate the specialist result and complete | Exactly the coordinator and specialist messages |

The instruction is inert data. Only its character count affects output. There
is one delegation and exactly three role events, with no branches, tools,
dynamic transfers, inference, loops, or retries. Native execution supplies
ordering, state transport, and synchronization; application functions supply
strict role semantics. No complete framework execution path is replaced.

## Application trust boundary

`orchestration.py` contains SDK-independent semantics. Frozen, extra-field-
rejecting `OrchestrationState`, `OrchestrationMessage`, and payload-free
`OrchestrationRecord` contracts bound state to three messages of at most 256
characters. Each message carries workflow/task UUIDs, a closed role, sequence,
and exact upstream source roles. The original request is retained outside ADK.

Every role revalidates framework session context against that request and the
expected message prefix. Native events must have the exact role/order, validated
output state, and matching state delta. Transfers, routes, artifact/auth/tool
actions, extra state keys, model usage, and content outside this contract are
rejected. Final session identities/state are checked again. SDK random IDs and
timestamps do not become trusted evidence.

The child returns only an application `RuntimeOutput`. Both the parent adapter
and `execute_workflow` revalidate its schema, identities, provenance, exact
deterministic content, resource limits, and explicit GOOGLE_ADK runtime. The
application constructs successful evidence afterward, never from agent-supplied
evidence. Nested Pydantic construction/copy bypasses are revalidated. There is no
credential-based selection or fixture/LangGraph/CrewAI/provider fallback.

## Offline and reliability controls

`GoogleADKRuntime` runs `_adk_worker.py` using isolated Python (`-I`), a fresh
temporary home/current directory, and an environment allowlist containing only
Windows runtime essentials and fixed local settings. Parent credentials,
provider/auth settings, OTLP endpoints, and tracing opt-ins are not inherited.
`OTEL_SDK_DISABLED=true` disables export; experimental ADK telemetry is disabled.
Sessions, artifact service, and memory service are in-memory and per-run; no
persistent/distributed application memory or external storage is used.

Before SDK import, the child guards non-loopback DNS/connect/connect_ex. Even a
swallowed denial prevents successful output. Loopback is permitted for Windows
asyncio machinery. This guard bounds this trusted deterministic implementation;
it is not an OS sandbox for hostile Python extensions. Tests retain the existing
parent network guard and separately exercise swallowed denial behavior.

No LlmAgent, model client, provider, tools, or plugins are instantiated. Native
execution tests reject Gemini/LLM/client and span-export processing calls.
Successful evidence records **model_calls=0, external_calls=0, retries=0**.
ADK interprets `max_llm_calls=0` as unlimited: its defensive run configuration
uses 1, while the application authorizes no model path. That SDK ceiling is not
permission to perform a model call. This slice makes no inference or hosted
telemetry charges; local CPU/process startup still consumes resources.

At least three steps/tasks/messages must be authorized before spawning/building,
and each role checks its bounds before advancing state. Execution limits retain
the existing ceilings (32 steps, three tasks/messages, 30 seconds). The service
deadline covers subprocess startup and execution. On timeout or caller
cancellation, including cancellation during spawn, the parent kills and reaps
the child before deleting temporary state. Native in-process cancellation tests
also verify ADK cancels/gathers its pending agent tasks. Public typed errors omit
task/credential/output payloads; bounded private causes retain diagnostics and
must not be exposed in future UI or telemetry.

## Operation

Use the synchronized repository Python 3.12 environment, without credentials:

```python
import asyncio
from multi_agent_orchestration.contracts import (
    ExecutionLimits, RuntimeId, TaskInput, WorkflowRequest,
)
from multi_agent_orchestration.execution import execute_workflow

request = WorkflowRequest(
    runtime=RuntimeId.GOOGLE_ADK,
    task=TaskInput(instruction="bounded context"),
    limits=ExecutionLimits(max_steps=3, timeout_ms=30_000),
)
result = asyncio.run(execute_workflow(request))
print(result.result.output)  # ADK validation accepted 15 characters.
print(result.evidence.model_dump_json())
```

SDK startup counts toward the deadline; the default one-second fixture deadline
may be too short. The caller explicitly selects an appropriate bounded deadline;
the application never increases it automatically. `GoogleADKRuntime.info` now
reports `execution_available=True`, `deterministic_multi_agent`, and the installed
version. Fixture remains the default; LangGraph and CrewAI remain independently
selectable.

## Evidence and remaining work

`test_adk_orchestration.py` observes real Workflow/Runner/NodeRunner/BaseAgent
execution, ordered context updates, no model/exporter calls, native/child failure
and cleanup, concurrent isolation, repeatability with ambient dummy credentials,
prompt injection, forged state/provenance/actions/output/evidence, budget denial,
and nested Pydantic bypasses. The former construction-only registry case is
strengthened to check real agents plus direct and service execution.

Partial evidence applies to M6-006/007/009/010/013/015/020; local prerequisites
only apply to M6-005/023/026. No distributed orchestration/processing acceptance,
live AI, UI, persistent memory, telemetry delivery, scaling benchmark, deployment,
full lab/deliverable completion, or production readiness is claimed.

Definition-of-Done review: requirements remain partially evidenced; product
experience is the documented application service (console pending); real local
SDK functionality exists; reliability/security/cost controls are tested within
this slice; complete platform evidence and deployment remain pending.

## Final verification

The interrupted work was recovered on the same branch/accepted HEAD with all
12 dirty Module 6 files attributable to this story. Nothing was reset, stashed,
discarded, or recreated. Pre-interruption evidence was reverified. Direct adapter
revalidation was additionally strengthened for preconstructed nested output.

| Gate | Actual result |
| --- | --- |
| Repository Ruff | PASS; safe fixes only, no unsafe fixes |
| Complete Module 6 suite | **248 passed**, no skips/warnings, 58.77 seconds |
| Complete root pytest | **2,363 passed, 6 skipped, 3 existing ChromaDB warnings**, 203.33 seconds |
| Independent root collection | **2,369 collected**, 10.03 seconds |
| compileall | PASS over all six modules' source/test directories |
| uv lock / sync / installed consistency | PASS; 239 locked, 216 installed, sync would make no changes |
| Six isolated installed imports | PASS outside repository with zero connection/DNS attempts |
| Whitespace / scope | PASS; exactly 12 Module 6 files, no historical-module changes |

The 64 new parametrized ADK cases are in 18 test functions; the existing registry
case is strengthened rather than removed. The collection increase is exactly 64
over the accepted 2,305 baseline. Fixture, LangGraph, and CrewAI regressions pass;
their accepted implementations and the existing test network guard are unchanged.
Genuine execution made zero guarded non-loopback attempts; separate adversarial
denial tests prove swallowed attempts cannot result in success.

Changed source files: `adapters.py`, `contracts.py`, `execution.py`,
`orchestration.py`, `_adk_adapter.py`, `_adk_worker.py`. Changed tests:
`test_adk_orchestration.py`, `test_registry.py`. Changed documentation: this record,
`PROJECT_STATUS.md`, `RUNTIME_FOUNDATION.md`, `TRACEABILITY.md`.
`pyproject.toml`, `uv.lock`, Modules 1–5, frozen requirements, Architecture B+,
ADRs, security/cost policy, and provider strategy remain unchanged.
