# Live Observability Slice 4 candidate

## Boundary reconstructed from the accepted repository

Slice 4 adds a bounded live operational metric window and one explicitly selected
OTLP/HTTP write of its frozen cumulative snapshot. It consumes retained Slice 1
finalized observations **after** canonical workflow return/failure handling.
Slices 1–3, deterministic accounting, orchestration, authorization, cleanup,
LangSmith, UI, architecture and accepted ADRs are unchanged.

Repository evidence determines this division:

- `observability_contracts.Accounting` is intentionally deterministic/zero-call.
  `LiveRuntimeFacts` allows known positive dispatch/repair counts or unknown
  accounting. The new narrow `LiveMetricObservation` is a sibling, not a relaxed
  deterministic contract or evidence type.
- `LocalOpenTelemetry` establishes private SDK providers, explicit resources,
  in-memory readers, fixed histogram buckets and disabled exemplars. The live
  collection follows those conventions without mixing aggregate streams.
- Existing operational delivery is cumulative and periodic. Inspection of the
  installed OTel 1.42.1 HTTP exporter found an explicit connection-error retry in
  `_export`, a retry/backoff loop in `_export_with_retries`, environment-sensitive
  configuration and raw transport reasons in logs. Reusing that exporter unchanged
  cannot satisfy Slice 4's one-shot/no-retry/minimization requirements.
- The live path therefore reuses the SDK's `encode_metrics` OTLP protobuf encoder
  and the existing loopback destination validator, with one explicit Requests
  operation. It does not construct the retrying exporter, a periodic reader or
  a second telemetry backend. This small transport boundary is justified by
  those observed SDK semantics, not speculative abstraction.
- ADR-006 approves metrics through Collector -> Prometheus -> Grafana and excludes
  additional trace/log storage. The Collector has only a metrics pipeline.
  **Trace export remains excluded.**

Metrics and delivery form one bounded increment because delivery consumes only
this minimized SDK snapshot. They remain separate explicit APIs; recording never
performs network I/O and delivery never executes or retries a workflow.

## Truthful measures and provenance

`live_metrics.LiveOperationalMetrics.record(observer, trace_id)` selects only an
exact, retained finalized observation from the application-owned observer. It
revalidates the full terminal/nested contract, normalizes through JSON and then
minimizes it to trace UUID (local replay bookkeeping only), evidence source,
outcome, duration and optional paired dispatch/repair accounting.

Namespaces are fixed by accepted application provenance:

| Application evidence source | Metric prefix |
| --- | --- |
| `synthetic_offline` | `module6.live.synthetic` |
| `local_provider_execution` | `module6.live.local` |

The prefix describes observation provenance, not provider/model identity or a new
execution mode. Offline fixtures marked with either provenance for a contract
test do not establish actual inference. Separate names prevent the Collector's
existing label policy from merging synthetic and provider observations, or either
with deterministic operational aggregates.

For **each** prefix, the exact instrument suffixes are:

| Suffix | Unit | Meaning |
| --- | --- | --- |
| `.workflow.finished` | `1` | One finalized observation, including failure/denial/cancellation/timeout |
| `.workflow.duration` | `ms` | Observed monotonic workflow duration, not role/model latency |
| `.accounting.observed` | `1` | One terminal whose dispatch and repair counts are known |
| `.model.calls` | `1` | Application-supervised dispatch attempts, not provider completions/billing |
| `.workflow.repair_attempts` | `1` | Application malformed-output repair attempts, not transport retries |

The first two measures are always recorded. The last three are recorded only
when accounting is known. Known zero is a genuine SDK point with value zero;
unknown is absent, never converted to zero. For mixed known/unknown observations,
`accounting.observed / workflow.finished` exposes the known accounting fraction.
Call/repair totals cover only that observed subset. If coverage is absent, the
consumer must report unavailable rather than assume a complete zero total.

No metric invents started/active counts from terminal records, queue depth,
worker utilization/count, role duration, token usage or monetary cost. This slice
deliberately does not project token counts even when a particular observation
knows them. Unknown token/cost fields remain unchanged in application observation.
Role prefix length 0/1/2/3 changes neither metric labels nor dispatch semantics.

## Security, authority and cardinality

All points use exactly the established `MetricLabels` keys: `runtime`, `topology`,
`distributed`, `outcome`. For the current live workflow, values are respectively
`langgraph`, `sequential`, false and one of the five accepted outcomes. There are
at most five dimension groups per namespace: ten across both sources, fifty SDK
points across ten instruments. Six fixed histogram boundaries
1/10/100/1000/10000/30000 ms create seven buckets without recorded min/max.
At most 130 resulting Prometheus counter/bucket/count/sum series are introduced
by this live vocabulary (excluding scrape/backend-generated bookkeeping).

