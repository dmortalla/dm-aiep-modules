# Additive Streamlit Operations Console

## Purpose and boundaries

The console is a runnable human-facing presentation layer for accepted
deterministic Module 6 capabilities. `app.py` contains native Streamlit controls
and rendering only. The new `console.py` application service validates commands,
selects explicit accepted runtime/topology/path choices, delegates to
`execute_observed_workflow`, validates/curates results and isolates observation
failures. It does not implement graph transitions, collaboration, delegation,
worker IPC, authority policy, retries or synthesis in Streamlit.

Architecture B+ and all source meanings remain frozen. No accepted runtime or
observability source/tests, historical CrewAI milestone, Modules 1–5, root
configuration or dependency/lockfile is modified.

The frozen observability paths remain AI/agent tracing -> LangSmith and workflow
operations -> OpenTelemetry -> OTLP-compatible collection -> Prometheus ->
Grafana. The console aggregates curated views; it is not telemetry storage.
LangSmith and Grafana retain specialist ownership. Neither remote trace URLs nor
dashboard links are invented. The page labels both as unavailable and explains
their future drill-down roles.

## Runnable reviewer experience

From repository root:

```powershell
uv run --locked --offline python module-06/run_console.py
```

Open the loopback URL the launcher prints, normally `http://127.0.0.1:8501`
(Streamlit uses the next free port when 8501 is taken). The launcher fixes
loopback binding, headless startup, disabled Streamlit usage analytics, hidden
detailed browser exceptions and a 1 MB WebSocket message limit. Root
configuration is unchanged. A direct `streamlit run` invocation must explicitly
use the equivalent safety flags; the provided launcher is the supported path.
Credentials never authorize execution and no credential entry/display exists.

The page starts idle with no selected demonstration. Selecting or refreshing
does not execute. Inputs are batched in a form; only submit calls the service.
The default synthetic example uses eight steps and a 30-second deadline.
Built-in guidance explains the operation, expected result, interpretation and
proof, and provides budget-denial/timeout exercises.

| Explicit demonstration | What the result/evidence demonstrates |
| --- | --- |
| Fixture | Fixed one-step offline request/result boundary |
| LangGraph coordinator-worker | Native delegation, text-length processing and return validation |
| LangGraph sequential | Ordered researcher/analyst/critic context passing |
| LangGraph parallel | Native two-branch join and capped parallel workflow |
| LangGraph hierarchical | Fixed supervisor/lead/specialist ownership and return |
| CrewAI collaboration | Real native task/context collaboration across three roles |
| Google ADK orchestration | Native delegation/validation within one execution process |
| Local distributed orchestration | Two independent ADK worker PIDs, disjoint work, barrier and reaping |

These are deterministic native-runtime demonstrations, not live AI reasoning.
The UI does not replay or fabricate successful SDK evidence. AppTest integration
tests run all eight real paths under the existing parent/child offline guards.
Parallel/hierarchical execution and actual worker lifecycle retain their existing
application semantics and prior detailed verification.

The latest submitted outcome becomes the selected result, so a previous success
cannot masquerade as a new failure's result. A submission that is rejected, busy
or faulted records no run; on that rerun the page hides the earlier result detail
and says the submission produced no result. Reviewers may inspect earlier views
using the recent-result selector. Failure text is fixed and actionable; it never
displays exception messages, chains, raw SDK output or credentials. A failed run
has no successful output/evidence. No automatic retry or runtime fallback occurs.

## Curation and security

Closed immutable `ConsoleRequest` and `ConsoleRun` contracts keep presentation
input/view models separate. Server-side validation independently checks the
demonstration allowlist, nonblank synthetic text <=4096 characters, strict integer
step bounds 1–32 and deadline bounds 1–30000 ms. Browser widget bounds are not
authority, and the text, step and deadline widgets deliberately declare none:
Streamlit 1.64 truncates text to a widget `max_chars` and resets numbers outside
a widget `min_value`/`max_value` to the default on the server, which would turn a
forged invalid submission into a valid executed request before the service saw
it. Limits are shown as guidance text; the submitted values reach `ConsoleRequest`
unmodified and out-of-range values are rejected, not adjusted. An unknown
demonstration value is passed through by Streamlit and rejected by the service.
Integer widgets still cast a submitted number to `int` before the service's
strict integer check. The service raises distinct sanitized errors for a rejected
request, a busy session and an internal fault, so none is reported as another.
No provider, key, exporter, endpoint, arbitrary runtime, privilege or
telemetry-enable field is accepted. Application-created workflow/task IDs and
closed mode mapping are retained outside untrusted output.

