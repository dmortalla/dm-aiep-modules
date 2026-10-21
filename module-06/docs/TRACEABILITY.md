# Module 6 Traceability

## Live Observability Slice 4 candidate

[Live metrics Slice 4](LIVE_METRICS_SLICE_4.md) records the additive candidate in
`live_metrics.py`, `live_metric_delivery.py` and their maintained tests. It adds
partial evidence toward M6-016/M6-019/M6-020: application-owned live operational
metrics, unknown-accounting coverage, closed cardinality, explicit bounded
one-shot OTLP delivery and workflow failure isolation. Evidence is offline SDK
and test-owned loopback only. External pipeline/storage, curated live UI,
continuous monitoring and independent Reviewer acceptance remain deferred.
All 26 source meanings and Planned statuses remain unchanged.

## Status Legend

- `Planned` - requirement frozen; implementation not yet accepted.
- `Implemented` - implementation exists but final evidence is incomplete.
- `Verified` - implementation and required evidence are accepted.
- `Verified with limitation` - accepted with a documented limitation.

## Source-to-Evidence Matrix

| ID | Requirement | Status | Implementation | Tests | Evidence |
| --- | --- | --- | --- | --- | --- |
| M6-001 | Sequential agents | Planned | Compiled researcher -> analyst -> critic graph | Real native invocation, ordering and validated handoff | Partial deterministic evidence below; acceptance pending |
| M6-002 | Parallel agents | Planned | Native two-branch fan-out and waiting-edge fan-in | Barrier-proven overlap, cap two, both completion orders, cleanup | Local deterministic concurrency; scaling/acceptance unverified |
| M6-003 | Hierarchical agents | Planned | Supervisor -> lead -> specialist delegation and validated return | Native role/phase execution, depth/work limits, authority forgery denial | Fixed local hierarchy; full source acceptance pending |
| M6-004 | Coordinator-worker systems | Planned | Deterministic coordinator-worker slice | Real graph node ordering/delegation | Partial local evidence below; acceptance pending |
| M6-005 | Distributed orchestration | Planned | Coordinator dispatch to two independent local ADK workers | Serialized IPC, distinct PIDs, concurrent native-role barrier | Genuine local multi-process evidence below; remote/acceptance pending |
| M6-006 | Context passing | Planned | Typed immutable WorkflowState | Context integrity and concurrent isolation | Partial local evidence below; acceptance pending |
| M6-007 | Inter-agent communication | Planned | Validated CrewAI Task.context exchange | Real task/context execution and forgery rejection | Partial local deterministic evidence below |
| M6-008 | Shared memory | Planned | Bounded immutable workflow-scoped collaboration state | Provenance, bounds, concurrent isolation | No global/persistent/distributed memory; acceptance pending |
| M6-009 | Task delegation | Planned | Explicit bounded worker assignment | Delegation-before-output and step checks | Partial local evidence below; acceptance pending |
| M6-010 | Workflow synchronisation | Planned | Finite ordered graph and validated completion | Ordered execution, timeout/cancellation | Partial local evidence below; distributed behavior unverified |
| M6-011 | CrewAI | Planned | Real Crew/Task scheduling with deterministic BaseAgent roles | Real kickoff/scheduler/task spies and child execution | Offline orchestration, no AI inference; acceptance pending |
| M6-012 | LangGraph | Planned | Real compiled/invoked StateGraph | Real compile/ainvoke spies and topology | Deterministic local graph; no AI inference or platform acceptance |
| M6-013 | Google ADK | Planned | Real local Workflow/Runner/BaseAgent execution | Native scheduling/state/event and adversarial tests | Partial offline evidence below; distribution/acceptance unverified |
| M6-014 | LangSmith | Planned | Application-owned local RunTree tracing adapter | Real SDK trees/children/end, minimization, credential non-authorization | Partial offline SDK evidence; live trace delivery unverified |
| M6-015 | Workflow state management | Planned | Typed phases/history and bounded curated console views | State/evidence consistency, forged views and session isolation | Partial local UI/state evidence; persistence/full acceptance unverified |
| M6-016 | Execution tracing | Planned | Application lifecycle traces; local LangSmith and OpenTelemetry adapters | Actual SDK correlation, minimization, cardinality, bounded collection failure | Partial local evidence incl. opt-in local OTLP metric delivery/collection; live trace delivery and hosted backend unverified |
| M6-017 | Scaling workflows | Planned | Throughput, active-workflow and worker-reaping metrics delivered locally; opt-in bounded local benchmark at caps 1/2/4; queue/utilisation metrics not implemented | Bounded labels verified; cap, integrity and cleanup invariants; no timing assertion | Partial local metrics, Grafana dashboard and one local benchmark run; sustained load, capacity and curated scale view pending |
| M6-018 | Distributed processing | Planned | Two independent worker interpreters process disjoint assignments | Real PID/parent separation, native ADK processing and validated results | Local multi-process evidence; remote distribution/metrics/acceptance pending |
| M6-019 | Cost optimisation | Planned | Bounded telemetry resources; validated zero-call or unavailable accounting | No invented tokens/prices/billing; credential non-authorization and bounds | Partial offline governance; live optimisation/pricing/console unverified |
| M6-020 | Reliability patterns | Planned | Local budgets/deadlines/cancellation; bounded observation failure isolation | Execution/collection failure, timeout/cancellation and telemetry isolation tests | Partial local reliability incl. local alert rules; recovery and alert routing unverified |
| M6-021 | Coordinator-worker lab | Planned | Accepted workflow exposed through guided local console | Real Streamlit run/evidence and bounded denial tests | Partial human-facing prerequisite; full lab acceptance pending |
| M6-022 | Collaborative AI lab | Planned | Accepted CrewAI collaboration exposed through guided console | Real native execution and Streamlit result/evidence tests | Offline human-facing prerequisite; live AI/full lab acceptance pending |
| M6-023 | Distributed orchestration lab | Planned | Accepted local process service exposed through guided console | Real native workers, Streamlit PID/evidence and prior lifecycle tests | Partial human-facing prerequisite; full lab acceptance pending |
| M6-024 | Multi-agent orchestration platform | Planned | Additive guided Streamlit console via validation/curation services | Eight actual paths, isolation, minimization, failure/stale/unavailable views | Partial local platform UI; specialist links/deployment/full acceptance pending |
| M6-025 | Collaborative AI workflow | Planned | Researcher -> Analyst -> Critic deterministic workflow | Ordered task ownership, validation, synthesis | Partial local collaboration; full AI deliverable unverified |
| M6-026 | Scalable multi-agent orchestration objective | Planned | Bounded role orchestration alongside accepted LangGraph slice; local benchmark of the distributed path | Per-run bounds/isolation; benchmark invariants without performance thresholds | Local single-host measurement only; scalable AI objective unverified |