Resource attributes are exactly `service.name=module6-live`; scope is
`module6.live.observability`. Exemplars are off. No trace/run/span/workflow/task
identifier enters SDK metrics, resources or the OTLP wire payload. No provider,
model, role, category, task/prompt/response, raw output, exception/reason text,
credentials, endpoint, environment value, filesystem path or arbitrary metadata
becomes a label or payload. Configuration endpoints are operator-owned transport
data only; they are not metric fields or result fields. Raw input validation,
HTTP/protobuf errors and server diagnostic text never escape safe results/logs.

Telemetry grants no authority and changes no workflow evidence, policy, budget,
canonical outcome or cleanup. It cannot trigger inference, a repair, a model
retry or provider selection. Construction/import/recording/shutdown never enables
delivery. Ambient credentials cannot authorize anything; none are looked up.

The unchanged Collector namespace filter accepts `module6.*`; unchanged
Prometheus relabeling accepts the new names and retains precisely these labels.
No configuration or ADR amendment is needed. Existing Grafana panels/rules query
the deterministic names and therefore do **not** display/alert on these live
names automatically. Curated live panels/queries remain separate later work.

## Execution and resource bounds

A window admits at most 32 terminal attempts with a never-evicted local replay
set. At most 128 model dispatches and 32 repairs can be counted in that window.
Recording takes its own and the observer's lock nonblockingly; contention refuses
without queued work. Snapshot lookup is bounded by existing 32-record retention.
The observer lock is released before SDK work. No workflow hook or lifecycle
counter is added. SDK setup is lazy, private and registers no shutdown-on-exit
handler or periodic reader. Disabled/unavailable SDKs report safe results.

An instrument exception/cancellation can leave partial local aggregates. Its
attempt remains spent, the window is marked damaged, subsequent new records
refuse and **delivery is refused**. Partial local data is diagnostic, never a
silently complete export. There is no rollback or implicit collection retry.

`live_metric_delivery.deliver_live_metrics(metrics, config)` requires exact owned
types and a revalidated explicit `LiveMetricDeliveryConfig`. Mode has no default;
destination must be `http://127.0.0.1:<1024..65535>/v1/metrics`, as established by
`DeliveryConfig`. No DNS hostname, TLS credentials, redirect or arbitrary path is
accepted. Timeout is 100–5000 ms. No environment exporter config is read. Requests
uses `trust_env=False`, no authentication, zero adapter retries, redirects off
and a streamed response. A private Session override returns no redirect requests,
including Requests' otherwise eager preparation of `Response.next`. No real
destination was contacted during implementation
except test-owned loopback stand-ins.

An empty/disabled/closed/damaged/invalid collection refuses before network work.
Serialization uses SDK OTLP encoding and is capped at 65,536 bytes. A successful
snapshot seals the window irreversibly **before** transport admission. Recording
then refuses. Each window has exactly one possible delivery attempt, including
timeouts, protocol errors and global saturation. There is no public retry/flush
loop, periodic export, durable queue, automatic resend or shutdown export.

A process-wide nonblocking semaphore admits at most three I/O workers across
windows. The monotonic application deadline covers all transport waiting,
including resolver, HTTP, response consumption/disposal and Session cleanup.
Socket timeouts are additional safeguards, not the DNS/deadline proof. Python
cannot safely cancel arbitrary blocked I/O. A timed-out daemon worker retains its
bounded batch/config and global permit until actual exit; it is never replaced
while blocked. At saturation, further attempts fail immediately. Three permanent
stalls require actual completion or process restart to recover capacity. Permit
release precedes a short worker-exit epilogue; OS scheduling is not a hard
real-time guarantee.

Workers own only a frozen batch/config and a fixed-category completion cell,
never an observer, SDK provider, collection replay set or returned result. Late
completion cannot rewrite evidence/results or reopen the window. The originally
authorized write may occur or complete late; timeout is **not** remote cancellation
or proof of nonreceipt. `close()` shuts down only the private in-memory SDK and
does not wait for transport or perform a final export; contention returns false.
An already admitted write is not cancelled by close.

Redirect/non-2xx bodies are never read. For 2xx replies, one raw read requests at
most 1025 bytes: the 1024-byte body limit plus a single discarded overflow probe.
Decoded content, Requests `.content` and automatic decompression are not used;
`Accept-Encoding: identity` is explicit. The reply body is capped at 1024 bytes.
A 2xx reply must parse as an OTLP
`ExportMetricsServiceResponse`; empty protobuf is valid. Rejected points or a
nonempty partial-success diagnostic report `partial` without exposing its text.
Oversized/malformed replies report `invalid_response`. Other HTTP statuses report
`export_failed` with no retry. `accepted` means protocol acknowledgement only,
not proof of persistence, full pipeline queries, real inference or acceptance.
All delivery results remain classified `otlp_write_unverified`.

