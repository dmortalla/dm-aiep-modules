# Deterministic Local Scaling Benchmark

Verified starting branch: `feature/module-06-architecture`; clean HEAD
`e471f5d6cb8e45664664d2af8daa5195eb823172`, subject
`feat: add opt-in local operational telemetry pipeline`. The story, its
benchmark-scoped admission control and report-only speedup were explicitly
human-approved on 2026-10-12. Architecture B+, all ADRs, the 26 frozen source
requirements, dependencies and every accepted source and test file are unchanged.

## Purpose and boundaries

This story measures how completed work changes as permitted concurrency changes,
which no earlier slice did. It holds one workload constant and varies one thing:
how many workflows the benchmark admits at once.

Nothing here runs by default. Imports, tests, the Streamlit console and the
telemetry command never start a benchmark. Evidence classes stay distinct:

| Class | What it is | Status |
| --- | --- | --- |
| Deterministic offline tests | Plan authority, admission, accounting and cleanup with an injected clock | Implemented and gated |
| Local multi-process measurement | Real worker processes on one workstation, run by the operator command | Observed locally, recorded below |
| Hosted, multi-host or cloud capacity | Horizontal or production scaling | Not implemented, not claimed |
| Live AI behaviour under load | Model-backed workflows | Not implemented, not authorized |

## What is measured

The measured unit is the accepted local two-process distributed workflow
(`execute_distributed_workflow` through `execute_observed_workflow`): a
coordinator dispatches one fixed synthetic instruction to two independent ADK
worker interpreters and validates their results. Every workflow in a benchmark is
identical work with a fresh request identity.

One level submits a fixed number of these workflows and admits at most `cap` of
them at a time. The approved plan is 8 workflows at caps 1, 2 and 4. Cap 1 is the
sequential baseline. Cap 4 means at most eight worker interpreters.

The in-process LangGraph, CrewAI and single-process ADK paths are deliberately
not benchmarked. Their deterministic work takes milliseconds on one event loop,
so concurrency cannot shorten it and timing would be noise. Comparing them with
the process-based path would compare start-up costs, not scaling.

## Architecture

```text
run_benchmark.py            operator command, does nothing without --run
      |
benchmark.py                plan, admission, measurement, validation, report
      |  at most `cap` workflows admitted per level
execute_observed_workflow   accepted, unchanged
      |
execute_distributed_workflow -> two worker interpreters per workflow (accepted)
```

`benchmark.py` adds three immutable contracts and one service.

- `BenchmarkPlan` is operator-owned. `mode` is required and has no default. Caps
  must be ascending values from 1, 2 and 4; workflows 2 to 16; repeats 1 to 3;
  per-workflow deadline at most 30 000 ms. A mapping, string, subclass or
  `model_construct` forgery is refused before anything executes. Workflow
  requests, runtime output, credentials and environment variables cannot set any
  of these values, and no runtime or provider is selectable.
- `LevelResult` and `BenchmarkReport` validate their own consistency, so a
  report cannot claim a pass that its counts contradict.
- The service returns a report and writes no file.

### Benchmark-scoped admission

Admission is an `asyncio.Semaphore` created inside one level and discarded with
it. It is not a platform worker pool, queue, scheduler or global limiter, and no
other code path uses it. Module 6 still has no cross-workflow concurrency
service; adding one would be a separate architecture decision.

## Methodology

1. One warm-up workflow runs and is discarded, so first-use effects stay out of
   the first level. If it fails, no level runs.
2. Levels run in ascending cap order. Each level has a fresh admission gate, a
   fresh adapterless `Observability` and fresh request identities, so nothing is
   shared between levels or repeats.
3. Each workflow keeps its accepted deadline. Each level also has a deadline
   derived from the plan, `ceil(workflows / cap) x timeout + 30 s`, after which
   unfinished workflows are cancelled.
4. Waiting is shielded: each workflow receives one cancellation request however
   often the caller cancels, and the level returns only after every workflow has
   settled, which in the accepted service means workers killed and reaped.
5. The run stops at the first level that breaks an invariant. No throughput,
   overlap or speedup is derived from such a level.
6. Repeats, when requested, are reported separately and never averaged.

All timing uses one monotonic clock (`time.perf_counter`).

## Measurements

Per level, all observed:

| Value | Source |
| --- | --- |
| requested, completed, failed, timed out, denied, cancelled | Outcome of each awaited workflow |
| wall-clock seconds | Clock around the level |
| throughput per second | completed / wall |
| duration minimum, median, maximum | Clock around each admitted workflow |
| peak in flight | Benchmark counter inside the admission gate |
| overlap factor | Sum of workflow durations / wall |
| workers reaped | Two per validated completion |
| integrity | Every result revalidated against the benchmark's own request |
| observer started, completed, drops, adapter failures | The level's `Observability` |
| speedup against cap 1 | Cap-1 wall / this wall, same repeat |

