# Local Operational Telemetry Pipeline

## Purpose and boundaries

This story implements the ADR-006 operational path as an explicit, separately
selected mode:

application/workflow instrumentation -> OpenTelemetry -> OpenTelemetry Collector
-> Prometheus -> Grafana.

Nothing here runs by default. Imports, tests, the Streamlit console and every
accepted demonstration remain offline. The accepted `LocalOpenTelemetry` and
`LocalLangSmith` adapters, `Observability`, `execute_observed_workflow`, all
runtime source, the console and its tests are unchanged. No Python dependency or
lockfile change was needed: `opentelemetry-exporter-otlp` 1.42.1 was already
declared and locked.

Four evidence classes are kept distinct throughout this document:

| Class | What it is | Status |
| --- | --- | --- |
| Deterministic local SDK evidence | Offline pytest, including a real OTLP export to a loopback test receiver | Implemented and gated |
| Local Docker integration evidence | Application -> Collector -> Prometheus -> Grafana on one workstation | Verified locally, recorded below |
| Live LangSmith evidence | Remote AI trace delivery | Not implemented, not authorized |
| Hosted/production deployment evidence | Authentication, TLS, capacity, retention, alert routing | Not implemented, unverified |

AI/agent tracing remains LangSmith's role and is untouched. Prometheus stores
metrics only; no trace or log pipeline exists. Streamlit remains a curated
presentation layer and is not a Prometheus or Grafana client.

## Application delivery boundary

`telemetry_delivery.py` adds one observation adapter, `OtlpMetricDelivery`, and
its operator-owned `DeliveryConfig`.

Selection is explicit. Delivery exists only when trusted operator code builds a
`DeliveryConfig` with the required `mode="loopback-otlp-http"` (no default) and
passes it to `OtlpMetricDelivery`. No environment variable, credential, workflow
request field, runtime output or model output can enable delivery or choose its
destination. `WorkflowRequest` forbids unknown fields, so request data cannot
carry an endpoint.

The destination is validated, not trusted. The endpoint must be exactly
`http://127.0.0.1:<port>/v1/metrics` with a port from 1024 to 65535. Other
schemes, host names (including `localhost`), user information, queries,
fragments and paths are rejected, and rejected values are not echoed in errors.
A subclass, mapping, string or `model_construct` forgery is refused before any
exporter or thread is created.

The SDK exporter is isolated from the environment. The exporter receives an
explicit endpoint, timeout, no-compression setting, a fixed non-secret header
and a `requests.Session` with `trust_env=False`. Without these, the installed
SDK would read `OTEL_EXPORTER_OTLP_*` endpoint, header and certificate variables
and system proxy settings.

Delivery is bounded:

- a private `MeterProvider` with one periodic reader; no global provider;
- cumulative temporality and no queue: a failed export is dropped and the next
  interval resends current totals, so an unavailable collector cannot build a
  backlog or a retry storm;
- export interval 1 to 60 s (default 5 s); export timeout 100 ms to 5 s (default
  2 s) and always shorter than the interval; the SDK's internal retries share
  that one timeout budget;
- exemplars off; no spans; resource is `service.name=module6` only;
- at most 4 runtimes x 4 topologies x 2 paths x 5 outcomes label sets, from the
  existing `MetricLabels` contract, and six fixed histogram buckets.

Telemetry failure is isolated. Exporter faults are counted in a payload-free
`DeliveryStatus` and never reach workflow execution, change a result, trigger a
model or provider call, or authorize spending. If `OTEL_SDK_DISABLED` is set the
adapter refuses to start rather than appear to deliver.

### Signals

Only signals the application already owns are exported.

| OpenTelemetry instrument | Prometheus series | Source |
| --- | --- | --- |
| `module6.workflow.started` | `module6_workflow_started_total` | observer lifecycle |
| `module6.workflow.active` | `module6_workflow_active` | observer lifecycle |
| `module6.workflow.finished` | `module6_workflow_finished_total` | validated run outcome |
| `module6.workflow.duration` | `module6_workflow_duration_milliseconds_*` | validated run |
| `module6.model.calls` | `module6_model_calls_total` | completed-run accounting |
| `module6.workflow.retries` | `module6_workflow_retries_total` | completed-run accounting |
| `module6.worker.reaped` | `module6_worker_reaped_total` | distributed completion |
| `module6.observation.drops` | `module6_observation_drops_total` | observer loss counter |
| `module6.observation.adapter_failures` | `module6_observation_adapter_failures_total` | observer loss counter |

Accounting that a run did not observe is not exported, so it is absent rather
than zero. Queue depth, worker utilisation, token usage and cost are not
measured and are not exported, stored or charted. The two observation-loss
series appear only after a loss has occurred.