## Operator use and remaining work

After an already authorized workflow returns (or its failure has been handled):

```python
from multi_agent_orchestration.live_metrics import LiveOperationalMetrics
from multi_agent_orchestration.live_metric_delivery import (
    LiveMetricDeliveryConfig, deliver_live_metrics,
)

window = LiveOperationalMetrics()
try:
    terminal = observer.live_terminal_records[-1]
    collection = window.record(observer, terminal.trace_id)
    # Recording above is local. Only this separate explicit call selects I/O:
    delivery = deliver_live_metrics(window, LiveMetricDeliveryConfig(
        mode="loopback-otlp-http",
        endpoint="http://127.0.0.1:4318/v1/metrics",
    ))
finally:
    window.close()
```

This is a bounded cumulative operator window, **not continuous production
monitoring**. Use one window per isolated collection session; do not run competing
windows exporting identical cumulative series to the same receiver. A deliberate
new window resets the SDK cumulative epoch and replay budget. Backend cumulative
reset/retention behavior and exact totals across multiple sessions need separate
acceptance; use a clean test receiver/session for exact verification, as existing
`run_telemetry.py` already requires for its deterministic verification. No durable
deduplication, automatic window rollover, UI integration, external readback or
remote recovery is claimed. Creating a fresh object is an explicit operator
action, not a retry performed by this implementation.

Requirements remain partial observability/cost/reliability evidence; all frozen
requirements/statuses remain intact. Product experience is an explicit application
API, with curated Streamlit live integration deferred. Real functionality is the
actual local SDK and test-owned OTLP wire path. Reliability/security/cost are
bounded and adversarially tested offline. Evidence is deterministic/offline;
deployment and external Collector/Prometheus/Grafana/provider acceptance remain
unverified. No production-readiness or final Module 6 completion claim is made.

## Independent redirect-body rejection and bounded repair (2026-10-21)

The Reviewer rejected the transport bound: installed Requests 2.34.2 can consume
a redirect body inside `Session.post()` before application validation, despite
`stream=True`, `allow_redirects=False` and `max_redirects=0`. Local source inspection
confirmed that `Session.send` invokes `resolve_redirects(..., yield_requests=True)`
to prepare `Response.next`; the resolver accesses `resp.content` before checking
`max_redirects`. Requests buffers that property by joining the complete body.
The prior status-only redirect tests did not prove bounded consumption.

The repair preserves the existing Requests adapter and its no-retry, loopback-only
configuration. A private Session subclass overrides only `resolve_redirects` with
an empty iterator, so neither redirect following nor eager redirect preparation
can enter the body-consuming resolver. The installed `HTTPAdapter.send` uses
`redirect=False`, `preload_content=False` and `decode_content=False` in urllib3.
Application code now reads eligible responses directly with
`raw.read(1025, decode_content=False)`. Oversized data is rejected immediately;
no content/decompression pipeline can materialize an arbitrarily large body.
`Response.close` closes an unconsumed raw response without draining its body.
Caller deadlines, worker admission, sealing, failure sanitization and late-result
isolation are unchanged. No accepted runtime, test deadline or authority rule is
altered.

`test_actual_large_loopback_response_consumption_is_bounded` has two actual
Requests/urllib3/HTTP cases, each served by a test-owned loopback server with a
1 MiB response body. The adapter probe calls the real send/read methods unchanged
and counts their returned bytes. It also checks urllib3's actual encoded-byte
counter, Requests' unmaterialized `_content`/`_content_consumed` state, response
closure, one request and replay refusal. Before repair, the 302 case failed with
**1048576 bytes consumed versus expected 0**. After repair both cases passed in
1.34 s: 302 consumes zero body bytes and has no prepared next request; 200 consumes
only the 1025-byte overflow probe with decoding disabled. Test-server handling
allows the expected client disconnect; no client assertion is relaxed.

The initial redirected pre-repair invocation and a direct CLI invocation were
interrupted without a completed result. They are not passing evidence or assigned
a root cause. The completed diagnostic used pytest's public `main` API with a
startup faulthandler and reproduced the exact body-consumption assertion above.
Subsequent gates use that same native pytest API and write standard JUnit XML
under the requested `E:/ONEDRIVE-PERSONAL/TECHADEMY/EVIDENCE/` directory. The repaired
regression evidence is `module06-slice4-redirect-repaired-20261021-d.xml`.

### Reviewer timing observations and repair validation

