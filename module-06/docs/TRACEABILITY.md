# Module 6 Traceability

This is the single authoritative Module 6 requirement-to-evidence record. The 26
source requirement IDs and meanings are frozen in
[SOURCE_REQUIREMENTS.md](SOURCE_REQUIREMENTS.md) and are reproduced here
verbatim; nothing is renamed or reinterpreted. Engineering status and gate
provenance live in [PROJECT_STATUS.md](PROJECT_STATUS.md).

## Final reconciliation (S7 candidate)

Baseline: `feature/module-06-architecture` at
`998b0d8da8cadc4cb0e9a2230dbe8b1e39276161` (S1–S6 accepted and committed). The
statuses below are the S7 candidate's reconciliation of the earlier
slice-by-slice records; they take effect only when S7 is independently accepted
and committed. They rest on evidence already in the repository; no new
execution, inference or external operation was performed to produce them.

The status transition follows the human closeout decisions of 2026-10-13
(deterministic agents accepted as verified-with-limitation evidence for
M6-022/025/026 at transition; the console is a local, loopback-only reviewer
system; hosted deployment is a separate gate). The slice sections further below
are dated historical records: where they say "Planned", "candidate" or "pending",
that was true when written and is superseded by this section.

### Status legend

- `Planned` - requirement frozen; implementation not yet accepted.
- `Implemented` - implementation exists but final evidence is incomplete.
- `Verified` - implementation and required evidence are accepted without a
  material limitation.
- `Verified with limitation` - implementation and evidence are accepted, with the
  documented limitation stated for that requirement.

No requirement is `Verified` without limitation, and none is `Planned` or
`Implemented`. `Verified with limitation` never means production, hosted,
SLA/SLO, load-tested, cloud-scale or statistically reliable.

### Summary

| ID | Source requirement | Final status | Evidence classification |
| --- | --- | --- | --- |
| M6-001 | Demonstrate sequential agents. | Verified with limitation | deterministic (+ real-local canonical) |
| M6-002 | Demonstrate parallel agents. | Verified with limitation | deterministic |
| M6-003 | Demonstrate hierarchical agents. | Verified with limitation | deterministic |
| M6-004 | Demonstrate coordinator-worker systems. | Verified with limitation | deterministic |
| M6-005 | Demonstrate distributed orchestration. | Verified with limitation | deterministic; local multi-process |
| M6-006 | Demonstrate context passing. | Verified with limitation | deterministic (+ real-local canonical) |
| M6-007 | Demonstrate inter-agent communication. | Verified with limitation | deterministic |
| M6-008 | Demonstrate shared memory. | Verified with limitation | deterministic |
| M6-009 | Demonstrate task delegation. | Verified with limitation | deterministic |
| M6-010 | Demonstrate workflow synchronisation. | Verified with limitation | deterministic; local multi-process |
| M6-011 | Use CrewAI meaningfully. | Verified with limitation | deterministic |
| M6-012 | Use LangGraph meaningfully. | Verified with limitation | deterministic; real-local canonical |
| M6-013 | Use Google ADK meaningfully. | Verified with limitation | deterministic; local multi-process |
| M6-014 | Use LangSmith meaningfully. | Verified with limitation | local projection; `service_read`; `unverified_write` |
| M6-015 | Implement workflow state management. | Verified with limitation | deterministic |
| M6-016 | Implement execution tracing. | Verified with limitation | application trace; LangSmith; local operational telemetry |
| M6-017 | Demonstrate scaling workflows. | Verified with limitation | deterministic; local single-host measurement |
| M6-018 | Demonstrate distributed processing. | Verified with limitation | deterministic; local multi-process |
| M6-019 | Demonstrate cost optimisation. | Verified with limitation | deterministic zero-call; real-local accounting |
| M6-020 | Demonstrate reliability patterns. | Verified with limitation | deterministic; local operational alert rules |
| M6-021 | Build a coordinator-worker workflow. | Verified with limitation | deterministic |
| M6-022 | Create a collaborative AI system. | Verified with limitation | deterministic (+ real-local canonical) |
| M6-023 | Implement distributed orchestration. | Verified with limitation | deterministic; local multi-process |
| M6-024 | Deliver a multi-agent orchestration platform. | Verified with limitation | local Streamlit cockpit |
| M6-025 | Deliver a collaborative AI workflow. | Verified with limitation | deterministic; synthetic; real-local canonical |
| M6-026 | Demonstrate scalable AI system orchestration using multi-agent architectures. | Verified with limitation | deterministic; local single-host measurement |

### Evidence vocabulary used below

- *Deterministic*: real framework execution with deterministic (non-model)
  agents; zero model, provider and external calls.
- *Synthetic*: the canonical live workflow driven by a fixed synthetic gateway;
  receipts classified `synthetic_offline`.
- *Real-local*: the canonical workflow with local Ollama inference
  (`local_provider_execution`). Recorded runs: Run 3 `out_of_policy_observation`
  (a technical timing observation, never an authorized live success); Run 4
  "Authorized current-path real-local verification" (no recorded identifier);
  Run 5 below. Four recorded real runs is a floor, not a proven total.
- *Local projection*: LangSmith/OpenTelemetry/metric projections built locally
  after a run; never external delivery.
- *External write / confirmation*: `service_read` (the service returned the
  recorded run) and `unverified_write` (HTTP 2xx write, no read-back) are
  distinct and never merged.
- The five accepted presentation dimensions are `execution_kind`, `provenance`,
  `delivery_confirmation`, `operational_classification` and `source`
  (`fresh_execution` or `recorded_historical`).

Source directory: `../src/multi_agent_orchestration/`; tests: `../tests/`.
Cockpit tabs (`../app.py`, Guide first): Guide, Deterministic Demo, Live / BYOK,
Operations, LangSmith Tracing, Implementation Evidence. The first five tabs were
the cockpit at S6 acceptance; the Implementation Evidence tab (abridged verbatim
source excerpts naming file and function, never proof of delivery or service
state) and the Guide-first ordering are later presentation updates.

### Per-requirement evidence

**M6-001 Sequential agents - Verified with limitation.**
Implementation: sequential LangGraph topology (`topologies.py`,
`_langgraph_topologies.py`); the canonical Researcher -> Analyst -> Critic
workflow (`canonical_workflow.py`, `live_execution.py`). Tests:
`test_langgraph_topologies.py` (actual compile/invoke, ordering, validated
handoff), `test_canonical_workflow.py`, `test_live_execution.py`. Reviewer
surface: Demo "LangGraph sequential" and the synthetic canonical workflow; Live
tab for the trusted-local run. Limitation: fixed roles and topology; agents are
deterministic outside the real-local canonical runs, whose quality is not
claimed.

