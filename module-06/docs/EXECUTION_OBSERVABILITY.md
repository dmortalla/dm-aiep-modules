# Application-Owned Execution Observation

## Scope and evidence classification

The explicit `execute_observed_workflow` application service wraps the accepted
fixture, LangGraph default/topology, CrewAI, Google ADK and distributed services.
It returns their existing validated result and preserves their exceptions and
cancellation. Existing entry points, defaults, runtime selection and trusted
execution-evidence contracts are unchanged. This is local/offline instrumentation
and actual installed SDK integration, not live trace delivery.

The frozen paths remain:

- AI/agent execution -> application tracing boundary -> LangSmith.
- Workflow operations -> OpenTelemetry -> OTLP-compatible collection boundary
  -> Prometheus -> Grafana.
- Later, validated evidence, curated metrics and AI trace references -> Streamlit.

No console, deployment, additional telemetry stack or direct domain dependency on
Prometheus/Grafana is introduced. Streamlit is not telemetry storage. LangSmith
and Grafana retain their specialist roles.

## Ownership and correlation

`observability_contracts.py` defines immutable, extra-field-forbidding contracts
for traces, validated role/worker completion provenance, accounting, closed metric
dimensions, bounded snapshots and the offline collection boundary.
`observability.py` owns observation identities, retention and counters.
`observed_execution.py` validates explicit runtime selection and owns lifecycle
observation. `observability_adapters.py` owns both private SDK implementations.

Each invocation gets a fresh application-generated trace UUID and root span ID.
Repeated workflow IDs do not reuse trace identity. Workflow/task IDs, runtime and
topology bind a trace to validated evidence. OpenTelemetry root and completion
spans use these exact trace/span identities. LangSmith root ID/trace ID equals the
application trace UUID; child metadata references the corresponding OTel span.
Worker records also retain validated assignment IDs and actual PIDs. These trace
identities are local references, not fabricated remote URLs.

Workflow start and terminal times are observed at the service boundary. Duration
uses a monotonic clock; wall-clock timestamps are ordered despite clock changes.
Completion, failure, timeout, cancellation and correlated policy/validation denial
are distinct outcomes. Unknown exception text, stack traces, causes and raw SDK
errors are never telemetry fields. Uncorrelatable invalid schemas are rejected
without emitting their untrusted content.

Agent/role child spans represent **validated completion provenance**. They have
zero duration at the workflow observation endpoint; they do not reconstruct
native role start/end times or claim per-agent latency. Distributed completion
records show the accepted two-worker native barrier and reaping before return.
Failure records do not invent successful worker cleanup counts or role outputs.
Existing process lifecycle tests remain the evidence for failed-run reaping.

## Meaningful local metrics

| Measure | Source and semantics |
| --- | --- |
| Started workflows | Observed service invocations with validated correlation |
| Active workflows | Currently retained observations; cap 16, drops disclosed |
| Finished throughput/counts | Terminal observations by runtime/topology/path/outcome |
| Success, failure, timeout, cancellation, denial | Closed terminal categories; no raw errors |
| Workflow latency | Measured service duration, fixed histogram boundaries |
| Model calls and retries | Validated successful deterministic evidence, currently zero |
| Reaped workers | Two only after successful distributed service return |
| Observation loss/adapter failures | Saturated local diagnostic counters |

Throughput is a count over an operator-chosen observation window, not a measured
speedup claim. Active counts and terminal totals describe observed executions;
capacity drops mean they are not universal workflow totals. SDK metric aggregates
cover the adapter lifetime. Retained trace records cover the last 32 observations.

There is no queue-depth metric: these services expose no application queue.
Worker utilization percentages and native task latency are unmeasured. Barrier
occupancy is completion evidence, not sampled utilization. Token counts, estimated
USD cost and provider-reported cost are **unavailable (`None`)**. No token meter,
pricing policy or invoice is implemented. Unavailable is never serialized as zero
or treated as free pricing. Provider-call evidence is zero for the distributed
slice; the other accepted evidence contracts do not expose that field, so their
observation is unavailable. Model/external calls and retries are zero on validated
success. Failed executions have unavailable accounting rather than assumed zeros.
The offline tests independently verify no provider/network/paid activity.