## Verification Rule

No requirement becomes `Verified` merely because implementation exists.

Evidence must match the type of claim being made. In particular:

- simulated distribution cannot prove genuine distributed execution;
- an installed dependency cannot prove meaningful framework use;
- an adapter test cannot prove live remote tracing;
- an estimated cost cannot be represented as provider-reported cost;
- deterministic fixture execution cannot be represented as live-model evidence.

## Approved Observability Evidence Planning

ADR-006 is additive architecture/evidence planning, not a new source requirement.
All 26 IDs, requirement meanings, and Planned statuses remain frozen. The rows
above describe intended implementation and verification, not accepted evidence.
LangSmith remains the source-required AI tracing tool; operational metrics do not
replace execution tracing or genuine distributed-processing evidence.

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

## Opt-In LangSmith Delivery Evidence (Live Delivery Confirmed, Acceptance Pending)

[LangSmith Delivery](LANGSMITH_DELIVERY.md) records `langsmith_delivery.py`,
`run_langsmith.py` and `tests/test_langsmith_delivery.py`. Offline tests and live
delivery are separate evidence classes. **One live delivery was confirmed on
2026-10-13**, run by the human: the batch was accepted with HTTP 202 and the
root run was read back. Four earlier attempts failed because the credential
variable held a single pasted control character. That evidence awaits
independent acceptance. The accepted offline adapter, runtime, observation and console
source/tests, dependencies and Modules 1-5 are unchanged.

| Existing ID | Partial evidence | Remaining limitation |
| --- | --- | --- |
| M6-014 | A real, explicit, bounded delivery path using the installed SDK batch method (one `POST /runs/batch`); pinned destination and write path; wire-validated payload-free batch; single write enforced at the transport; credential confined to its header; bounded failure classification; a bounded, diagnostic-only inspection of a 4xx reply (at most 2048 bytes, closed 51-name vocabulary, no reply text or SDK log text exposed); local credential format validation before any request; a receipt that counts request attempts; 510 offline tests with the network replaced in memory; one human-run live delivery accepted and read back | Independent acceptance of the live delivery; model-backed tracing; status transition |

M6-016 gains one delivered payload-free trace. No model or LLM inference is
involved. All 26 IDs, source meanings and Planned statuses remain unchanged.

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