**M6-002 Parallel agents - Verified with limitation.**
Implementation: native two-branch fan-out with waiting-edge fan-in under a
per-run cap of two (`_langgraph_topologies.py`, `topologies.py`). Tests:
`test_langgraph_topologies.py` (barrier-proven overlap, both completion orders,
cleanup). Reviewer surface: Demo "LangGraph parallel". Limitation: concurrency
inside one local workflow only; the scaling benchmark varies concurrency between
workflows and adds no parallel-agent evidence.

**M6-003 Hierarchical agents - Verified with limitation.**
Implementation: supervisor -> lead -> specialist delegation, depth two
(`topologies.py`, `_langgraph_topologies.py`). Tests:
`test_langgraph_topologies.py` (role/phase execution, depth and work limits,
authority-forgery denial). Reviewer surface: Demo "LangGraph hierarchical".
Limitation: a fixed local hierarchy, not dynamic delegation.

**M6-004 Coordinator-worker systems - Verified with limitation.**
Implementation: coordinator -> worker -> coordinator validation
(`coordinator_worker.py`, `adapters.py`). Tests: `test_langgraph_workflow.py`.
Reviewer surface: Demo "LangGraph coordinator-worker". Limitation: one local
worker per run in this topology; multi-process workers are M6-005.

**M6-005 Distributed orchestration - Verified with limitation.**
Implementation: coordinator dispatch of serialized assignments to two
independent local ADK worker interpreters (`distributed.py`,
`distributed_contracts.py`, `distributed_execution.py`,
`_distributed_processes.py`, `_distributed_worker.py`, `_distributed_adk.py`).
Tests: `test_distributed_orchestration.py` (distinct PIDs, serialized IPC,
barrier, replay/forgery, cleanup); `test_benchmark.py`. Reviewer surface: Demo
"Local multi-process distributed orchestration" (worker PIDs, reaping).
Limitation: genuine multi-process on one host; no remote-host, cluster or cloud
distribution is claimed.

**M6-006 Context passing - Verified with limitation.**
Implementation: typed immutable workflow context (`contracts.py`) revalidated at
every handoff (`topologies.py`, `collaboration.py`, `orchestration.py`,
`distributed.py`). Tests: `test_contracts.py`, `test_langgraph_workflow.py`,
`test_langgraph_topologies.py`, `test_crewai_collaboration.py`,
`test_adk_orchestration.py`. Reviewer surface: validated evidence per result.
Limitation: per-run bounded context; no persistent or global context store.

**M6-007 Inter-agent communication - Verified with limitation.**
Implementation: validated CrewAI `Task.context` exchange (`_crewai_adapter.py`),
ADK role events (`orchestration.py`, `_adk_adapter.py`), bounded serialized
inter-process packets (`distributed.py`, `distributed_contracts.py`). Tests:
`test_crewai_collaboration.py`, `test_adk_orchestration.py`,
`test_distributed_orchestration.py` (forgery and malformed-packet rejection).
Limitation: fixed role-to-role protocols; no general messaging system.

**M6-008 Shared memory - Verified with limitation.**
Implementation: bounded immutable workflow-scoped collaboration state
(`collaboration.py`, `CollaborationState`; at most three 256-character messages
with owner/source checks). Tests: `test_crewai_collaboration.py` (provenance,
bounds, concurrent isolation). Limitation: workflow-scoped only; there is no
persistent, global or distributed memory, by design.

**M6-009 Task delegation - Verified with limitation.**
Implementation: coordinator-owned assignment before result generation
(`coordinator_worker.py`), fixed hierarchical delegation (`topologies.py`),
launcher-bound worker assignments with explicit release (`distributed.py`).
Tests: `test_langgraph_workflow.py`, `test_langgraph_topologies.py`,
`test_distributed_orchestration.py`. Limitation: fixed, authorized delegation;
no dynamic or remote delegation.

**M6-010 Workflow synchronisation - Verified with limitation.**
Implementation: finite ordered graph edges and validated completion
(`adapters.py`), native fan-in join (`_langgraph_topologies.py`), IPC start
barrier with deterministic fan-in (`_distributed_processes.py`). Tests:
`test_langgraph_workflow.py`, `test_langgraph_topologies.py`,
`test_distributed_orchestration.py` (both workers active at the barrier).
Limitation: single-host synchronisation; no distributed failure recovery.

**M6-011 CrewAI - Verified with limitation.**
Implementation: real `Crew`/`Task` kickoff, sequential scheduling, task
ownership/context and callbacks with deterministic `BaseAgent` role executors
(`_crewai_adapter.py`, `_crewai_worker.py`, `collaboration.py`). Tests:
`test_crewai_collaboration.py` (real kickoff/scheduler/task spies, child
execution, external-access denial). Reviewer surface: Demo "CrewAI
collaboration". Limitation: no LLM behind the CrewAI agents; the model-backed
collaboration is the separate LangGraph canonical workflow.

**M6-012 LangGraph - Verified with limitation.**
Implementation: real compiled and invoked `StateGraph` for four topologies
(`adapters.py`, `_langgraph_topologies.py`) and the canonical live graph
(`live_execution.py`). Tests: `test_langgraph_workflow.py`,
`test_langgraph_topologies.py`, `test_live_execution.py`. Limitation: model
inference occurs only in the recorded trusted-local canonical runs.

**M6-013 Google ADK - Verified with limitation.**
Implementation: real `Workflow`/`Runner`/`BaseAgent` execution
(`_adk_adapter.py`, `orchestration.py`), including one native role per worker
process (`_distributed_adk.py`). Tests: `test_adk_orchestration.py`,
`test_distributed_orchestration.py`. Reviewer surface: Demo "Google ADK
orchestration". Limitation: deterministic roles; no model-backed ADK.

**M6-014 LangSmith - Verified with limitation.**
Implementation: local RunTree tracing adapter (`observability_adapters.py`
`LocalLangSmith`); explicit deterministic delivery (`langsmith_delivery.py`,
`run_langsmith.py`); live-family local projection and delivery
(`live_langsmith.py`); read-only recorded-evidence boundary
(`cockpit_langsmith.py`). Tests: `test_observability.py`,
`test_langsmith_delivery.py`, `test_live_langsmith.py`,
`test_cockpit_langsmith.py`. Evidence, kept distinct:
(1) the deterministic sanitized trace `01a166fa-1c8d-7b40-9686-a08cfd14444f`
delivered once to project `module6-verification` (202, 4 runs accepted) and read
back - classification "current-path external LangSmith delivery verification",
`service_read`, independently accepted 2026-10-22; evidence artifact held
outside the repository; (2) Run 5, trace `e48944ac-1e67-4562-b6e7-e3cab5abbb4c`,
classified exactly: "One-run live-model current-path LangSmith projection and
delivery verification (`unverified_write` receipt); authority-consumption status
operator-attested and not independently confirmed." Reviewer surface: the
LangSmith tracing tab shows both as recorded/historical, never merged, with an
explicit read-only inspection that reports unavailable on the stock page.
Limitation: Run 5 has no service-read confirmation, so live-model traces are not
read back; not every live run is delivered or read back; the LangSmith project
must not be claimed to hold exactly one Run 5 trace.