Two labels need care. "Peak in flight" counts workflows the benchmark admitted;
it is not a sample of live operating-system processes, which is bounded at twice
the cap by construction. "Workers reaped" follows from validated evidence and the
accepted service contract, which returns only after reaping both workers; the
process handles themselves are checked in tests, not by the operator command.

Not measured, and absent from the report contract: queue depth, worker
utilisation, CPU or memory use, tokens, prices, cost and capacity. A value that
was not derived is `null`, never zero. Call and retry counts are zero only when
every level passed, because validated evidence fixes them; otherwise they are
`null`.

## Acceptance invariants

A level passes only if all of these hold. None depends on the machine.

- every requested workflow completed, with none failed, timed out, denied or
  cancelled, inside the level deadline;
- every result matched the benchmark's request: identities, limits, coordinator
  process, character count and the expected output text;
- peak in flight never exceeded the cap, and none remained in flight;
- the observer saw exactly the requested starts and completions and dropped none;
- the longest workflow fits inside the level's wall time, and the sum of
  durations is at most cap x wall.

The last pair is exact rather than a threshold: every duration is measured
inside the level's window on the same clock, and at most `cap` overlap.

### Why speedup is not an acceptance criterion

Speedup depends on the host's cores, load and process start-up cost. A required
minimum would be a machine-dependent threshold and would make the benchmark fail
or pass for reasons unrelated to correctness. Speedup is therefore reported as an
observation and never affects the result or the exit code. A test drives a higher
cap to be slower than cap 1 and confirms the benchmark still passes.

## Running it

From the repository root, with the accepted environment synchronized:

```powershell
uv run --locked --offline python module-06/run_benchmark.py --run
```

Without `--run` the command prints a notice and exits with status 2.
`--workflows` (2 to 16) and `--repeats` (1 to 3) are bounded; caps are fixed at
1, 2 and 4. `--json` prints the validated report instead of the table. The exit
status is 0 when every invariant held and 1 otherwise. No credentials, network
access or Docker stack are needed.

## Observed local evidence (2026-10-12)

Host: Windows (`win32`), Python 3.12.14, 22 logical CPUs. One run, default plan,
warm-up completed.

| Cap | Completed | Wall s | Per second | Min s | Median s | Max s | Peak | Overlap | Speedup |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 8 / 8 | 28.09 | 0.285 | 3.44 | 3.49 | 3.65 | 1 | 1.00 | 1.00 |
| 2 | 8 / 8 | 15.68 | 0.510 | 3.78 | 3.90 | 4.02 | 2 | 1.99 | 1.79 |
| 4 | 8 / 8 | 9.68 | 0.827 | 4.51 | 4.74 | 5.14 | 4 | 3.96 | 2.90 |

48 workers reaped; model, provider and external calls and retries all 0; every
invariant passed; exit status 0.

Reading these numbers: wall time fell as the cap rose, while each workflow took
longer (median 3.49 s at cap 1, 4.74 s at cap 4). Speedup was therefore below the
cap. Workflow time is dominated by interpreter start and SDK import, so this is
start-up-bound throughput of process-per-worker execution. It is one sample on
one workstation and will differ on other hosts and under other load.

## What this proves, and what it does not

It shows, on one workstation, that:

- several distributed workflows can run concurrently under an explicit cap with
  every result validated and every worker reaped;
- the cap is respected and the observed overlap matches it;
- completed work per second rose with the cap for this workload on this host.

It does not show, and no document should cite it for:

- hosted, cloud, multi-host or production horizontal scaling or capacity;
- a maximum capacity or saturation point (the cap stops at 4);
- sustained-load or soak behaviour (a run lasts about a minute);
- queue depth, worker utilisation, CPU or memory consumption;
- scaling of the in-process LangGraph, CrewAI or single-process ADK paths;
- behaviour with live model calls, which are I/O-bound and would scale differently;
- telemetry stack behaviour under load;
- statistical confidence, or any universal performance improvement;
- POSIX behaviour; the distributed path is verified on Windows only.

## Validity controls

| Risk | Control |
| --- | --- |
| Warm-up effects | One discarded warm-up; fixed ascending order; repeats shown individually |
| Scheduler and timing noise | Minimum, median and maximum reported; no timing assertion anywhere |
| Tiny-workload noise | Millisecond in-process paths excluded; the unit takes seconds |
| Process start-up overhead | Stated as what is being measured, not hidden |
| Machine-specific results | Host facts in every report; classification `local_single_host` |
| Docker and telemetry overhead | No Docker, exporter or adapter in the core path |
| Misleading speedup | Descriptive only; overlap shown beside it; fixed disclaimer in output |
| Flaky timing tests | Injected clock and wave-controlled service in deterministic tests |
| Accidental external calls | Existing non-loopback guard; accepted worker environment allowlist |
| State leakage | Fresh identities, gate and observer per level; shielded settle before return |