OTel instruments are workflow started/active/finished, duration, model calls,
retries and worker reaping. Outcome dimensions support timeout/denial/failure
aggregates. Local snapshots additionally expose observation loss and adapter
failure. Unknown token/cost/queue/utilization instruments are not emitted.

## Security and bounded resource use

Telemetry never accepts instruction text, prompts, fragments, result content,
credentials, provider endpoints, free-form tags, arbitrary attributes, exception
messages or exporter configuration. Content is excluded by schema and explicit
construction, rather than heuristic secret matching. Both SDK adapters inspect
closed fields and fresh nested data before SDK serialization, including Pydantic
construction/copy bypasses. Rejected values cannot reach serializer warning logs.
Evidence correlation is checked before completion observation; telemetry cannot
modify or grant execution authority.

Metric dimensions are only runtime, topology, distributed path and terminal
outcome: a theoretical maximum of 4 x 4 x 2 x 5 = 160 combinations per terminal
instrument, with fewer valid combinations. Workflow/task/trace IDs, PIDs,
assignment IDs, roles, content and errors are excluded from metric labels. SDK
exemplars are disabled so trace IDs do not silently enter metric samples.

Application bounds: 16 active observations, 32 retained immutable traces, at most
three role records/four spans per workflow, two adapters, and counters saturating
at one billion. Excess observations and evicted records increment loss counters;
they do not deny execution. Adapters retain at most 128 SDK spans and 32 LangSmith
trees with at most three children each. SDK span bounds are ten attributes, two
events, zero links and 64-character attribute values. Duration aggregation uses
six fixed boundaries (1/10/100/1000/10000/30000 ms); the contract caps recorded
duration at one hour. No unbounded per-workflow metric series are allocated.

There are no background threads, periodic readers, asynchronous export tasks,
remote queues, delivery retries or telemetry-generated execution retries.
Adapters are trusted synchronous local code. Arbitrary blocking/remote exporter
plugins are outside this boundary; a future delivery implementation must supply
its own bounded queue, deadlines, destinations and authorization controls.

## SDK integration and failure isolation

The verified installed SDK versions are LangSmith **0.14.3** and OpenTelemetry
API/SDK **1.42.1** in the accepted Python 3.12.14 environment. No dependencies or
lockfile entries were changed.

`LocalLangSmith` exercises installed `RunTree`, `create_child` and `end` with a
fixed local project, empty inputs/outputs and closed metadata. It never accesses
the lazy client, calls `post`/`patch`, resolves a remote URL or enables delivery.
API keys and tracing flags cannot authorize transport. No `traceable` decoration
or automatic raw-payload collection is introduced.

`LocalOpenTelemetry` uses private `TracerProvider`/`MeterProvider`, application
trace IDs, `SimpleSpanProcessor`, a bounded local `SpanExporter`,
`InMemoryMetricReader`, counters and a fixed histogram view. No global provider is
replaced. Resource attributes are explicitly constructed without environment
resource detectors. Internal processor metrics use a private no-op provider.
`OTEL_SDK_DISABLED` is respected; tests explicitly enable local SDK recording
under the existing network guard. It never constructs an OTLP network exporter,
uses environment exporter endpoints or configures remote delivery.

Collection failures are sanitized before the SDK processor can log raw exporter
exceptions. Adapter failures increment diagnostics; observation startup/finalizing
failure, including an adapter's own cancellation exception, cannot replace a
result, exception or caller cancellation. Runtime/schema/output
validation stays fail-closed. No observation failure causes execution fallback,
provider escalation or acceptance of forged evidence. Local providers have an
explicit `close()` lifecycle; no atexit handler is registered.

`CollectionBoundary` declares the future OTLP-compatible infrastructure handoff
and rejects delivery enablement/addresses in workflow data. This is a contract,
not proof of serialized OTLP wire delivery, a running Collector, Prometheus
storage, Grafana queries or alerting. Those future deployment boundaries require
separate implementation and verification.

## Local operation

Run from the synchronized repository environment. Explicit runtime selection is
required by the observation service, including a typed request's field selection.