**M6-015 Workflow state management - Verified with limitation.**
Implementation: typed immutable phases and bounded transition history
(`contracts.py`, `coordinator_worker.py`), per-run evidence, and bounded
revalidated session views (`console.py` `ConsoleSession`). Tests:
`test_contracts.py`, `test_langgraph_workflow.py`, `test_console.py`,
`test_console_app.py`, `test_cockpit_*.py`. Limitation: in-memory, per-run and
per-browser-session state; no persistence.

**M6-016 Execution tracing - Verified with limitation.**
Three layers, none claimed beyond what exists. (a) Application trace/evidence
contracts: payload-free correlated `RunTrace` and live terminal observations
(`observability.py`, `observability_contracts.py`, `live_observation.py`). (b)
LangSmith AI/agent tracing (M6-014). (c) Operational telemetry:
OpenTelemetry -> OTel Collector -> Prometheus -> Grafana, metrics only
(`observability_adapters.py`, `live_otel.py`, `live_metrics.py`,
`live_metric_delivery.py`, `telemetry_delivery.py`, `run_telemetry.py`,
`../telemetry/`). Tests: `test_observability.py`, `test_live_observation.py`,
`test_live_otel.py`, `test_live_metrics.py`, `test_live_metric_delivery.py`,
`test_telemetry_delivery.py`. Verified end-to-end locally on 2026-10-23 as an
"authorized deterministic local operational-telemetry pipeline verification"
(14/14 workflows, 3 alert rules loaded, dashboard provisioned). Limitation: per
ADR-006 and the Collector configuration (metrics pipeline only; traces and logs
have no pipeline) no additional trace or log storage backend exists or is
claimed; the stack is local and loopback-only, not hosted, public or production.

**M6-017 Scaling workflows - Verified with limitation.**
Implementation: opt-in bounded benchmark at admission caps 1, 2 and 4
(`benchmark.py`, `run_benchmark.py`) and throughput/active/worker-reaping
metrics with a provisioned Grafana dashboard. Tests: `test_benchmark.py`,
`test_telemetry_delivery.py`. Reviewer surface: the Demo tab's local scaling
benchmark. Evidence: one local run on 2026-10-12 completed 8 of 8 workflows at
each cap in 28.09 s, 15.68 s and 9.68 s on one Windows workstation. Limitation:
deterministic, single-host and machine-specific; speedup is descriptive, not a
pass criterion. No production load test, capacity, saturation, queue/utilisation
or cloud/horizontal scaling is claimed.

**M6-018 Distributed processing - Verified with limitation.**
Implementation: two independent worker processes process disjoint fragments
through native ADK roles; the benchmark runs up to eight concurrently (see
M6-005, M6-017). Tests: `test_distributed_orchestration.py`,
`test_benchmark.py`. Limitation: one host; no remote, cluster or cloud
processing.

**M6-019 Cost optimisation - Verified with limitation.**
Implementation: deterministic zero-cost default; per-run budgets, deadlines and
call/repair/retry bounds (`live_contracts.py` `LiveBudget`); the ADR-008 NORMAL
profile as policy data (`live_policy.py`); no silent escalation and credentials
never authorize spending; validated call/token/latency accounting with
unavailable values never invented (`COST_GOVERNANCE.md`). Tests:
`test_live_policy.py`, `test_live_contracts.py`, `test_execution.py`,
`test_canonical_workflow.py`. Evidence: Run 4 and Run 5 record local compute with
provider charge classified `no_provider_charge_local_compute`. Limitation: no
hosted-provider pricing, estimated or provider-reported monetary cost, or
comparative optimisation measurement exists.

**M6-020 Reliability patterns - Verified with limitation.**
Implementation: deadlines, cancellation, step/task budgets, fail-closed denial,
bounded single repair, supervised child processes with kill/reap, observation
failure isolation and three Prometheus alert rules (`execution.py`, `errors.py`,
`live_execution.py`, `observability.py`, `../telemetry/rules/`). Tests:
`test_execution.py`, `test_live_execution.py`, `test_distributed_orchestration.py`,
`test_observability.py`, `test_telemetry_delivery.py`. Limitation: transport
retries are zero by design; there is no recovery, circuit breaker, host-failure
handling or alert routing; one alert was driven to firing locally and two were not
triggered. See the known timing observation in `PROJECT_STATUS.md`.

**M6-021 Coordinator-worker lab - Verified with limitation.**
Implementation: the accepted coordinator-worker workflow with a runnable offline
example (`LANGGRAPH_COORDINATOR_WORKER.md`) and the guided console. Tests:
`test_langgraph_workflow.py`, `test_console_app.py`. Limitation: deterministic
agents; the human browser review of the console is a separate release gate.

**M6-022 Collaborative AI system - Verified with limitation.**
Implementation: CrewAI collaboration (M6-011) and the canonical Researcher ->
Analyst -> Critic workflow with real-local, synthetic and deterministic modes.
Tests: `test_crewai_collaboration.py`, `test_canonical_workflow.py`,
`test_console_app.py`. Evidence: accepted as verified-with-limitation for
deterministic agents by the 2026-10-13 human decision; Run 4 is the authorized
real-local verification. Limitation: model output quality and semantic
correctness are not proven.

**M6-023 Distributed orchestration lab - Verified with limitation.**
Implementation: the accepted local process service with a runnable example
(`DISTRIBUTED_ORCHESTRATION.md`) and console exposure. Tests:
`test_distributed_orchestration.py`, `test_console_app.py`. Limitation: local
multi-process only; human browser review is a separate release gate.

**M6-024 Multi-agent orchestration platform - Verified with limitation.**
Implementation: the Streamlit reviewer cockpit (`../app.py`, `console.py`,
`cockpit_view.py`, `cockpit_ops.py`, `cockpit_langsmith.py`,
`cockpit_local_live.py`) over the accepted services; the five tabs accepted in
S1–S6 are Deterministic Demo, Live / BYOK, Operations, LangSmith Tracing and
Guide, with the later Implementation Evidence tab and a separate private-local
launcher (`../run_local_live.py`, `../private_local_app.py`,
`../private_local_runtime.py`) that supplies the trusted runtime to a private
operator only. Tests: `test_console.py`, `test_console_app.py`,
`test_console_live.py`, `test_cockpit_view.py`, `test_cockpit_demo.py`,
`test_cockpit_ops.py`, `test_cockpit_langsmith.py`, `test_cockpit_local_live.py`,
`test_cockpit_s6.py`, `test_private_local_launcher.py`. Limitation: delivered and
verified as a local, loopback
reviewer cockpit; human browser acceptance, hosted deployment verification and
release are separate, still-open gates. Public live execution is intentionally
unavailable (below).