## Security, cost and reliability

No new trust boundary, privilege or subprocess authority is introduced: workers
are launched only by the accepted service. Its output remains untrusted until
the benchmark revalidates it. The report carries no instruction text, workflow,
task, assignment, trace or span identifier and no PID. No metric name or label
was added and `telemetry/` is unchanged; Prometheus and Grafana are not required,
because the benchmark's own clock and validated counters are authoritative here.

No model, provider, paid or network call is made and no credential is read.
Credential and provider flags in the environment change nothing. The real cost
is local CPU and memory for up to eight worker interpreters for about a minute.

Work is bounded by count, cap, per-workflow deadline, level deadline and zero
retries. The derived worst case for the default plan is under ten minutes.

## Files and evidence

Exactly six intended Module 6 files:

- New source: `src/multi_agent_orchestration/benchmark.py`.
- New operator command: `run_benchmark.py`.
- New tests: `tests/test_benchmark.py`.
- Documentation: this file, `PROJECT_STATUS.md`, `TRACEABILITY.md`.

`tests/test_benchmark.py` has **66 passing cases** under the existing guard that
fails on any non-loopback DNS lookup or connection. Sixty-five replace only the
accepted distributed service behind the observed execution boundary and use an
injected clock, so they assert exact values without real time. They cover:

- the required mode, approved defaults and derived level deadlines;
- 23 out-of-range or unknown plan values and six forged plan objects, with
  nothing executed;
- caps bounding admission exactly, proved by waves that only fill when the cap
  is really reached, and peak limited by the workload when the cap is larger;
- throughput, overlap and speedup arithmetic, a slower higher cap that still
  passes, and absent speedup without a cap-1 baseline;
- repeats reported separately, fresh identities and fixed authority for all 25
  requests of a default run, with credentials present in the environment;
- warm-up failure stopping before any level;
- failure, timeout and denial accounting, siblings finishing, the run closing
  and no derived value on a failed level;
- four kinds of untrusted service output failing integrity;
- level deadline expiry, and repeated caller cancellation that still waits for
  cleanup, each leaving no pending task;
- a failing observation adapter changing nothing except its own failure count;
- a payload-free report with no invented field names, and 18 forged level and
  report mutations rejected;
- the operator command doing nothing without `--run`, bounded arguments, JSON
  and table output, and a failed run reported without invented values.

One integration case runs eight real worker processes (two workflows at caps 1
and 2) and asserts completion, integrity, peak, exit status zero for every
process handle, removed temporary directories, zero calls and the exact
invariants. It does not assert that cap 2 is faster.

## Conservative acceptance

Requirements: new partial local evidence for M6-005, M6-017, M6-018, M6-020,
M6-024 and M6-026, and marginal evidence for M6-019 (zero calls under concurrent
load; local time per workflow measured; no token, price or optimisation
evidence). M6-002 gains nothing: intra-workflow parallel agents are unchanged.
All 26 source meanings and Planned statuses remain frozen; nothing is marked
complete or verified. Product experience: an operator command; no console
integration. Real functionality: real local worker processes. Reliability:
bounded admission, deadlines, fail-closed levels and settled cleanup. Security:
operator-owned plan and revalidated output. Cost: no paid service. Evidence:
offline tests plus one recorded local run. Deployment: unverified.

## Validation record

- `ruff check .` passes. Ruff formatting was applied only to the three new
  Python files; no unsafe fixes were used.
- Focused suite: **66 passed in 11.80 s**, also with unraisable-exception
  warnings treated as errors.
- Complete Module 6 pytest: **761 passed in 173.53 s**, no skips (695 accepted
  plus 66 new).
- `compileall` over the established Modules 1 to 6 source, test, example and
  application paths plus the three Module 6 commands passes.
- Root collection: **2882 tests**, 66 above the accepted telemetry baseline of
  2816.
- Complete root pytest: **2876 passed, 6 skipped, 3 warnings in 250.10 s**.
  Skips are existing conditional Module 5 cases; warnings are existing Module 3
  Chroma deprecations.
- `git diff --check` passes; scope is exactly the six files listed above.
- During implementation one new test (repeated caller cancellation) failed
  twice and exposed a real defect: a repeated cancellation reached in-flight
  workflows and interrupted their cleanup. The wait was made shielded from the
  start so each workflow is cancelled once. The test was not changed.

## Unverified limitations

- Everything listed under "does not show" above.
- The operator command does not inspect process handles; reaping in a real run
  rests on the accepted service contract and validated evidence.
- Memory and CPU use of eight concurrent worker interpreters was not measured.
- One recorded run; no repeated-run statistics.
- The benchmark is manual and is not part of pytest or CI beyond its tests.
- Benchmark runs are not delivered to Prometheus or shown in the console.
