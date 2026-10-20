# Live Observability Slice 3 candidate

## Decision and boundary

Slice 3 projects **finalized live observations into local OTel traces only**.
`live_otel.project_live_observation(observer, trace_id, adapter=otel)` selects a
retained Slice 1 terminal snapshot after workflow return. The exact built-in
`Observability` and `LocalOpenTelemetry` instances are required. There are no
workflow hooks, inference changes, or automatic delivery.

This extends the established private SDK provider, application ID generator,
SimpleSpanProcessor and bounded local exporter rather than introducing another
telemetry system. Architecture B+ and ADRs 001–007 remain intact. Local recording
is actual SDK integration, not external delivery or execution evidence.

The Collector configuration has **only a metrics pipeline**. ADR-006 explicitly
does not approve additional trace/log storage. Sending these spans to that
Collector would not establish an operational trace path. No transport, endpoint,
network exporter, queue, thread or new backend is added here.

Metrics are intentionally deferred to Slice 4. Existing `RunTrace.Accounting`
requires deterministic zero-call evidence; live accounting must not be coerced
into it. A separate explicit live aggregation entry point should reuse the
existing closed metric dimensions where semantically correct, with evidence
class/window separation and bounded OTLP delivery verified independently.
Started/active counts cannot be reconstructed from terminal records. Repair
attempts are not silently renamed transport retries; cleanup is not a worker
count. Unknown usage/cost cannot become zero. Existing deterministic metric
delivery and Collector/Prometheus/Grafana configurations are unchanged.

## Correlation, topology and time

The trusted application trace UUID maps exactly to the OTel 128-bit integer,
and each 16-character application span ID maps exactly to its 64-bit integer.
The root is `module6.workflow`; at most three direct children are `Researcher`,
`Analyst`, `Critic`, in validated sequence. No model-call spans are created.
Children represent validated completion provenance with equal start/end times
at their observed completion instants, not measured role latency.

Installed OTel 1.42.1 source inspection established that `Tracer.start_span`
calls the private provider's ID generator for each span, inherits a valid
explicit parent's trace ID, and accepts integer nanoseconds unchanged.
`Span.start`/`end` preserve supplied timestamps. Root context is explicitly empty;
children use the root's explicit context, including after root end. SDK regression
tests verify this behavior at 1 ns, a current timestamp and the OTLP uint64 upper
boundary, including equal child instants and extreme nonzero trace UUIDs.
There is no LangSmith child UUID ordering workaround, datetime conversion,
timestamp adjustment or invented parent. Values exceeding OTLP fixed64 timestamp
range are refused before SDK work; the underlying live contract is unchanged.

## Safe vocabulary and privacy

Root attributes are only `observation=live_terminal`, closed `evidence_source`,
`runtime`, `topology`, `outcome`, `cleanup`, measured `duration_ms`, optional
closed `category`, and known `model_calls`/`repair_attempts`. Maximum ten attributes
fits the existing span limits. Child attributes are only
`observation=validated_completion`, closed `role`, `sequence`, `model_calls`,
`repair_attempts`. Resource remains `service.name=module6-offline`.

No task, prompt, response, role output, exception text, reason string,
credentials, environment value, endpoint, filesystem path, user/model metadata,
provider/model label, workflow/task identifier or arbitrary tag is copied.
No events, links, stack traces or status descriptions are emitted. Success sets
OK; other terminal outcomes set ERROR and retain the closed outcome attribute.
No span attribute is authorization. SDK exception capture is explicitly disabled.
Snapshots and nested contracts are revalidated and JSON-normalized before SDK
construction, including construction/copy bypasses. Rejections expose fixed
categories without rejected diagnostics. Unknown counts are omitted. Token usage
and monetary cost are not projected; omission means unprojected/unavailable,
never zero. No new metric label or instrument is emitted, and exemplars remain
disabled in the existing provider.

## Bounds, results and failures

One adapter admits at most 32 live attempts over its lifetime, with a permanent
bounded replay set. Each attempt produces at most four spans; the existing deque
retains at most 128 spans shared with deterministic instrumentation. Mixed use
can evict older spans. A fresh adapter starts a new budget; replay protection is
per adapter, not durable or process-wide deduplication. Deliberate projection
into another adapter repeats the same identities.