**M6-025 Collaborative AI workflow - Verified with limitation.**
Implementation: the canonical workflow (`canonical_workflow.py`,
`canonical_contracts.py`, `live_execution.py`) with application-owned validation
and evidence. Tests: `test_canonical_workflow.py`, `test_live_execution.py`,
`test_cockpit_local_live.py`. Evidence: accepted for deterministic agents by the
2026-10-13 decision; synthetic runs classified `synthetic_offline`; real-local
Run 4 ("Authorized current-path real-local verification") with 3 calls, 0 repairs,
0 retries in 48,407 ms. Run 3 stays an `out_of_policy_observation`. Limitation:
structural validation is not proof of semantic correctness; the live repair path
is unexercised.

**M6-026 Scalable AI orchestration using multi-agent architectures - Verified with limitation.**
Implementation and evidence: the combined bounded orchestration architectures
(M6-001..005), three runtimes (M6-011..013), the local benchmark and operational
metrics (M6-017), distribution (M6-018) and the reviewer-visible cockpit.
Accepted as verified-with-limitation by the 2026-10-13 decision. Limitation:
local single-host, deterministic and machine-specific; no production scaling,
SLA, capacity or cloud-scale validation is claimed.

### Observability reconciliation

- AI / agent observability: LangSmith (M6-014).
- Operational observability: OpenTelemetry -> OTel Collector -> Prometheus ->
  Grafana, verified end-to-end locally only. The Collector has the accepted
  metrics pipeline only; no trace or log storage backend is implied.
- Unified reviewer presentation: the Streamlit cockpit, with no iframe,
  embedding or link to localhost services. Its only unsafe-HTML surface is one
  static, application-owned CSS block; no workflow, model, user, tool or
  provider value can flow into it.
- Not claimed: hosted production telemetry, public Grafana or Prometheus, an SLA,
  production deployment.

### Live / BYOK reconciliation

Deterministic, no-key Demo is the deployed-safe baseline. Local Live/BYOK is
trusted-operator only: BYOK means the trusted runtime brings its own provider
connectivity, never a public key textbox. Local Ollama inference does not itself
require a credential; a provider that needs one has it held by that runtime.
Credential presence never authorizes execution; each run needs a fresh single-use `LiveAuthorization` under the
ADR-008 NORMAL profile. Public/deployed live is fail-closed and no deployment
authority boundary exists. There is no automatic LangSmith write and no
automatic operational query; external writes need separate authority.

### Verification rule

No requirement becomes `Verified` merely because implementation exists.
Evidence must match the claim: simulated distribution cannot prove genuine
distributed execution; an installed dependency cannot prove meaningful framework
use; an adapter test cannot prove live remote tracing; an estimated cost cannot
be represented as provider-reported cost; deterministic fixture execution cannot
be represented as live-model evidence.

### Historical evidence log

The sections below are the slice-by-slice records as written at the time. They
are kept unchanged as history; any status or "candidate/pending" wording in them
is superseded by the reconciliation above.

## Live Observability Slice 4 (historical candidate record)

[Live metrics Slice 4](LIVE_METRICS_SLICE_4.md) records the additive candidate in
`live_metrics.py`, `live_metric_delivery.py` and their maintained tests. It adds
partial evidence toward M6-016/M6-019/M6-020: application-owned live operational
metrics, unknown-accounting coverage, closed cardinality, explicit bounded
one-shot OTLP delivery and workflow failure isolation. Evidence is offline SDK
and test-owned loopback only. External pipeline/storage, curated live UI,
continuous monitoring and independent Reviewer acceptance remain deferred.
All 26 source meanings and Planned statuses remain unchanged.

## Runtime Foundation Evidence (Partial Prerequisite Only)

All IDs, source meanings, and statuses remain unchanged. The following existing
requirements have prerequisite implementation evidence, not completion:

| Existing ID | Foundation reference | What remains unproved |
| --- | --- | --- |
| M6-011 | `../src/multi_agent_orchestration/adapters.py`; `../tests/test_registry.py` | Original construction evidence; now extended by deterministic collaborative execution below |
| M6-012 | `../src/multi_agent_orchestration/adapters.py`; `../tests/test_registry.py` | Original builder construction evidence; now extended by the deterministic slice below |
| M6-013 | `../src/multi_agent_orchestration/adapters.py`; `../tests/test_registry.py` | ADK base-agent construction only; delegation/distributed runtime remains Planned |
| M6-015 | `../src/multi_agent_orchestration/contracts.py`; `../tests/test_contracts.py` | Typed request/status/identity contracts; transitions now implemented below; persistence unimplemented |
| M6-019 | `../src/multi_agent_orchestration/fixture.py`; `../tests/test_execution.py`; `../tests/test_registry.py` | Zero-call offline fixture evidence only; live cost optimization/budgets not implemented |
| M6-020 | `../src/multi_agent_orchestration/execution.py`; `../tests/test_execution.py` | Boundary rejection/deadline/cancellation only; complete workflow reliability patterns not implemented |
| M6-024 | `../src/multi_agent_orchestration/runtime.py`; `../src/multi_agent_orchestration/registry.py`; `../tests/test_registry.py` | Runtime foundation only; platform and human-facing console not delivered |

[RUNTIME_FOUNDATION.md](RUNTIME_FOUNDATION.md) records exact scope and validation.
Minimal structured fixture evidence is not LangSmith execution tracing or
operational telemetry and does not complete M6-014 or M6-016. No lab, delivery,
scaling, collaboration, or distributed-execution requirement is marked complete.

## Deterministic LangGraph Slice Evidence

All 26 source IDs, meanings, and statuses are preserved. Planned means the source
requirement has not yet been accepted, not that no partial implementation exists.
This real local graph uses deterministic agent functions without AI inference.
It does not establish full platform/lab acceptance. The focused implementation
and final gate record are in [LANGGRAPH_COORDINATOR_WORKER.md](LANGGRAPH_COORDINATOR_WORKER.md).