```python
import asyncio
from multi_agent_orchestration.contracts import RuntimeId, TaskInput, WorkflowRequest
from multi_agent_orchestration.observability import Observability
from multi_agent_orchestration.observability_adapters import LocalLangSmith, LocalOpenTelemetry
from multi_agent_orchestration.observed_execution import execute_observed_workflow

otel = LocalOpenTelemetry()
observer = Observability(adapters=(otel, LocalLangSmith()))
try:
    request = WorkflowRequest(runtime=RuntimeId.FIXTURE, task=TaskInput(instruction="Local task"))
    result = asyncio.run(execute_observed_workflow(request, observer=observer))
    print(observer.records[0].model_dump_json())
    print(observer.metrics.model_dump_json())
finally:
    otel.close()
```

The result is the accepted service result; observation remains separate. For
distributed execution, explicitly select Google ADK, authorize four steps and
adequate deadline via existing limits, and pass `distributed=True`. Runtime
dependency injection remains trusted code only and is unavailable for that path.

## Partial acceptance and remaining work

Partial evidence affects M6-014 (actual offline LangSmith SDK boundary), M6-016
(application lifecycle/correlation and local OTel metrics), M6-019 (truthful usage
availability and bounded telemetry resources), M6-020 (failure isolation and
timeout/cancellation observation), and M6-026 (bounded operational prerequisite).
All 26 source meanings and Planned statuses remain frozen.

Requirements: partial evidence only. Product experience: documented application
API, console pending. Real functionality: accepted runtimes and actual local
LangSmith/OTel APIs. Reliability/security/cost: bounded local instrumentation,
strict minimization, fail-safe collection and no billable execution. Evidence:
offline SDK, integration and adversarial tests. Deployment: unverified.

Live LangSmith delivery, OTLP wire transport, collection/storage, Prometheus,
Grafana, native role timing, token metering/pricing, production throughput,
operational alerts, the Streamlit console, deployment and production readiness
remain unverified. This does not complete M6-014/M6-016 or replace specialist AI
tracing with operational metrics.

Later status: the paragraphs above record this slice as it was accepted. The
Streamlit console has since been delivered ([Operations Console](OPERATIONS_CONSOLE.md)),
and opt-in local OTLP metric delivery, collection, Prometheus storage, Grafana
provisioning and alert rules have since been implemented and locally verified
([Operational Telemetry](OPERATIONAL_TELEMETRY.md)). The offline adapters
described here are unchanged and remain the default.

## Validation record

- `ruff check .` passes; only safe fixes/formatting were used during development.
- Focused observation suite: **76 passed in 31.94 s**, with warnings treated as
  errors. Complete Module 6: **535 passed in 132.43 s**, no skips/warnings.
- Complete root pytest: **2650 passed, 6 skipped, 3 warnings in 220.10 s**.
  Skips are existing conditional Module 5 cases; warnings are existing Module 3
  Chroma deprecations. No new warnings remain.
- Authoritative root collection: **2656 tests in 8.58 s**, exactly 76 above the
  accepted distributed baseline; discovery configuration is unchanged.
- `compileall` over all six module source/test directories passes.
- Offline `uv lock --check`, `uv sync --locked --offline --check` and `uv pip check`
  pass: 239 locked packages, 216 installed packages, no sync changes needed.
- All six application packages and four new observation modules import using
  isolated Python from outside the repository, with correct ownership and zero
  network attempts. Existing parent/child offline guards pass throughout tests.
- The documented example executes actual local SDK recording under the existing
  non-loopback guard: correlated workflow/task IDs, two SDK spans, one completed
  observation, zero adapter failures and zero external attempts; providers close.
- Real observed process cancellation/timeout reap both children, remove temporary
  profiles and leave no pending tasks. Both SDK and generic adapter failures,
  including adapter cancellation, preserve original execution outcomes.
- Scope is exactly nine Module 6 files: four new source files, the new
  `tests/test_observability.py`, this document, and updates to `OBSERVABILITY.md`,
  `PROJECT_STATUS.md` and `TRACEABILITY.md`. Accepted runtime source/tests,
  Modules 1–5, dependencies, root configuration, governance, Architecture B+ and
  frozen requirement meanings/statuses are unchanged. Whitespace checks pass.