Admission takes adapter and observer locks nonblockingly; contention returns
`busy` without queued work. Snapshot lookup inspects at most 32 records. The
observer lock is released before SDK work. SDK work is finite synchronous local
construction and bounded in-memory collection; there is no socket/DNS operation
to time out, no asynchronous cancellation claim and no late completion. Replacing
private providers/exporters with blocking plugins is unsupported. These bounds
are operation/resource bounds, not a hard real-time scheduling guarantee.

`LiveOTelResult` reports `recorded`, `refused` or `failed`, fixed failure categories,
the correlation UUID when validated, planned span count, and the classification
`local_sdk_collection`. Recorded means local SDK collection only. SDK-disabled
recording reports `sdk_disabled`. A closed adapter refuses. Existing `close()` is
now serialized and idempotent. SDK collection faults, including adapter
cancellation, are sanitized by the existing exporter and reported separately.
An opaque constant-space failure marker detects new collection faults even when
the existing diagnostic counter is saturated at one billion.
Failed attempts can leave partial spans, remain spent, and are never retried.
No metric, workflow evidence, policy, authorization, cleanup or model call is
changed. There are no credentials to inspect or billable operations to activate.

## Usage and evidence limits

After an explicitly authorized canonical workflow has already returned (or its
application failure has been handled), trusted operator code can use:

```python
from multi_agent_orchestration.live_otel import project_live_observation
from multi_agent_orchestration.observability_adapters import LocalOpenTelemetry

otel = LocalOpenTelemetry()
try:
    terminal = observer.live_terminal_records[-1]
    telemetry_result = project_live_observation(
        observer, terminal.trace_id, adapter=otel
    )
finally:
    otel.close()
```

`observer` is the existing application-owned observer; this example does not
execute inference or enable network delivery. `OTEL_SDK_DISABLED` is respected.
Maintained tests cover actual installed SDK semantics, closed fields, corrupted
snapshots, all terminal classes, bounds, replay, contention, deterministic
repetition, Slice 2 correlation and actual synthetic child-process execution
with collection failure and unchanged call/evidence/cleanup results.

Requirements: partial observability evidence only. Product experience: explicit
application API, no Streamlit live mode. Real functionality: existing SDK local
collection, not vendor/remote integration. Reliability: bounded synchronous local
work and explicit failure/replay results. Security: allowlisted revalidation and
no payload/authority transfer. Cost: no paid calls or transport. Evidence:
offline tests only. Deployment: unverified. No frozen requirement is COMPLETE;
no production readiness or independent acceptance is asserted.

Slice 4 remains responsible for live operational metric projection and its
bounded delivery/collection evidence, curated UI integration as separately
scoped, and final external acceptance. This slice proves neither remote OTel
delivery nor Collector/Prometheus/Grafana live integration, LangSmith service
readback, real inference, provider compatibility, deployment or alerting.

## Implementation validation record

New maintained tests in `tests/test_live_otel.py` (45 parameterized cases):

| Test (`test_` prefix omitted) | What it proves |
| --- | --- |
| `installed_sdk_exact_identity_topology_and_nanoseconds` | 24 SDK cases: exact trace/span IDs, root/child parentage, all role prefixes, tied child times, minimum/current/maximum timestamps, status, context isolation, no deterministic accounting or metric emission |
| `minimized_closed_attributes_and_cross_slice_correlation` | Exact safe root/child vocabulary, resource, no sensitive content/events/links/exception descriptions, unknown tokens preserved, same Slice 2 trace UUID |
| `terminal_failures_and_unknown_accounting` | Failure, timeout, cancellation and denial remain closed observations; unknown counts are absent rather than zero |
| `forged_retained_data_refuses_without_sdk_or_sensitive_logs` | Extra/nested fields, timestamp overflow and duplicate span forgery refuse before SDK recording and without sensitive logs |
| `only_retained_owned_finalized_observations_are_selected` | Active/unretained records, string trace IDs and unowned observer data cannot project |
| `replay_lifetime_capacity_retention_and_close` | One attempt per trace per adapter, 32-attempt ceiling, 128-span retention ceiling, closed refusal and idempotent close |
| `contention_refuses_without_waiting_or_creating_work` | Either contended observer or adapter lock refuses immediately without a projection attempt |
| `concurrent_replay_has_one_attempt_and_no_background_workers` | Forty concurrent requests yield one recording, no duplicate spans or projection-owned background threads |
| `collection_fault_is_sanitized_and_never_replayed` | Exporter exception/cancellation is isolated, sanitized and not retried; retained evidence is unchanged |
| `disabled_sdk_never_claims_collection` | Disabled SDK returns explicit failure and no spans |
| `saturated_diagnostic_counter_cannot_hide_collection_failure` | Counter saturation cannot turn a failed collection into success |
| `post_workflow_failure_preserves_evidence_and_model_calls` | Actual synthetic success/failure workflows retain evidence and cleanup, with exactly three calls before and after collection failure |
| `repeat_projection_across_private_adapters_is_deterministic` | Repeating an observation in a deliberately separate adapter reproduces the same IDs, topology, attributes and timestamps |