Results are fresh-revalidated recursively, including constructed/copied nested
models and unexpected fields, without serializer warnings containing rejected
values. Evidence must match workflow/task/runtime/topology/path and execution
limits. Display text admits only the existing bounded deterministic result
formats; this is a presentation minimization rule, not duplicated orchestration
or counting logic. Actual output uses plain `st.text`; no untrusted Markdown,
HTML, JavaScript, external assets or arbitrary links are rendered.

Evidence is already payload-free. Instructions/fragments, requests, credentials,
exception causes, SDK objects and raw telemetry buffers are not retained in the
recent result views. The task widget necessarily holds the current synthetic
input in transient Streamlit state; the form requests frontend clearing on
submit. It is not a credential-storage or sensitive-data interface.

Each browser session owns an application facade with one active execution and at
most eight curated result views. There is no global mutable result state or
shared resource/data cache. Clear removes the temporary views; closing the
session/server loses them. This bounded UI convenience is not a telemetry
database, durable workflow state or cross-session metrics store. It does not
establish platform-wide admission control, authentication or hosting capacity.

Malformed session objects are replaced; malformed stored views are discarded.
Snapshots have age labels and become stale after 60 seconds. A manual rerun
updates the label without executing or querying a backend. Recent counts cover
only the retained eight-result window, not all historical executions or a
production throughput measurement.

## Curated observability, reliability and cost

Each execution creates private local LangSmith/OTel adapters around the accepted
observation service. OTel providers close before returning, even when local
metric collection fails. Startup, tracing, collection and close failures degrade
observation availability without granting authority or changing successful
execution evidence. Uncorrelated/forged observations are omitted; a telemetry
failure cannot change the valid workflow result into a failure.

The OTel SDK disable flag is respected; disabled local SDK recording is labeled
degraded. The UI does not override environment flags or configure remote
exporters. Ambient API keys/tracing flags cannot enable inference or remote
delivery. Streamlit usage analytics are separately disabled by the launcher.

The view shows validated outcome/identity/evidence, workflow latency, observed
model/external calls, local trace/span identities and role completion provenance.
Distributed views include actual worker PIDs and reaping evidence. Per-role timing
is not reconstructed. Failed runs have unavailable call accounting rather than
invented zero counts. Tokens, monetary estimates and provider billing remain
unavailable. Zero billable inference does not mean local CPU/process resources
are free. No queue-depth/utilization percentages, fake telemetry charts, global
health verdicts, remote links or premium/provider escalation are introduced.

Execution continues to use accepted deadlines/budgets and deterministic offline
paths. UI submission is synchronous; there is no background job, refresh loop,
export queue, execution cache or new retry mechanism. In-flight browser stop or
disconnect is not a new cancellation API; existing execution deadlines/lifecycle
remain authoritative. Public hosting and aggregate session/process limits require
separate engineering and verification.

## Requirements and Definition of Done

Partial new UI/curation evidence affects M6-015/016/019/020/021/022/023/024/025/026.
Existing architecture/runtime requirements gain UI integration evidence through
all eight accepted demonstrations, without changing their source meaning or
claiming additional live/scaling functionality. All 26 requirements remain
Planned; zero labs/deliverables are marked complete or independently verified by
this implementation alone.

Requirements: partial exposure/curation evidence. Product experience: runnable
guided console with headless interaction tests; independent human/browser review
pending. Real functionality: accepted SDK/runtime/process paths. Reliability:
bounded inputs, views, admission and failure/observation isolation. Security:
closed commands, minimization, no raw markup/credentials or model authority.
Cost: offline zero-call operation and no telemetry delivery. Evidence: test and
gate results below. Deployment: unverified, loopback local review only.

Live AI, live LangSmith delivery, OTLP transport/collection, Prometheus/Grafana
deployment, specialist drill-down links, persistent state, production scaling,
multi-user authentication/hosting, measured throughput, full labs/platform and
production readiness remain unverified.

## Implementation provenance

Codex authored the original console: `app.py`, `console.py`, `run_console.py`,
both console test files, this document, the README and the status/traceability
updates. Its work stopped with one failing adversarial test
(`test_bypassed_browser_text_bound_is_revalidated_on_submit`).

Claude then reviewed the changeset read-only and, on human authorization,
performed a bounded repair and completion:

- removed widget-level `max_chars`, `min_value` and `max_value` in `app.py` so
  the application service is the only validation authority;
- added `ConsoleRequestError`, `ConsoleBusyError` and `ConsoleFaultError` in
  `console.py` and mapped each to its own fixed message in `app.py`;