| Existing ID | Implementation evidence | Tests and remaining limitation |
| --- | --- | --- |
| M6-004 | `coordinator_worker.py`, `adapters.py`: coordinator -> worker -> coordinator validation | Real topology/invocation and ordered node execution; broader systems and product acceptance pending |
| M6-006 | `contracts.py`: typed WorkflowState retains bounded request/task context | Context observed in each real node; forged context rejected; no shared memory implementation |
| M6-009 | `coordinator_worker.py`: explicit worker assignment before result generation | Worker cannot precede delegation; step budget enforced; only one local worker |
| M6-010 | `adapters.py`: finite ordered edges and validated terminal state | Validation waits for worker result; async timeout/caller cancellation; no distributed synchronization |
| M6-012 | `adapters.py`: actual StateGraph.compile and compiled.ainvoke | Spies observe real execution, fixed topology; missing/broken runtime cannot fall back; no live AI |
| M6-015 | `contracts.py`, `coordinator_worker.py`: immutable phases and bounded transition history | Nested Pydantic bypass, forged IDs/bounds/results rejected; concurrent run isolation; no persistence |
| M6-020 | `execution.py`, `errors.py`: deadline, cancellation, typed budget/output failures | Real graph worker cancellation and budget rejection; retries zero; no recovery/distributed reliability |
| M6-021 | `LANGGRAPH_COORDINATOR_WORKER.md`: runnable offline service example | `test_langgraph_workflow.py` exercises workflow and adversarial cases; human-facing lab/acceptance pending |

The existing non-loopback socket/DNS guard remains unchanged. Credential and
tracing-flag tests make zero external attempts. Evidence records three transitions,
explicit requested/actual LangGraph, identities, limits, and zero calls/retries;
it contains no raw instruction, authority, policy, credential, or remote trace.
CrewAI/ADK execution, collaboration, distribution, LangSmith delivery, operational
telemetry, and deployment remain unverified.

## Deterministic CrewAI Collaboration Evidence

[CREWAI_COLLABORATION.md](CREWAI_COLLABORATION.md) records the bounded slice and
quality evidence. `_crewai_adapter.py` exercises real Crew.kickoff, sequential
scheduling, Task.execute_sync, explicit Task ownership/context, validated callbacks,
and native completion. Custom BaseAgent implementations replace only local role
behavior at the SDK's abstract execution interface; there is no LLM or fake Crew.
`collaboration.py` owns immutable state/contribution validation, independent of
SDK types. `_crewai_worker.py` guards external access; `adapters.py` isolates each
run's environment/storage and cancels/reaps it. `execution.py` validates output
and creates payload-free ordered provenance evidence outside runtime output.

| Existing ID | Partial implementation/test evidence | Still unverified |
| --- | --- | --- |
| M6-007 | Real Crew context aggregates validated researcher/analyst contributions; context forgery tests | General inter-agent protocols and full platform acceptance |
| M6-008 | At most three immutable 256-character messages with owner/source/identity checks; concurrent isolated runs | Persistent/distributed/shared global memory |
| M6-011 | Real Crew/Task/BaseAgent objects and kickoff/scheduler/task execution observed by tests | Model-backed CrewAI collaboration and source acceptance |
| M6-022 | Offline role workflow, runnable example, adversarial and resource-bound tests | Human-facing collaborative AI lab acceptance |
| M6-025 | Research -> analysis -> critic refinement from actual validated upstream context | Full collaborative AI deliverable and product experience |
| M6-026 | Local bounded orchestration, deterministic repeatability, per-run isolation | Scalability, AI inference, complete objective acceptance |

All 26 IDs/meanings/statuses remain unchanged. This extends deterministic local
evidence only; it does not establish live AI, Google ADK/distribution, telemetry
delivery, UI, deployment, or production readiness. No requirement is marked
Complete or Verified. The accepted LangGraph evidence remains valid; its historical
CrewAI construction-only limitation is superseded by this slice.

## Deterministic Local Google ADK Evidence

[GOOGLE_ADK_ORCHESTRATION.md](GOOGLE_ADK_ORCHESTRATION.md) records the installed
2.11.0 APIs, local topology, operation, tests, and gates. `_adk_adapter.py` uses
real Workflow/Runner/BaseAgent machinery; `orchestration.py` owns immutable
semantic state and provenance; `_adk_worker.py` and `GoogleADKRuntime` enforce
credential-free process isolation and external-access denial. No SDK types
escape into domain contracts, and trusted evidence follows final application
validation. Earlier ADK construction-only records are historical.

| Existing ID | Partial implementation/test evidence | Still unverified |
| --- | --- | --- |
| M6-005 | Local bounded ADK multi-agent workflow prerequisite | Genuine distributed orchestration; remains Planned |
| M6-006 | Typed context transported through native session/event updates; handoff forgery rejection | Broader platform/distributed context acceptance |
| M6-007 | Three role events with validated owner/source/sequence and upstream data consumption | General inter-agent protocols and platform acceptance |
| M6-009 | Coordinator explicitly assigns adk_specialist; native scheduler executes only that role next | Remote/dynamic delegation |
| M6-010 | Ordered Workflow edges and validation after specialist completion; real scheduler spies | Distributed synchronization |
| M6-013 | Real Workflow, InMemoryRunner, custom BaseAgents, events, and session execution | Model-backed/distributed ADK and source acceptance |
| M6-015 | Immutable bounded state, exact provenance/request validation, concurrent isolation | Persistent/distributed state and console |
| M6-020 | Budget denial before execution, native cancellation, child timeout/cancel/reap, sanitized failures | Recovery, distributed reliability, operational alerts |
| M6-023 | Runnable local ADK prerequisite only | Genuine distributed orchestration lab acceptance; remains Planned |
| M6-026 | Three local runtimes with bounded deterministic orchestration evidence | Scaling, AI inference, complete objective acceptance |

All 26 IDs/meanings/statuses remain unchanged. M6-018 remains Planned/unverified;
three agents inside one process and parent/child isolation do not prove
distributed processing. No live inference, persistent memory, UI, remote
observability, deployment, lab completion, or production readiness is claimed.

## Deterministic LangGraph Topology Evidence

[LANGGRAPH_TOPOLOGIES.md](LANGGRAPH_TOPOLOGIES.md) describes the implementation
and gates. `topologies.py` owns immutable context, closed roles and delegation,
canonical provenance, budgets, and validation; `_langgraph_topologies.py` uses
real StateGraph compilation/invocation, native parallel scheduling, reducer, and
waiting-edge join. `test_langgraph_topologies.py` contains 117 new cases.