The first repair-focused gate failed at
`test_actual_synthetic_execution_has_no_extra_calls_or_evidence_changes[happy]`:
1 failed, 26 passed in 37.73 s. Its assertion observed zero synthetic gateway
calls and no spawned process before the test constructed or invoked the Slice 4
collector. Both exact cases (`happy`, `second_bad`) then passed unchanged in
diagnostic isolation: 2 passed in 8.41 s. Accepted `live_execution.py` includes lazy
LangGraph import/graph construction in its startup budget before worker start.
That is a plausible startup mechanism, consistent with the Reviewer's reported
slow import, but this occurrence did not capture the import duration or enough
runtime detail to establish its precise cause. The failed full focused gate is
retained as red evidence, not relabeled harmless or erased by isolation.

The exact unchanged CrewAI compatibility node reproduced `ExecutionTimeoutError`
twice in isolation: 1 failed in 36.63 s and 1 failed in 30.76 s. Both stack traces
locate the timeout while accepted `adapters.py` awaits child `process.communicate`
inside accepted `execution.py`'s unchanged deadline. The second process explicitly
checked `sys.modules` after failure: neither
`multi_agent_orchestration.live_metrics` nor
`multi_agent_orchestration.live_metric_delivery` was loaded. This establishes
that this failure reproduces independently of Slice 4 execution, rather than
attributing it to the repaired transport. Why the accepted child did not complete
within its budget remains unresolved. No runtime, import policy, worker behavior,
test or deadline was changed to obtain a pass.

After those bounded diagnostics, the final unchanged source revision restarted
the fail-fast sequence. Ruff passed and the complete focused gate passed all
64 cases in 17.88 s, including both synthetic workflows and the two new actual
transport consumption cases. This is a subsequent complete passing focused run,
not a replacement of the prior failure history.

| Repair gate | Result |
| --- | --- |
| Ruff | PASS, exit 0 |
| Actual large-response regressions | 2 passed in 1.34 s |
| Final complete Slice 4 focused gate | 64 passed in 17.88 s |
| Slice 1–3 / deterministic / live-contract compatibility | FAIL: 1 failed, 260 passed in 93.47 s; exit 1 |
| Full Module 6 pytest | Not run: compatibility prerequisite failed |
| Root pytest | Not run: compatibility prerequisite failed |
| compileall | Not run: fail-fast sequence stopped at compatibility |
| Final read-only `git diff --check` | PASS; independent scope/whitespace check, not an override of the failed gate |

Native pytest XML evidence is under the requested EVIDENCE directory, with names
`module06-slice4-repair-focused-20261021-a.xml` (red),
`module06-slice4-repair-zero-calls-isolation-20261021-a.xml`,
`module06-slice4-repair-crewai-isolation-20261021-a.xml`,
`module06-slice4-repair-crewai-causality-20261021-b.xml` (both CrewAI red),
`module06-slice4-repair-focused-20261021-b.xml` (final focused pass) and
`module06-slice4-repair-compat-20261021-a.xml` (compatibility gate).
All are offline evidence under unchanged maintained guards. No independent
acceptance, deployment or external verification is claimed.

The final compatibility gate selected `test_live_observation.py`,
`test_live_langsmith.py`, `test_live_otel.py`, `test_observability.py`,
`test_telemetry_delivery.py` and `test_live_contracts.py`, with `-q -x --tb=short`.
It stopped at the same exact CrewAI node after 260 passes. This is the third
observed CrewAI timeout in this bounded investigation, not a passing gate or an
automatically excused historical failure. Diagnostics established independence
from executing/loading Slice 4, but did not establish a safe repair of the
accepted child-process slowdown. No further rerun was used to seek green status.
The source candidate remains repaired for redirect consumption, with broader
validation incomplete because of this outstanding runtime compatibility failure.

Repair edits are confined to `src/multi_agent_orchestration/live_metric_delivery.py`,
`tests/test_live_metric_delivery.py` and this document. The other five intentional
candidate files are preserved: `docs/OBSERVABILITY.md`, `docs/TRACEABILITY.md`,
`src/multi_agent_orchestration/live_metrics.py`, `tests/test_live_metrics.py` and
the existing additive security inventory in `tests/test_live_contracts.py`.
All are under Module 6. Branch remains `feature/module-06-architecture` and HEAD
remains `78a5524f87c31bf2bf0d952cbf134b58376a1158`; the index is empty of staged
changes. No reset/discard, branch change, commit, push, merge, tag or release was
performed. No real model/Ollama, LangSmith, external telemetry/network,
hosted-provider or credential discovery/use occurred. Test-owned loopback and
local SDK execution are offline evidence only.

The repaired candidate requires independent Reviewer acceptance.
