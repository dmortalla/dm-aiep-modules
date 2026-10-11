# Deterministic LangGraph Topologies

Starting branch: `feature/module-06-architecture`; clean HEAD
`9d1986fda20ec951e79b900640fdaa109e538f8c` (`feat: add deterministic google adk orchestration`).
This bounded expansion preserves Architecture B+, frozen source requirements,
dependencies, root configuration, historical modules, and accepted runtimes.

## Native execution

The existing LangGraph adapter dispatches an explicitly selected `GraphTopology`
to real `StateGraph` objects, `compile()`, and compiled `ainvoke()`. Private SDK
state carries an `Annotated` immutable contribution reducer. Domain contracts
and semantic validation contain no framework types.

| Topology | Actual nodes/edges | Work/concurrency/depth |
| --- | --- | --- |
| Sequential | START -> researcher -> analyst -> critic -> END | 3 steps, 1 task at a time, depth 0 |
| Parallel | START -> fanout -> left AND right -> aggregate -> END | 4 steps, at most 2 tasks, depth 1 |
| Hierarchical | START -> supervisor_delegate -> lead_delegate -> specialist -> lead_validate -> supervisor_synthesize -> END | 5 steps, 1 task at a time, depth 2 |

Each topology has three bounded contributing roles. Sequential researcher counts
instruction characters, analyst consumes validated research, and critic consumes
validated research/analysis and synthesizes the result. Three roles preserve the
existing hard task/message ceiling rather than expanding it for a fourth role.

Parallel branches receive the same validated parent context. Native scheduling
executes both async branch nodes under `max_concurrency=2`; a cooperative yield
allows overlap. `add_edge(["left", "right"], "aggregate")` is a native waiting
barrier. The immutable reducer sorts by canonical sequence, rejects duplicates,
and bounds the collection. Aggregation validates both branches independently
before consuming them. Tests hold both native branch bodies at a barrier before
either can finish, observe peak concurrency two, force either completion order,
and verify identical ordered evidence. This proves local overlap, not throughput
improvement for tiny character-counting work or a scaling benchmark.

Hierarchical graph phases enforce supervisor -> lead -> specialist delegation,
then specialist -> lead validation -> supervisor synthesis. Only the authorized
role can advance each phase; the specialist cannot delegate or promote itself.
Two immutable assignments encode parent, child and depth. Fixed depth two and
five graph invocations prevent recursive or unbounded delegation. This is a
local role hierarchy, with genuine native down/up graph execution, not remote
or distributed workers.

## Application authority and bounds

`WorkflowRequest.topology` defaults to `coordinator_worker`. Other topology values
require explicit LangGraph selection; fixture, CrewAI and ADK reject them. There
is no runtime or topology fallback. Existing default graph behavior is preserved.

Example through the existing application service:

```python
import asyncio
from multi_agent_orchestration.contracts import (
    ExecutionLimits, GraphTopology, RuntimeId, TaskInput, WorkflowRequest,
)
from multi_agent_orchestration.execution import execute_workflow

request = WorkflowRequest(
    runtime=RuntimeId.LANGGRAPH,
    topology=GraphTopology.PARALLEL,
    task=TaskInput(instruction="Summarize this deterministic example."),
    limits=ExecutionLimits(max_steps=4, timeout_ms=1000),
)
result = asyncio.run(execute_workflow(request))
print(result.result.output)
print(result.evidence)
```

Steps require 3/4/5 respectively; tasks/messages require three. Existing hard
ceilings remain 32 steps, three tasks/messages, 4096 instruction characters and
30000 ms. New strict limits have hard ceilings of two for concurrency and
hierarchy depth; callers can reduce them. Parallel needs concurrency two;
hierarchy needs depth two. Insufficient budgets fail before graph compilation
or execution. These caps apply per workflow; no repository-wide queue or global
active-workflow limiter is introduced.

Frozen, extra-forbidding contracts bind workflow/task identities, explicit
topology, limits, phase, closed roles, ordered source roles and parent authority.
At most three messages of 256 characters and two delegation records cross graph
boundaries. Fresh schema validation also checks nested constructed models.
Every candidate node update is checked against exact permitted fields and
canonical application semantics before native channels can discard unknown
fields. Final adapter/application validation precedes trusted evidence creation.
Evidence includes bounded payload-free provenance; raw instruction/messages,
credentials, authority and policy are not evidence fields. Injection text stays
data and cannot change routing, delegation, limits or runtime.

## Offline execution and cleanup

Roles count characters and process validated upstream context; they do not
invoke models or tools. Model/external calls and retries remain zero. Credential,
provider and tracing flags do not enable calls. LangSmith tracing is explicitly
disabled during invocation; this is not telemetry delivery. Existing unchanged
Module 6 non-loopback socket/DNS guards verify zero attempted external access,
including attempts swallowed by a library. Zero inference calls do not mean
CPU resources are free, and no provider-reported or invented monetary estimate
is emitted.

The application deadline/caller cancellation surrounds invocation. Native
LangGraph async execution cancels and awaits pending branch work on failure or
cancellation. New nodes use no child processes or unmanaged threads. Tests prove
both branch finalizers execute and no new pending asyncio task remains after
branch error, invalid output, timeout or caller cancellation. Typed public errors
are sanitized; internal diagnostic causes remain chained.

## Evidence and limits

117 new tests execute real compiled graphs, inspect native edges/configuration
and role handoffs, prove overlap/fan-in, and attack identities, parents, source
order, nested state, authority, budgets, runtime selection and final evidence.
All 365 Module 6 tests pass, including existing fixture, default LangGraph,
CrewAI and ADK regressions.

Final validation using Python 3.12.14 and the authoritative root configuration:

- Focused topology suite: **117 passed in 2.02 s**.
- Complete Module 6 suite: **365 passed in 58.38 s**, no skips/warnings.
- Root collection: **2486 tests**, exactly 117 above the accepted ADK baseline.
- Complete root pytest: **2480 passed, 6 skipped, 3 existing ChromaDB warnings
  in 157.99 s**. Existing conditional live/memory skips remain unchanged.
- Ruff passed; only safe import sorting was mechanically autofixed, no unsafe fixes.
- Compileall passed over all six established source/test directory pairs.
- Offline uv lock check, sync check and installed dependency check passed:
  239 locked packages, 216 installed packages, sync would make no changes.
- Six isolated installed imports outside the repository passed under a network
  guard; the documented parallel example also ran with zero external attempts.
- Whitespace and scope checks passed. Exactly ten Module 6 files changed;
  historical modules, existing tests/network guard, root configuration, lock,
  architecture, source requirements and governance are unchanged. CrewAI/ADK
  adapter classes and default LangGraph construction/compilation are preserved.

Requirements: partial M6-001/002/003 evidence and supporting contracts only;
all 26 remain Planned. Product experience: documented service use, console and
human acceptance pending. Real functionality: three genuine local LangGraph
topologies with deterministic roles, no live AI. Reliability/security/cost:
bounded execution, adversarial and cleanup evidence, zero inference calls.
Evidence: deterministic local tests; deployment: unverified. Persistence,
distributed execution, scaling, observability delivery, UI, lab completion and
production readiness are not established.