| Existing IDs | Partial evidence | Remaining limitation |
| --- | --- | --- |
| M6-001/002/003 | Actual compiled sequential, parallel and hierarchical execution; overlap and delegation observed | Full source/product acceptance |
| M6-006/007/008 | Validated immutable context/messages, ordered sources, concurrent isolation | General communication and persistent/distributed memory |
| M6-009/010 | Fixed authorized delegation, native fan-in after both branches, deterministic ordering | Dynamic/remote delegation and distributed synchronization |
| M6-012/015 | Native graph invocation, strict node updates before SDK channels, state/evidence rejection | Live AI, persistent state, operations console |
| M6-017/026 | Per-run concurrency cap two, depth two, finite work, isolation | Prerequisite only; no scaling/load benchmark |
| M6-019 | Zero inference/external calls and retries; budgets cannot authorize providers | No provider-reported cost or complete cost optimisation |
| M6-020 | Fail-closed branch error, timeout/cancellation and pending-task cleanup tests | Recovery/distributed reliability and operational alerts |
| M6-024 | Existing application service exposes explicit topology selection and validated evidence | Platform/UI and deployment remain pending |

All 26 source meanings and Planned statuses are preserved. Fixture, default
coordinator-worker, CrewAI, and ADK regressions pass independently. Offline
deterministic role processing is distinguished from live AI; no observability
delivery, deployment, lab acceptance, or production readiness is claimed.

## Deterministic Local Distributed Orchestration Evidence

[DISTRIBUTED_ORCHESTRATION.md](DISTRIBUTED_ORCHESTRATION.md) records explicit
serialized inter-process assignments/results, independent worker execution and
final gates. `distributed_contracts.py` and `distributed.py` own immutable
contracts and semantic validation; `distributed_execution.py` owns trusted
evidence and explicit selection; `_distributed_processes.py` owns pipe transport
and lifecycle; `_distributed_worker.py` guards the process boundary;
`_distributed_adk.py` executes one native role per worker. The new focused suite
contains 94 cases. All existing runtime source/tests remain unchanged.

| Existing IDs | Partial evidence | Remaining limitation |
| --- | --- | --- |
| M6-005/018 | Two independent local worker PIDs, distinct from coordinator; real disjoint fragment processing through native ADK | Remote-host/cluster/cloud distribution and full acceptance |
| M6-006/007 | Bounded serialized UTF-8 JSON in both directions, fresh worker/coordinator validation | General inter-agent transport protocols |
| M6-009 | Coordinator-owned identity/capability/parent/limits, launcher-bound assignment and explicit release | Dynamic or remote delegation |
| M6-010 | Both native roles active at IPC barrier, deterministic fan-in only after valid terminal responses | Distributed failure recovery and remote synchronization |
| M6-015 | Immutable per-run assignments/results, fresh single-use IDs, rejection of replay/duplicate/cross-run data | Persistent/shared distributed state and console |
| M6-017/026 | Fixed two-worker concurrency, four work steps, bounded lifecycle and concurrent-run isolation | Prerequisite only; no capacity, throughput or scaling benchmark |
| M6-020 | Real process failure/malformed-output/timeout/cancellation/spawn-race cleanup, all children reaped | Recovery, operational alerts and host-failure handling |
| M6-023 | Documented runnable real local distribution example and adversarial/process evidence | Full lab and human-facing acceptance |

This extends earlier ADK prerequisite evidence with genuine local multi-process
execution; it does not retroactively label the earlier sandboxed single-process
workflow distributed. All 26 IDs, meanings and Planned statuses remain intact.
No live AI, billable operation, remote telemetry, deployment, production horizontal
scaling or production readiness is claimed.

## Application-Owned Observation Evidence (Partial)

[Execution Observability](EXECUTION_OBSERVABILITY.md) records the new explicit
observation service, immutable contracts and local SDK adapters. All accepted
execution services and tests remain unchanged. Workflow start/terminal duration
is observed; role/worker child traces project validated completion provenance,
without inventing native task timing or successful accounting on failed runs.

| Existing ID | Partial evidence | Remaining limitation |
| --- | --- | --- |
| M6-014 | Actual local RunTree/child/end APIs, fixed project and no client/post/patch | Live LangSmith delivery and specialist review |
| M6-016 | Application-generated trace/span correlation; private OTel SDK providers, local spans/metrics; strict minimization/cardinality | OTLP wire delivery, collection, storage and native agent timing |
| M6-019 | Validated zero-call successes; explicit unavailable tokens/pricing/billing; bounded telemetry resources | Live cost optimisation, token/pricing policies and console |
| M6-020 | Collection failure isolation, timeout/cancellation/denial observation, real distributed reaping preservation | Remote delivery recovery, operational alerts and deployment |
| M6-026 | Bounded observation under concurrent workflows and accepted runtime integration | Production throughput, scaling, platform and full objective |

All 26 IDs, source meanings and Planned statuses remain unchanged. Offline SDK
integration is distinct from live trace delivery and deployed observability.
No console, additional stack, paid operation, remote telemetry, deployment or
production readiness is claimed by that slice. The console and the local
operational stack were added later and are recorded in the sections below.

## Additive Operations Console Evidence (Partial)

[Operations Console](OPERATIONS_CONSOLE.md) records guided local exposure of all
eight accepted demonstrations. New `console.py` owns validated commands and
curated views; Streamlit `app.py` owns presentation, and `run_console.py` fixes
loopback startup with usage analytics disabled. Existing runtime/observation
source/tests, frozen architecture, dependencies and Modules 1–5 are unchanged.

| Existing IDs | Partial evidence | Remaining limitation |
| --- | --- | --- |
| M6-015 | Bounded immutable curated session results, clear and separate browser sessions | Persistent/shared platform state |
| M6-016 | Correlated evidence/local trace references, role provenance, stale/unavailable observation labels | Live trace delivery and deployed specialist drill-down |
| M6-019 | Zero-call evidence, unavailable token/pricing/billing labels, bounded result retention | Live optimisation, pricing and full cost governance |
| M6-020 | Input/evidence denial, sanitized failures, latest-outcome selection, fail-safe observation degradation | Hosted capacity, recovery and operational alerts |
| M6-021/022/023 | Guided runnable coordinator-worker, CrewAI collaboration and real local distribution | Independent human/full lab and live AI acceptance |
| M6-024/025 | Runnable additive platform/accepted collaborative workflow surface | Complete deliverables, hosted operation and full acceptance |
| M6-026 | Guided reviewer experience across accepted bounded workflows | Production scaling, throughput and overall objective acceptance |

UI integration also exercises M6-001/002/003/004/005/011/012/013 through existing
accepted paths; it introduces no new runtime/source meanings. All 26 requirement
statuses remain Planned. UI existence does not complete or verify a requirement.

## Local Operational Telemetry Evidence (Partial)

[Operational Telemetry](OPERATIONAL_TELEMETRY.md) records opt-in loopback OTLP
metric delivery (`telemetry_delivery.py`, `run_telemetry.py`), the Compose stack
under `telemetry/` and `tests/test_telemetry_delivery.py`. Offline tests and the
manual local Docker run are separate evidence classes. Accepted runtime,
observation and console source/tests, dependencies and Modules 1-5 are unchanged.