The final source revision passed these gates in order:

| Gate | Result |
| --- | --- |
| `.venv/Scripts/ruff.exe check .` | PASS, exit 0 |
| `pytest module-06/tests/test_live_otel.py -q -x` | 45 passed in 3.97 s |
| Slice 1 / Slice 2 / existing OTel compatibility | 373 passed in 88.40 s |
| `pytest module-06/tests -q -x` | 2558 passed in 441.40 s |
| Root `pytest -q -x` | 4673 passed, 6 skipped, 3 warnings in 656.63 s; exit 0 |
| compileall, all six module source/test directories | PASS, exit 0 |

Compatibility used `test_live_observation.py`, `test_live_langsmith.py`,
`test_observability.py` and `test_telemetry_delivery.py`. All pytest commands use
the repository `.venv/Scripts/python.exe`, fresh ignored `build/` basetemp paths
and unchanged maintained test/provider/network guards. Module 6 completed with
no reported warnings or skips. The historical CrewAI collaboration UI timeout
did not recur in that complete Module 6 run.
Root warnings are the three Module 3 Chroma `legacy embedding function config`
deprecations, outside this candidate. The six skips are existing conditional
Module 5 tests. No gate is reported as warning-free when it was not.

Initial safe Ruff fixes/formatting corrected two E501 test lines. Initial
sandboxed focused runs stalled after 41 passes. Diagnostic faulthandler output
located the stall in Windows asyncio event-loop fixture setup:
`socket.accept -> _fallback_socketpair -> _make_self_pipe`, before the synthetic
workflow test body. Those runs were interrupted, not counted as passes. The
unchanged 44-test suite then passed outside the sandbox in 3.43 s with the
maintained guards active. This is execution-environment evidence, not a
candidate failure or a relaxed test timeout.

Source review then found a saturated diagnostic-counter edge case. A new
constant-space marker and regression ensure new collection faults cannot be
mistaken for success when that counter reaches its ceiling. The in-progress
compatibility run against the superseded revision was stopped. Ruff and the
required focused/compatibility/Module 6 sequence were restarted against the
final revision, producing the results above. No test or security boundary was
weakened. No candidate pytest assertion failure was observed in these runs.

The first root gate reached captured progress at 21% without a failure
report, but the session was subsequently lost. On explicit human resumption,
the session ID was unavailable and read-only process inspection found no
matching root pytest process. Its completion, final totals and exit code are
unknown. That run is not counted as PASS or attributed to the historical UI
timeout. Only the unfinished root gate was resumed; completed prior gates
were preserved. The resumed root gate passed with the totals above. Output is
retained in ignored
`build/module06-slice3-root-resume-a.log`.

The final syntax command was `.venv/Scripts/python.exe -m compileall -q` followed
by `module-01/src module-01/tests` through `module-06/src module-06/tests`.
It completed after the passing root prerequisite. Final `git diff --check`
passed, and the index remained empty of staged changes. These are engineering
gate results, not fresh independent acceptance or external integration evidence.

Branch remains `feature/module-06-architecture` at
`5a570dff9ee0b48ddf083f1ed5b7c8436109c48e`. Changes are confined to this document,
`docs/OBSERVABILITY.md`, `src/multi_agent_orchestration/live_otel.py`,
`src/multi_agent_orchestration/observability_adapters.py` and
`tests/test_live_otel.py`, all within Module 6. No staging, commit or push occurs.
No real model/Ollama, LangSmith, external telemetry/network, hosted-provider or
credential activity is performed. Test-owned local IPC/collection is offline
evidence, never live external-service verification.

The candidate requires fresh independent acceptance review.