- stopped a non-running submission from presenting an earlier result;
- added the all-demonstrations guidance table to the review expander;
- added the launcher's 1 MB message limit;
- added ten tests and one launcher assertion; no existing test was weakened,
  and the failing test passes unchanged;
- updated this document, the README and the status/traceability records.

## Validation record

- `ruff check .` passes. No Ruff fixes, safe or unsafe, were applied.
- Complete Module 6 pytest: **608 passed in 152.34 s**, no skips.
- `compileall` over all six module directories passes.
- Root collection: **2729 tests in 9.22 s**, 73 above the accepted observability
  baseline of 2656 (63 original console tests and 10 repair tests).
- Complete root pytest: **2723 passed, 6 skipped, 3 warnings in 233.43 s**. Skips
  are existing conditional Module 5 cases; warnings are existing Module 3 Chroma
  deprecations.
- All console tests run under the existing non-loopback DNS/connection guard
  with zero external attempts. One test runs with the OTel SDK enabled and
  reports `local` observation; the suite otherwise sets `OTEL_SDK_DISABLED` and
  therefore reports `degraded`.
- Not verified: a live browser session against the launched server, the 1 MB
  message limit under a real oversized frame (read from Streamlit source only),
  and a forged demonstration value through the UI (AppTest cannot submit one;
  covered at the service boundary).

## Console closeout: reviewer-visible scaling evidence

Added after the scaling benchmark was independently accepted, on explicit human
authorization of 2026-10-13. Starting point: clean HEAD
`faac33c4731ec89b4b83031116434574d7d09283`. The sections above are the record of
the original console and are kept as written; where they say that measured
throughput is absent from the console, this section supersedes them.

### What a reviewer sees

The page has a new bordered section, **Local scaling benchmark**, between the
result views and the review guide. It shows five fixed guidance lines (purpose,
action, expected result, what it proves, what it does not prove), a profile
selector with no default, and a **Run scaling benchmark** button that is disabled
until a profile is chosen. Selecting a profile or refreshing starts nothing.

| Profile | Plan run by the accepted benchmark | Typical duration on the recorded host |
| --- | --- | --- |
| Quick check | 2 workflows at caps 1 and 2, after one warm-up | About 20 seconds |
| Approved plan | 8 workflows at caps 1, 2 and 4, after one warm-up | One to two minutes |

After a run the section shows the report the benchmark just produced: one row per
cap (completed, wall time, throughput, median, peak in flight, overlap, speedup
against cap 1, workers reaped, invariants), then the classification, host facts,
warm-up state and call counts, then a fixed limitation line. Values the benchmark
did not derive are shown as "Not derived", never as zero. Nothing is copied from
an earlier run or from documentation.

### Boundary

`app.py` remains presentation only. It imports Streamlit, `console` and
`observability_contracts` and nothing else; a test asserts that import set and
that the page references no benchmark, clock, concurrency, process or environment
name. The page formats values and computes none.

`console.py` owns the boundary. `ScalingProfile` is a closed two-value choice.
`scaling_plan` maps it to a `BenchmarkPlan`; no number from the page or a caller
reaches the benchmark, so there is no workload control to forge or widen. Unknown
profiles and extra fields (workflows, caps, repeats, deadlines, runtime, keys) are
rejected before the benchmark is called. `ConsoleSession.run_scaling` calls the
unchanged `run_benchmark`, revalidates the returned report recursively and
requires it to match the selected plan before keeping it. `benchmark.py`,
`run_benchmark.py` and their tests are unchanged, and every bound, deadline and
invariant stays where it was accepted.

The scaling run shares the session's single admission lock with the eight
demonstrations, so one browser session cannot run a benchmark and a demonstration
at once. The session keeps only the latest report. Clear removes it.

### Outcomes and failure

- A report whose invariants held is shown with a success line.
- A report whose invariants did not hold replaces any earlier report and is shown
  as an error with its counts; an earlier success cannot remain on screen as the
  current result.
- A rejected, busy or faulted submission records nothing. On that rerun the page
  hides the earlier report and says the submission produced none; the earlier
  report reappears, with its age, on the next interaction.
- Faults are fixed text. No exception message, cause or SDK output is shown or
  retained.

### Wording corrected

- The observation-window caption no longer says the console has no throughput
  benchmark; it points to the scaling section as the only source of scaling
  evidence.
- The review guide no longer hard-codes "All 26 requirements remain Planned",
  which would have become false at status transition. It now says status is
  recorded in the traceability document.
- The opening notice and the review guide state that every agent is
  deterministic and that no model or LLM inference runs.