| Existing IDs | Partial evidence | Remaining limitation |
| --- | --- | --- |
| M6-016 | Application-owned workflow metrics exported over OTLP, collected, stored and queried locally; identifiers excluded from metrics | Trace delivery, live LangSmith and hosted backends |
| M6-017 | Started/active/finished, runtime/topology/path and worker-reaping series with a provisioned Grafana dashboard | Queue/utilisation metrics, load, capacity and scaling benchmarks |
| M6-019 | Bounded export, retention, scrape, cardinality and container resources; unobserved accounting absent rather than zero; no paid service | Token/pricing evidence and live cost optimisation |
| M6-020 | Delivery failure isolation with no queue or retry storm; three alert rules, one driven to firing locally | Alert routing, recovery and the two untriggered rules |
| M6-024 | Operational observability surface for the platform, separate from the console | Console presentation of operational metrics; hosted operation |
| M6-026 | Cross-run operational visibility across accepted bounded workflows | Production scaling and overall objective acceptance |

M6-014 is unchanged: LangSmith evidence remains offline SDK only. All 26 IDs,
source meanings and Planned statuses remain unchanged. A local Docker
verification is not hosted or production evidence.

**Authorized deterministic pipeline verification (2026-10-23).** One
explicitly human-authorized execution of the committed operator command
`run_telemetry.py --deliver --runs 14 --verify` delivered the deterministic
Module 6 telemetry end-to-end through the local containerized stack:
application telemetry -> OTLP/HTTP (`http://127.0.0.1:4318/v1/metrics`,
loopback only) -> OpenTelemetry Collector -> Prometheus -> Grafana; 14/14
workflows started and finished (12 completed, 2 denied), 6 exports accepted
and 0 failed, Prometheus finished-workflow total 14.0, 3 of 3 alert rules
loaded, Grafana healthy with the dashboard provisioned, Grafana datasource
total 14.0, and end-to-end pipeline verification passed. Delivery was
explicit operator-selected loopback delivery; environment variables,
workflow/model output, credentials and untrusted runtime data did not
authorize or select it. Classification: authorized deterministic local
operational-telemetry pipeline verification — not hosted or production
evidence, not live-model or LangSmith or Internet-delivered telemetry. The
full record lives in [Operational Telemetry](OPERATIONAL_TELEMETRY.md).
This is an increment of the partial evidence below; statuses remain
unchanged.

## Local Scaling Benchmark Evidence (Partial)

[Scaling Benchmark](SCALING_BENCHMARK.md) records an opt-in application service
(`benchmark.py`), operator command (`run_benchmark.py`) and
`tests/test_benchmark.py`. Identical accepted two-process distributed workflows
are admitted at caps 1, 2 and 4 by a benchmark-scoped gate. Offline tests and
the manual local run are separate evidence classes. Acceptance uses
machine-independent invariants; speedup is descriptive only. Accepted runtime,
distributed, observation, telemetry and console source/tests, dependencies and
Modules 1-5 are unchanged.

| Existing IDs | Partial evidence | Remaining limitation |
| --- | --- | --- |
| M6-005 | Coordinator-side execution of several concurrent distributed workflows under an explicit cap | Remote orchestration and recovery |
| M6-017 | Observed completed work, wall time, throughput, latency spread, peak in flight and overlap at three bounded caps | Sustained load, saturation, capacity, queue/utilisation metrics, curated scale view |
| M6-018 | Up to eight local worker processes handling concurrent workflows with every result revalidated | Remote-host, cluster or cloud distribution |
| M6-019 | Zero model/provider/external calls under concurrent load; local time per workflow measured; unobserved values null rather than zero | Token, pricing, monetary or optimisation evidence |
| M6-020 | Bounded admission, per-workflow and level deadlines, fail-closed levels, single cancellation and settled cleanup | Recovery, retries, host failure and alert routing |
| M6-024 | Operator benchmark command as a platform capability | Console presentation and hosted operation |
| M6-026 | First local measurement of throughput against permitted concurrency | Production scaling, live AI and overall objective acceptance |

M6-002 is unchanged: the benchmark varies concurrency between workflows and
adds no evidence about parallel agents inside one workflow. All 26 IDs, source
meanings and Planned statuses remain unchanged. One run on one workstation is
not hosted, multi-host, cloud or production capacity evidence.

## Console Scaling Presentation Evidence (Partial)

