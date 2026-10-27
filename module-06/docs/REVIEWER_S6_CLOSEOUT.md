# S6 candidate: reviewer guidance, polish and code-quality closeout

> **Status note (S7).** S6 was independently accepted and committed at `998b0d8da8cadc4cb0e9a2230dbe8b1e39276161`; the "candidate" wording below is the record as written before acceptance. The root-suite first-run record is reconciled in [PROJECT_STATUS.md](PROJECT_STATUS.md#known-reliability-observation-unresolved-and-future-hardening).

Baseline: clean `feature/module-06-architecture` at
`bb383fcbdee624e64aa9ac025018389d41bc905c`, empty index. S1–S5 are accepted and
committed. This candidate implements S6 only; S7 documentation/traceability
reconciliation is not started. Architecture, evidence taxonomy, the trusted-local
capability, `LiveAuthorization`, ADR-008 and the public fail-closed posture are
unchanged. No dependency or lockfile changed.

## Later presentation update (not part of S6)

After S6 acceptance the cockpit presentation evolved. The current app has six
tabs with the Guide first (Guide, Deterministic Demo, Live / BYOK, Operations,
LangSmith Tracing, Implementation Evidence), restores every accepted
`GUIDANCE_SECTIONS` panel in the Guide, and contains exactly one bounded,
application-owned static CSS block rendered with `unsafe_allow_html=True`.
The security invariant is not that the flag never appears: the allowed surface
is one literal `<style>` element, no workflow, model, user, tool or provider
value can flow into it, untrusted text stays inert, and there is no iframe,
component or link surface (pinned by AST and rendered-page tests in
`tests/test_cockpit_s6.py`). A separate private-local launcher
(`run_local_live.py`) supplies the trusted runtime to a private operator; the
stock app and public posture are unchanged. The S6 description below is the
accepted S6 state and is preserved as history.

## Reviewer experience

Each workflow tab now opens with compact Purpose / Action / Expected result /
What it proves guidance; Demo and Live also state what they do not prove. The
header names the observability story in three layers (LangSmith for AI/agent
tracing; OpenTelemetry → Collector → Prometheus → Grafana for operations,
verified end-to-end locally and not hosted; Streamlit as the unified reviewer
view) and points newcomers to the Guide. Stale "later story" wording was
removed from the header, the LangSmith tab and the Guide.

The Guide renders every static `GUIDANCE_SECTIONS` panel: where to start, what
Module 6 demonstrates (all orchestration architectures), Demo, Live / BYOK (BYOK
is trusted-runtime connectivity, never a key field; why public live is
fail-closed), the composed evidence labels, recorded versus fresh evidence, the
observability layers, current-host localhost semantics, LangSmith, how to test
each capability and what evidence does not prove. The Operations tab now shows
the Grafana data-source total; the LangSmith tab shows each recorded trace
identifier as inert text. No widget, link, iframe or HTML was added in S6 (as
committed at `998b0d8`; the later presentation update below changes the HTML
statement).

## Non-blocker disposition

| Item | Disposition |
| --- | --- |
| S3-1 stale S1/S2 status headings | Already resolved; the stale S5 heading and Current State were repaired |
| S3-2 `age_seconds` duplicates `age_in_seconds` | Repaired: `console.age_seconds` delegates to the S1 helper |
| S3-3 "no cause retained" docstrings vs chaining | Repaired: `ConsoleFaultError` and the check/inspection docstrings state which paths chain |
| S3-4 concurrent explicit checks | Deferred (see concurrency below) |
| S3-5 Grafana data-source total dropped | Repaired: stored as `grafana_datasource_total` and presented |
| S3-6 coverage gaps | Repaired with focused S6 tests |
| S3-7 "moved" vs "added" wording | Already resolved |
| S4 Run 5 classification presentation | Already resolved in S5; S6 test pins it in both tabs |
| S4 fuller recorded reference facts | Repaired: recorded trace identifiers shown as inert text |
| S4 unavailable vs failed-read wording | Already resolved in S5; still accurate (the page supplies no capability) |
| S4 holder-service wording | Already resolved in S5 |
| S4 `TraceReadProvider` trusted-caller note | Already resolved in S5; Args/Returns/Raises added |
| S4 unused `Exploding` helper | Repaired: removed |
| S4/S5 status chronology | Repaired |

Additional S6 findings, repaired: the operational reader followed HTTP redirects
(a loopback reply could steer a read to another host) and now refuses them;
HTTP protocol errors from a local stack surfaced as console faults instead of an
honest unavailable state; the current-host dashboard reference was offered even
when Grafana was not read; "Clear recent results" left a retained LangSmith
inspection; and several docstrings described delivered S3/S5 behaviour as
future work or overstated "never raises".

## Audits

- Security: no credential, password or key field (whole-page input inventory is
  pinned by test); session state holds only the console of closed revalidated
  views; no authorization, permit or runtime is retained (S5 object-walk tests
  unchanged); dynamic values render through `st.text`/`st.metric`/`st.json` or
  closed literals; at S6 acceptance no `unsafe_allow_html`, and no links, iframes
or components (a later presentation update adds one bounded static CSS block,
see below); endpoints,
  trace targets, provider, model and budget are application constants; localhost is
  never trust; nothing executes, queries or writes on render.
- Docstrings and types: Google-style docstrings and return types now cover every
  public class, function and method in the cockpit, console and live-console
  modules (pinned by test), plus the observability, observation-contract,
  live-observation, distributed and validator interfaces. Private underscore
  worker/adapter modules keep their existing documentation (internal, not public).
- Exceptions: execution actions suppress causes; read-only checks chain causes
  for in-process diagnostics only; neither is stored or rendered. Expected read
  failures are explicit tuples, unexpected failures reach the sanitized console
  boundary, and no blanket swallowing was found.

## Cold-start timing

The CrewAI demonstration imports CrewAI inside a fresh child process within the
accepted 30,000 ms workflow deadline; `app.py` and the parent never import CrewAI.
On this workstation a first cold `import crewai` measured 113 s of wall time
(one observation, cold disk cache), and a warm import measured 7.9 s. No
parent-side lazy-import change can shorten the child's import, and pre-warming
would need eager imports, a deadline change or a process-isolation change, all
out of scope. Classification: non-blocking environment/load timing risk.
Discrimination: rerun the exact node
`module-06/tests/test_console_app.py::test_actual_accepted_demonstrations_run_through_ui[CrewAI collaboration]`
warm; a warm pass indicates environment load, a repeatable warm failure a regression.

## Concurrency

Streamlit runs one script at a time per browser session, so each explicit click
maps to at most one action; reruns never re-query (S3/S4 tests). Live execution
is already guarded by the session lock and the runtime's nonblocking lock. The
operations and LangSmith checks are read-only, bounded, single-attempt and
write-free; only direct multi-threaded API callers could run two such reads
concurrently, which duplicates no write or external effect. No lock was added.

## Validation

Recorded in [PROJECT_STATUS](PROJECT_STATUS.md#reviewer-cockpit-s6-candidate-not-accepted-guidance-polish-and-code-quality-closeout).
No real model, provider, LangSmith, telemetry, credential or container operation
was performed. No deployment, release, completion or requirement advancement is
claimed. The S6 candidate is not independently accepted.