## Local stack

`module-06/telemetry/compose.yaml` defines three services and one volume.

| Service | Image | Host binding | Limits |
| --- | --- | --- | --- |
| `otel-collector` | `otel/opentelemetry-collector:0.162.0` | `127.0.0.1:4318` (OTLP/HTTP) | 192 MB, 0.5 CPU, read-only |
| `prometheus` | `prom/prometheus:v3.15.0` | `127.0.0.1:9090` | 384 MB, 0.5 CPU, read-only, 7 d / 256 MB retention |
| `grafana` | `grafana/grafana:12.4.12` | `127.0.0.1:3000` | 384 MB, 0.5 CPU, no persistent state |

Image digests observed at verification:

- collector `sha256:310a800ad69ee430e7c541796852a242c9c7db97aaad4daa5ccf843c525fbdb2`
- Prometheus `sha256:efd719c99d83b060d9daefdcf00360461adf279f45ef5391f8d111892118753e`
- Grafana `sha256:83be3e511ede559bee80e2215bb1987cb1246075461cb961beb515b0341e7aea`

Tags are pinned; digests are recorded here rather than enforced in the Compose
file. All services drop Linux capabilities, set `no-new-privileges`, cap log
size and do not restart automatically. Host ports can be moved with
`MODULE6_OTLP_PORT`, `MODULE6_PROMETHEUS_PORT` and `MODULE6_GRAFANA_PORT`.

Grafana 13.2.3 was tried first and rejected: it installs its Prometheus data
source through a start-up background installer, which adds a network dependency
and unrelated plugins. Grafana 12.4.12 ships the data source in the image and
runs with plugin preinstall, update checks, usage reporting and the news feed
disabled.

**Collector** (`otel-collector.yaml`): OTLP/HTTP receiver with a 1 MB request
limit; `memory_limiter` (128 MiB), a filter that drops every metric outside the
`module6.` namespace, and `batch` (5 s, 512 points); Prometheus exposition on
container port 8889, which is not published to the host; series expire two
minutes after the last update. Metrics pipeline only. The file is mounted
read-only and is operator-owned.

**Prometheus** (`prometheus.yaml`): one scrape job at 10 s with `sample_limit`
1000 and label count/length limits; relabelling keeps only `module6_*` series
and only the label names `job`, `instance`, `le`, `runtime`, `topology`,
`distributed` and `outcome`. No remote write and no Alertmanager.

**Alert rules** (`rules/module6.rules.yaml`), evaluated by Prometheus:

- `Module6CollectionBoundaryDown`: the collector cannot be scraped for 1 m;
- `Module6WorkflowFailureRatioHigh`: more than 20% of at least five finished
  workflows failed or timed out over 5 m, held for 2 m;
- `Module6ObservationLoss`: any observation drop or adapter failure in 5 m.

No notification channel is configured. Rule state is visible in Prometheus and
as the "Firing alerts" panel in Grafana.

**Grafana**: a provisioned, non-editable Prometheus data source and the
`module6-operations` dashboard (ten panels: started, finished, active, firing
alerts, outcomes per minute, bucketed p50/p95 duration, runtime/topology/path
breakdown, denials/timeouts/retries/worker reaping, observation health and
reported model calls). Refresh is 30 s with a 10 s floor.

### Access boundary

Every published port binds to loopback. Grafana allows anonymous read-only
viewing with the login form, basic authentication and sign-up disabled, so no
password is stored in source and the built-in administrator account cannot be
used. Prometheus and the collector have no authentication. This is a local
review boundary. It is not equivalent to hosted authentication, authorization
or TLS, and these ports must not be published beyond loopback.

## Running it

From the repository root, with Docker running:

```powershell
docker compose -f module-06/telemetry/compose.yaml up -d
uv run --locked --offline python module-06/run_telemetry.py --deliver --runs 14 --verify
docker compose -f module-06/telemetry/compose.yaml down --volumes
```

`run_telemetry.py` does nothing without `--deliver`. With it, the command runs
7 to 32 bounded deterministic demonstrations (fixture, four LangGraph
topologies, one intentionally denied one-step parallel run, and the local
two-process distributed path) through a single delivering observer.
`--verify` then reads curated values back from Prometheus and Grafana and
requires the stored finished-workflow total to equal the number just run. To
keep that check exact it refuses to start if earlier `module6_*` series are
still present; restart the collector first.

Remote responses are untrusted. `prometheus_scalar` and `grafana_scalar` accept
only one successful, label-free, finite, non-negative sample and report an
absent series as unavailable. `grafana_reference` permits only
`http://127.0.0.1:<port>/d/module6-operations`.