- LangSmith is described as offline SDK tracing evidence with no delivered trace
  and live verification pending. Grafana is described as the separate opt-in
  local stack with no link from the console.

### Claims

Scaling results are deterministic, local, single-host, machine-specific,
bounded-concurrency evidence. Speedup is a measurement and never a pass
criterion; it is not typical or portable performance. The console does not claim
production capacity, service levels, or cloud, horizontal or remote-cluster
scaling. No requirement status changed in this story; all 26 remain Planned.

### Security and cost

No external network call, credential, model or provider call, paid service,
Docker requirement or dependency was added. Tests run under the existing
non-loopback guard, including the real-process test with provider and LangSmith
keys present in the environment. The approved plan starts up to eight worker
interpreters; that is local CPU and memory only.

### Validation record

- `ruff check .` passes; the four changed Python files are already formatted. No
  Ruff fix, safe or unsafe, was applied.
- Console suites: **106 passed** (73 accepted plus 33 new: 25 service tests and
  8 page tests, counted with parameters). No existing test was changed.
- Complete Module 6 pytest: **794 passed in 215.84 s**, no skips (761 + 33).
- `compileall` over the established Modules 1 to 6 paths and the Module 6
  commands passes.
- Root collection: **2915 tests** (2882 + 33).
- Complete root pytest: **2909 passed, 6 skipped, 3 warnings in 291.15 s**; the
  skips and warnings are the existing Module 5 and Module 3 ones.
- One page test runs ten real worker processes through the page and checks every
  process handle exited with status zero and every temporary directory is gone.
- Two new tests failed on first run. Both were test defects, not candidate
  defects: a stand-in service that never yielded could not show overlapping
  admission, and a helper did not read the notice element. The tests were
  corrected; no production code changed for them.
- Not verified: a live browser session against the launched server. Human
  browser review remains a separate closeout action.

## Canonical live workflow demonstration (synthetic)

### What a reviewer sees

A separate bordered section, `Canonical live workflow (synthetic)`, runs the
accepted canonical Researcher → Analyst → Critic workflow through the
supervised live process path with a fixed module-level synthetic gateway
(`src/multi_agent_orchestration/synthetic_gateway.py`). The gateway returns
deterministic, role-shaped Ollama envelopes through `httpx.MockTransport`, so
no socket is opened and no inference runs. The run may submit any nonblank
bounded task text, including prompt-injection text; the synthetic replies and
authorizations cannot change because text is always data.

On completion it shows the synthetic offline classification, the three
validated role replies labeled as unverified model-shaped synthetic text,
model calls, repair attempts, token usage and transport retries, per-role
validated completion rows, a bounded event timeline, and post-run projection
statuses for the accepted LangSmith, local OpenTelemetry and local metric
window boundaries. On refusal or failure it shows the fixed sanitized
`failure_text` wording for the closed category. Nothing is delivered, exported
or collected externally.

### Authorization and exclusions

The authorization, model selection and budget are application-owned and fixed
inside `console_live.py`; the submitted text is the only input. There are no
deadline, step, budget, provider, model or delivery controls in this section.
The receipts remain classified `synthetic_offline` by the accepted canonical
service itself. No real live execution control, host execution, delivery,
trace export, credential handling or raw SDK metric dump was added.

### Boundary

`LiveRequest` validates the submitted text before any process is created;
`ConsoleSession.run_live` shares the single session admission lock, keeps at
most eight temporary `LiveRun` views, and raises the same sanitized request,
busy and fault error types as the other sections. The service calls the
accepted `execute_canonical_workflow`, revalidates the synthetic receipt and
terminal observation, and projects the terminal observation through the
accepted Slice 2, Slice 3 and Slice 4 boundaries only after the run returned.
Correlation across receipt, failure, terminal and events is validated; forged
or corrupted views are not renderable. `app.py` presents the curated view only.

### Validation record

- `ruff check` passes on the changed files; `compileall` passes.
- New console live suite: **28 passed** (`tests/test_console_live.py`,
  counted with parameters), including two real supervised child-process runs
  under the existing non-loopback guard, injection attacks, forged commands
  and views, refusal before any execution, sanitized failure/cancel/fault
  paths, admission sharing, projection-failure isolation and page tests with
  runs through the real Streamlit UI. No existing test was changed.
- First cold runs on a cold file cache may expire the honest 30,000 ms run
  deadline while the child process warms up; the guarded bounded helper makes
  up to four attempts (asserting any interim outcome is only the honest
  timed-out boundary) and the page guidance says to retry manually.
- Not verified: a human browser session against the launched server; that
  remains a separate closeout action.