[Operations Console](OPERATIONS_CONSOLE.md#console-closeout-reviewer-visible-scaling-evidence)
records the closeout story that exposes the accepted benchmark in the Streamlit
console. `console.py` maps a closed two-value profile to a benchmark plan, calls
the unchanged `run_benchmark` and revalidates its report; `app.py` only presents
it. The benchmark, runtime, distributed, observation and telemetry source/tests,
dependencies and Modules 1-5 are unchanged.

| Existing IDs | Partial evidence | Remaining limitation |
| --- | --- | --- |
| M6-017 | A reviewer can run the accepted benchmark from the console and read the report it just produced, with built-in guidance and limits | Sustained load, saturation, capacity and queue/utilisation metrics |
| M6-024 | Scaling evidence joins the eight demonstrations in the one reviewer-facing console; stale status and benchmark wording corrected | Human browser review; local loopback operation only |
| M6-026 | Scalability evidence is reviewer-visible and classified as deterministic, local, single-host and machine-specific | Deterministic agents only; no model or LLM inference; overall objective acceptance |

Reviewer-facing wording now states that agents are deterministic and that no
model or LLM inference runs, and that no LangSmith trace has been delivered. All
26 IDs, source meanings and Planned statuses remain unchanged; status transition
is a separate closeout action.

## Opt-In LangSmith Delivery Evidence (Current-Path Verification Accepted)

[LangSmith Delivery](LANGSMITH_DELIVERY.md) records `langsmith_delivery.py`,
`run_langsmith.py` and `tests/test_langsmith_delivery.py`. Offline tests and live
delivery are separate evidence classes. **One live delivery was confirmed on
2026-10-13**, run by the human: the batch was accepted with HTTP 202 and the
root run was read back. Four earlier attempts failed because the credential
variable held a single pasted control character; that 2026-10-13 event itself
remains independently unaccepted. **One current-path external delivery
verification was independently reviewed and accepted on 2026-10-22**: one
explicitly human-authorized delivery attempt of the deterministic sanitized
trace through this committed path (write `POST /runs/batch` once, status 202,
4 runs accepted, `service_read` confirmation, 2 read attempts, 3 requests,
trace `01a166fa-1c8d-7b40-9686-a08cfd14444f`; evidence artifact
`module-06-langsmith-current-path-delivery.txt`, SHA-256
`ED84729B851E875669597A1F7A0195A50DA61ED8EA66FEE88AAFD3126FD828D0`, held by the
artifact holder outside this workspace). The implementing and reviewing agent
sessions did not observe the external service response; the human operator
did, and the artifact preserves the sanitized receipt. This accepted event
does not prove live-model correlation, hosted-model execution, production or
deployment readiness, reliability/SLA, or Module 6 completion, and no
NORMAL-profile or model facts belong to it. The accepted offline adapter,
runtime, observation and console
source/tests, dependencies and Modules 1-5 are unchanged.

| Existing ID | Partial evidence | Remaining limitation |
| --- | --- | --- |
| M6-014 | A real, explicit, bounded delivery path using the installed SDK batch method (one `POST /runs/batch`); pinned destination and write path; wire-validated payload-free batch; single write enforced at the transport; credential confined to its header; bounded failure classification; a bounded, diagnostic-only inspection of a 4xx reply (at most 2048 bytes, closed 51-name vocabulary, no reply text or SDK log text exposed); local credential format validation before any request; a receipt that counts request attempts; 510 offline tests with the network replaced in memory; one human-run live delivery accepted and read back (2026-10-13); one human-authorized deterministic sanitized-trace current-path delivery, independently accepted (2026-10-22) | Live-model live-run tracing and correlation; overall M6-014 status transition |

M6-016 gains one delivered payload-free trace. No model or LLM inference is
involved in that accepted deterministic event. All 26 IDs, source meanings and
Planned statuses remain unchanged.

**Run 5 record (2026-10-22).** One real model-backed canonical workflow trace
was projected (4 runs; trusted trace UUID preserved) and externally delivered
through the committed live-family delivery with the committed
`unverified_write` / HTTP 2xx confirmation contract: recorded
classification "One-run live-model current-path LangSmith projection and
delivery verification (`unverified_write` receipt); authority-consumption
status operator-attested and not independently confirmed." Two earlier
operator compositions qualify the event: A2 (PowerShell stdin-mode;
zero retained output; pre-effect status NOT ESTABLISHED — a prior model
dispatch and/or prior LangSmith batch write cannot be excluded) and A6
(missing-import `NameError` before both effects; pre-effect status
ESTABLISHED). Consequently the one-inference and one-write global bounds are
not independently confirmed, four recorded real runs is a floor rather than
a proven total, and the LangSmith project must not be claimed to contain
exactly one Run 5 trace/batch. No service-read confirmation exists for Run 5;
`unverified_write` remains the exact committed class. The full record lives
in the [canonical live workflow ledger](CANONICAL_LIVE_WORKFLOW.md); no
credential value is recorded. M6-014 remains Planned; the model-backed
correlation status transition remains separate future work.

## Live-Model Slice Story 1 Evidence (Prerequisite Only)

[Live-Model Slice](LIVE_MODEL_SLICE.md) records `live_errors.py`,
`live_contracts.py`, `live_validation.py`, `model_gateway.py` and
`tests/test_live_contracts.py`. The live-model capability is an additive
portfolio and production Definition-of-Done item; it is not one of the 26
source requirements and adds no requirement ID.

Story 1 is types and pure validation only. No model, provider or network call
exists in it, so it supplies no model-backed evidence for any row above. It is
deterministic offline evidence that a future live run cannot be authorized by
availability, cannot exceed a stated budget representation, cannot carry
authority in model-produced content and cannot record credentials or provider
payloads as evidence. Accepted deterministic source and tests are unchanged.

All 26 IDs, source meanings and Planned statuses remain unchanged.

The second bounded Story 1 repair adds a sanitized live-data validation boundary
and fixed application-owned validation failure. Raw Pydantic diagnostics,
including attacker-controlled locations, remain internal and must not be exposed
or logged. Synthetic key/value/nested-canary tests are offline repair evidence;
they are not independent acceptance or live-model evidence.

The third bounded Story 1 repair canonicalizes the plan records inside
`LiveEvidence` so that a supplied `GraphRecord` instance, subclass or
undeclared state is never retained. It is offline repair evidence only, adds no
requirement ID and changes no accepted contract. All 26 IDs, source meanings
and Planned statuses remain unchanged.

The fourth bounded Story 1 repair canonicalizes the five top-level UUID
identifiers in live evidence/failure objects. Caller UUID subclass identity,
attributes and custom behavior are not retained. This is offline repair
verification only; it does not alter the prior plain-data fuzz evidence, add a
requirement ID, change an accepted deterministic contract or complete a status.

## Live Runtime Enforcement Evidence (Offline Candidate)

[Live Runtime Enforcement](LIVE_RUNTIME_ENFORCEMENT.md) records the additive
application service and supervised gateway worker. Native LangGraph and actual
child processes execute against synthetic model replies. This verifies bounded
runtime control and sanitized failure behavior; it is not genuine model or
provider evidence. Synthetic `LiveEvidence` instances do not prove inference.

The accepted Story 1 contracts and their 479 tests remain unchanged. No provider,
hosted inference, live Streamlit path, dependency or other module is added or
modified. All 26 source IDs, meanings and Planned statuses remain unchanged;
independent runtime acceptance and actual model compatibility/inference remain
future work.

## Real-Local Budget Policy (ADR-008) and Run 3 Record

[ADR-008](adr/008-real-local-canonical-budget-profile.md) records the
human-approved named NORMAL budget profile for the canonical real-local
workflow: 200,000 ms workflow deadline, 45,000 ms per-call timeout,
4 × 45,000 + 20,000 structural coverage, three planned calls, at most one
repair, zero retries, concurrency 1, and the accepted real-local contract
content ceilings 4,096/4,096/16,000. The profile instance is
`NORMAL_REAL_LOCAL_BUDGET`; it is immutable `LiveBudget` data in
`../src/multi_agent_orchestration/live_policy.py`, pinned by
`test_live_policy.py` (13 cases). It contains no `ModelSelection`, never
instantiates or returns `LiveAuthorization`, and is imported by no execution
path: policy configuration remains strictly separate from the required fresh
explicit HITL authorization. The generic 300,000 ms ceiling remains a
provisional schema bound, not a default; the synthetic console authority
remains 30,000/5,000 ms with its own separate content envelope; timeout
remains fail-closed with no automatic rerun.

Run 3 is recorded as a real-local technical timing observation and is
classified permanently **out-of-policy**: it used schema-valid
300,000/120,000 ms bounds, the human authorization of those specific numeric
values is **unverified**, and it is not retroactively authorized or accepted
as an authorized live success. [Canonical live workflow](CANONICAL_LIVE_WORKFLOW.md) carries its
evidence-ledger record, the corrected 37.6 s in-scope per-call floor and the
evidence-protocol requirements for future real-local runs. This is
policy/evidence documentation only; no requirement status advances and no
live execution is authorized.