The three stat panels show cumulative totals for the delivering process and
reset when it restarts. Rate and percentile panels need a process that runs
across several scrapes, so a short one-shot run shows little in them.

## Streamlit

The console is unchanged. It does not deliver metrics, does not query Prometheus
or Grafana and shows no dashboard link, and its text still states that Grafana
has no deployed dashboard or link. Console runs therefore do not appear on the
dashboard. Presenting curated operational availability in the console remains
future work.

## Evidence

### Deterministic offline tests

`tests/test_telemetry_delivery.py` (87 tests) runs under the existing guard that
fails on any non-loopback DNS lookup or connection. A loopback HTTP server
stands in for the collector, so the real OTLP exporter and protobuf encoding
are exercised without Docker. The tests cover:

- 22 invalid configurations, the required mode with no default, and four forged
  configuration objects, with no secret echoed and no thread started;
- refusal when the SDK is disabled;
- workflow data cannot carry a destination;
- importing the application loads no OTLP exporter (checked in a subprocess);
- a real export decoded from protobuf: exact metric names, label keys within
  the four allowed, no exemplars, fixed histogram buckets, at most 16 points,
  and no instruction text, workflow, task, trace or span identifier in the
  payload in text, hex or raw byte form;
- unobserved accounting for a denied run is absent, not zero;
- eight exporter, credential and proxy environment variables neither start
  delivery nor redirect or decorate it;
- connection refused, HTTP 500 and HTTP 400: identical workflow results, bounded
  time, failures counted, no adapter failure charged to execution;
- observation-loss counters, idempotent close and export-thread shutdown;
- strict Grafana reference and untrusted Prometheus/Grafana reply curation;
- the operator command does nothing without `--deliver`;
- configuration contracts: three pinned images, loopback-only published ports,
  resource limits, retention, the namespace filter, the label allowlist, and a
  dashboard and rules that reference only implemented series and labels.

### Local Docker integration (2026-10-12, Docker 29.8.2 on Windows/WSL2)

- `otelcol validate` accepted the collector configuration; `promtool check
  config` accepted the Prometheus configuration and found 3 rules.
- From a freshly created stack, `run_telemetry.py --deliver --runs 14 --verify`
  reported 14 started and finished (12 completed, 2 denied), 3 exports accepted
  and 0 failed, a Prometheus finished-workflow total of exactly 14, 3 of 3 alert
  rules loaded, Grafana healthy with the dashboard provisioned, the same total
  of 14 through Grafana's data source query API, and verification passed.
- Prometheus stored exactly the nine `module6_*` series names expected for the
  signals that occurred and only the label names `distributed`, `instance`,
  `job`, `le`, `outcome`, `runtime` and `topology`. `module6_worker_reaped_total`
  was 4 after two distributed runs.
- Every dashboard query returned successfully through Grafana, and the
  dashboard rendered in a browser.
- Published ports were `127.0.0.1:4318`, `127.0.0.1:9090` and `127.0.0.1:3000`
  only; collector port 8889 was not reachable from the host.
- Collector, Prometheus and Grafana logged no errors during the final run.
- With the OTLP port pointed at a closed port, three workflows completed
  normally, one export failed and none was accepted, and the command reported
  the boundary as unavailable.
- With the collector stopped, `Module6CollectionBoundaryDown` moved from
  inactive to pending after about 30 s and to firing after about 90 s. Two
  workflows run during the outage completed normally with the export counted
  as failed. The collector was then restarted.

Image pulls from Docker Hub were infrastructure set-up traffic. No model,
provider, paid or remote telemetry call was made; all delivered runs report
zero model calls.

### Authorized deterministic pipeline verification (2026-10-23)

Classification: **authorized deterministic local operational-telemetry
pipeline verification.** One explicitly human-authorized execution of the
committed operator path
`uv run --locked --offline python module-06/run_telemetry.py --deliver --runs 14 --verify`
delivered the deterministic Module 6 telemetry through OTLP/HTTP to the local
containerized stack only. Authorization boundary: loopback OTLP/HTTP to
`http://127.0.0.1:4318/v1/metrics` only; Collector -> Prometheus -> Grafana
only; no LLM/model inference, no Ollama operation, no LangSmith operation; no
Internet/external telemetry; no credentials; no repository mutation; no
configuration, container or image changes; read-only Prometheus and Grafana
verification; no automatic second telemetry run. The authorization was
consumed by this single invocation.

Observed result: workflows started 14, finished 14 (completed 12, denied 2);
exports accepted 6, failed 0; final export accepted: true; Prometheus
finished-workflow total 14.0; alert rules loaded 3 of 3; Grafana healthy with
the dashboard provisioned; Grafana datasource query total 14.0; end-to-end
pipeline verification: **passed** (dashboard
`http://127.0.0.1:3000/d/module6-operations`).

Post-delivery: the stack remained running on its loopback ports (Collector
4318; Prometheus 9090, healthy; Grafana 3000); the repository HEAD remained
unchanged and clean; no model inference was requested; no Ollama or LangSmith
operation was requested; no second telemetry invocation was performed.

Established, for this verification: the Collector accepted the application
telemetry path; Prometheus stored and query-exposed the resulting
finished-workflow metric; all three configured Prometheus alert rules were
loaded; Grafana was healthy; the Module 6 Grafana dashboard was provisioned;
Grafana's configured Prometheus datasource returned the expected total of 14.
Delivery was explicit operator-selected loopback delivery; environment
variables, workflow or model output, credentials and untrusted runtime data
did not authorize or select delivery. No reusable authority is created from
the consumed allocation.

Claim boundaries, preserved: this record is exactly one bounded local
deterministic verification. It is not production deployment, hosted or cloud
observability, an Internet-accessible Grafana/Prometheus, production
reliability, SLA/SLO attainment, percentile or statistical reliability
evidence, live-model execution, LangSmith delivery, or externally delivered
telemetry; it proves no general portability, Module 6 completion, or release
acceptance. Export-count differences from the 2026-10-12 first integration
run reflect each recorded run's own delivery accounting; no prior
observation is rewritten by this record.

Portfolio significance: Module 6 includes a containerized
operational-observability stack — application telemetry over OTLP/HTTP into
OpenTelemetry Collector, Prometheus storage and rules, Grafana dashboards —
and this local pipeline is now operationally verified end-to-end. This
capability is intended to be surfaced prominently in later module/root
GitHub presentation, reviewer-facing Streamlit experience and
recruiter-facing closeout material; no premature deployment claim is made
by this record.

### Gates

- `ruff check .` passes. Ruff formatting was applied only to the three new
  Python files; no unsafe fixes were used.
- Complete Module 6 pytest: **695 passed in 178.19 s**, no skips (608 accepted
  plus 87 new).
- `compileall` over all six module directories passes.
- Root collection: **2816 tests**, 87 above the accepted console baseline of 2729.
- Complete root pytest: **2810 passed, 6 skipped, 3 warnings in 237.45 s**. Skips
  are existing conditional Module 5 cases; warnings are existing Module 3 Chroma
  deprecations.
- During development one accepted console test (CrewAI through the UI) failed
  once in a full Module 6 run executed while Docker Desktop was crash-looping
  and other commands were running. It passed alone and in every later full run,
  including the final gates above. It is recorded as a load-related transient,
  not diagnosed further; no test was changed.

## Requirements and Definition of Done

New partial evidence applies to M6-016 (operational workflow metrics delivered
over OTLP; this is not trace delivery), M6-017 (throughput, active-workflow and
worker-reaping series; no load or scaling benchmark), M6-019 (bounded telemetry
cost; absent rather than zero accounting), M6-020 (failure isolation and
operational alert rules), M6-024 (the operational observability surface of the
platform) and M6-026. M6-014 is unchanged: LangSmith evidence remains offline
SDK only. All 26 source meanings and Planned statuses remain frozen; nothing is
marked complete or verified.

Requirements: partial evidence only. Product experience: an operator command
and a provisioned dashboard; no console integration. Real functionality: actual
OTLP export, collection, storage, query and provisioning on one workstation.
Reliability: bounded export, no queue, failure isolation. Security: explicit
selection, loopback-only validation and binding, allowlisted labels in the
application and again in Prometheus. Cost: no paid service, bounded resources
and retention. Evidence: offline tests plus the local integration run above.
Deployment: unverified.

## Unverified limitations

- Hosted or multi-host deployment, authentication, authorization and TLS.
- Alert notification routing; rules only change state.
- Behaviour under sustained load, real retention pressure or the configured
  memory limits; no capacity, throughput or scaling benchmark.
- Collector `memory_limiter`, the 1 MB receiver limit, Prometheus `sample_limit`
  and the label allowlist are configured and contract-tested but were not
  driven to their limits against live services.
- `Module6WorkflowFailureRatioHigh` and `Module6ObservationLoss` were loaded and
  evaluated healthy but not driven to firing.
- Image digests are recorded, not enforced.
- Short-lived delivering processes under-report in rate panels.
- Console runs are not delivered; the console shows no operational metrics.
- Live LangSmith delivery, live AI inference, token usage and cost.
- The Docker integration run is manual and is not part of pytest or CI.
