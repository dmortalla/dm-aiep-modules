# Reviewer Experience Contract: Unified Module 6 Observability Cockpit

> **Status note (S7).** Stories S1-S6 are delivered, independently accepted and committed; S7 reconciliation is a candidate. This contract remains the planning record it was written as; delivery status is in [PROJECT_STATUS.md](PROJECT_STATUS.md).

## Purpose and status

This contract defines the final reviewer-facing Module 6 Streamlit
experience: the accepted current-state findings, the accepted minimal
architecture, bounded implementation stories, security boundaries and
acceptance criteria. It is a planning artifact; it adds no requirement ID,
changes no accepted contract, and advances no requirement status.
Implementation proceeds only through the stories below under the existing
Builder -> independent Reviewer -> commit workflow and the established
quality gates.

## Current-state findings (evidence-grounded)

Accepted reusable capability:

- The committed `app.py` is the Streamlit presentation layer only
  (`st.*` rendering and session state); authoritative business logic lives
  in `console.py` and the wider application layer, not in the UI.
- Deterministic console service (`console.py`, 8 non-live demonstrations
  plus worker guard) with validated evidence; no model, no network, no
  credentials.
- Bounded real two-process ADK distribution and the scaling benchmark with
  accepted local run evidence; the console scaling presentation was
  independently accepted.
- Synthetic reviewer-facing canonical live demonstration
  (`console_live.py`, `synthetic_gateway.py`); explicit authority objects;
  local projection statuses (LangSmith/OTel/metrics); payload-free views;
  pinned 30,000/5,000 synthetic authority; receipts classified
  `synthetic_offline`.
- Real live path (`canonical_workflow.execute_canonical_workflow`) with
  fresh explicit `LiveAuthorization`/`LiveBudget` per execution; ADR-008
  NORMAL profile (`live_policy.py`, policy data only, never authority);
  supervised child runtime; closed failure taxonomy; recorded Runs 3-5 in
  the canonical evidence ledger.
- LangSmith chain: local projection
  (`live_langsmith.project_live_observation`); deterministic external
  delivery with a `service_read` receipt (`langsmith_delivery.py`,
  `run_langsmith.py`); live-family delivery with the committed
  `unverified_write` contract (`LiveLangSmithDelivery`).
- Operational telemetry chain: `telemetry_delivery.py` (loopback-only
  `DeliveryConfig`, guarded OTLP exporter, `grafana_reference()`,
  `prometheus_scalar()`, `grafana_scalar()` helpers), `run_telemetry.py`
  (deliver + verify), `telemetry/` Compose stack; the 2026-10-23
  authorized deterministic end-to-end local pipeline verification
  (Collector -> Prometheus -> Grafana).

Front-end gaps for the final cockpit (presentation-layer only; nothing
requires new backend/domain authority):

1. The demonstrations, live views and scaling views exist as separate
   console sections rather than one unified evidence-labelled cockpit.
2. No operational-metrics aggregation view in Streamlit (a recorded
   limitation).
3. No LangSmith aggregation view in Streamlit; projection/delivery states
   are operator-command surfaces today.
4. No live-with-delivery composition from the UI; live delivery is
   operator-only today.
5. Guidance gap (refined): the committed app already carries limited,
   general reviewer guidance per demonstration, but it lacks the required
   per-mode, evidence-labelled guidance surface of this contract.
6. No backend-availability model (Prometheus/Grafana reachable or not).
7. Reconciliation note: the committed `app.py` specialist-observability
   wording predates the accepted LangSmith delivery evidence and is stale;
   it must be reconciled during the appropriate presentation story (S2/S4).

## Final presentation architecture (minimal, accepted as sound)

Preserve: Streamlit/API -> application layer (`console.py`) -> orchestration
service -> workflow domain + policy/security + observability -> runtime
interface (LangGraph/CrewAI/ADK) -> validated evidence -> telemetry/events
-> Streamlit + LangSmith + Grafana. OpenTelemetry Collector remains the
ingestion boundary. Streamlit is the curated presentation/aggregation layer
only — never the telemetry store, specialist operations backend, agent
authority or security authority. Prometheus remains the metrics backend;
Grafana remains the specialist operational drill-down; LangSmith remains
specialist AI/agent tracing. No iframes for Prometheus, Grafana or
LangSmith; no public Prometheus; no new backend authority.

Components (module-scoped, additive):

- `cockpit_view.py` (new, application layer): immutable evidence-view
  contracts, the evidence/provenance/confirmation composition of B3, the
  `CockpitState` mode/state model, and the reviewer guidance content.
- `console.py` / `console_live.py` (minimal additive methods only): expose
  existing validated evidence collections to the cockpit view builders;
  the live-with-delivery composition is a new bounded method delegating to
  the committed live-family delivery with an explicit
  `LangSmithDeliveryConfig` supplied by explicit operator selection at
  submit time; no new authority anywhere.
- `cockpit_ops.py` (new, application layer): bounded local operational
  aggregation reusing the committed loopback helpers and fixed query
  patterns, behind the B2 explicit-selection/activation model; strict
  timeouts; every fetch wrapped in closed failure categories with an
  honest `unavailable` fallback; reads only the loopback of the current
  running host; never a credential; never a proxy request
  (`ProxyHandler({})` retained).
- `app.py` (presentation only): a tabbed cockpit (Demo / Live BYOK /
  LangSmith tracing / Operations / Reviewer guide) calling only
  application service/view interfaces; it renders no control flow, no
  validation, no provider, authority or telemetry logic.

### Mode/state model (with B2 activation state)

- `demo` (default): the eight deterministic demonstrations (+ scaling).
  Importing, starting or rendering the cockpit in Demo mode performs zero
  localhost and zero external observability requests; demo execution
  remains the deterministic offline applications only.
- `live_byok` (explicit opt-in; see B1 deployment posture): the real-local
  canonical path with fresh explicit NORMAL-profile authorization per
  execution; available only in the supported local/operator runtime
  posture; otherwise truthfully unavailable.
- `guide`: static curated guidance.
- Operations surface: an explicit activation/query state, NOT an implicit
  side effect of rendering. Rendering or rerunning the app — in any mode —
  performs no probe; operational evidence is fetched only when the
  reviewer explicitly selects the bounded query action (click/state of
  that story's control), with results timestamped and labelled as
  current-host local observations when fresh and `unavailable` when the
  local specialist stack is not reachable.

### B3 — Evidence model: composition, not coarse enum

Each presented item carries a small structured composition instead of a
single coarse five-value enum, so accepted vocabulary is preserved
verbatim and no false implication is possible:

- `execution_kind`: `deterministic_demo` | `canonical_live_demo` |
  `canonical_real_local` | `unavailable` | `not_executed` (distinguishes
  how the presented content was produced).
- `provenance` (accepted classes verbatim where an authoritative evidence
  classification is presented): `synthetic_offline` for the synthetic
  canonical demonstration; `local_provider_execution` for real local
  model-backed executions; the historical out-of-policy observation label
  (`out_of_policy_observation`) where the Run 3 record is presented.
- `delivery_confirmation` (LangSmith items only, exact committed
  vocabulary): `service_read` (deterministic-path accepted delivery),
  `accepted_only` (accepted write, no service read-back inside the
  window), `unverified_write` (live-family committed 2xx-write contract),
  `not_sent`, or none-where-not-applicable.
- `operational_classification` (Operations items only): exactly
  "authorized deterministic local operational-telemetry pipeline
  verification" for the recorded accepted event; fresh bounded query
  results are never merged with it.
- `source`: `fresh_execution` | `recorded_historical` — every item from
  the curated static source is labelled recorded/historical.

Definition of the historical/recorded source: historical/recorded cockpit
evidence is a curated presentation-layer static source derived from the
accepted repository ledger/documentation records (canonical live workflow
ledger, telemetry record, LangSmith delivery record). It is NOT a fresh
execution, NOT a runtime query, and NOT a new telemetry/evidence database,
service or store. It must be labelled recorded/historical wherever shown
and must never masquerade as current live evidence.

Accepted classes are never renamed into stronger or ambiguous presentation
labels: where the UI presents an authoritative classification, the accepted
string appears verbatim.

### B1 — Deployment posture and live/BYOK authority

1. Local operator live/BYOK execution is supported only through an
   explicitly trusted local/operator runtime that satisfies the accepted
   credential and authority boundaries (Credential Manager target
   `LangSmith-Module6` -> trusted operator process -> process-local
   `LANGSMITH_API_KEY` -> execution child; committed
   `credential_format_valid` check without disclosure; value cleared after
   use; never displayed, logged, persisted, embedded in artifacts or
   placed in URLs).
2. Deployed deterministic Demo mode is always the baseline supported
   reviewer path and works without Docker, Ollama, LangSmith credentials,
   provider credentials or developer-workstation access.
3. A deployed/public Streamlit application MUST treat live/BYOK execution
   as unavailable unless a separate deployment-compatible
   secret/identity/authorization boundary has been deliberately
   implemented, independently verified and explicitly enabled. No such
   boundary exists today; it is not invented in this contract.
4. The current Windows Credential Manager mechanism is a local/operator
   mechanism and MUST NOT be assumed to exist or be appropriate in a
   Linux/public Streamlit deployment.
5. A server-side credential MUST NEVER become usable merely because an
   untrusted/public visitor can access the Streamlit application.
6. Credential presence MUST NEVER authorize execution.
7. Every live execution still requires a fresh explicit `LiveAuthorization`
   bound to that execution (NORMAL profile values stated per execution).
8. Stale, replayed, session-state-derived, environment-derived,
   model-derived or visitor-derived authority is forbidden.
9. Optional external LangSmith delivery/write is explicitly operator
   initiated and MUST NEVER be visitor-triggered merely by rendering,
   opening or interacting with a public reviewer page.
10. No provider escalation; no hosted/paid fallback; no automatic rerun;
    timeout stays fail-closed.
11. Where the required secure runtime is unavailable (including every
    deployed/default environment), live mode presents an honest
    unavailable state and offers no execution; it never fabricates a
    result.

### B2 — Operational aggregation selection and localhost boundary

- Operational live/local querying requires the explicit bounded query
  action; Demo import/start/render and mere Operations-tab rendering
  perform zero requests.
- Any `127.0.0.1` value always means the loopback of the current running
  host. In a deployed Streamlit app, that is the deployed host/container —
  never the developer/operator workstation — and the UI never labels
  deployed-host loopback values as operator-workstation evidence.
- Unreachable specialist stack => honest `unavailable` state; values are
  never fabricated; historical accepted evidence is never silently
  substituted for a fresh observation.
- Historical accepted operational evidence may be displayed separately and
  explicitly labelled recorded/historical (B3 `source`).
- Prometheus remains non-public; Grafana remains specialist drill-down and
  reference only where genuinely reachable; Streamlit remains the curated
  presentation layer.

### LangSmith aggregation boundary (native; no iframe)

Presented natively and only from application-held validated
projections/receipts: delivery/confirmation state using the B3 vocabulary;
project `module6-verification` and fixed destination as reference facts;
trace/run identifiers already in validated view models; bounded summaries
(calls/repairs/retries/tokens/duration/cleanup). Externally sourced
identifiers — LangSmith run/trace IDs and dashboard references among them —
are rendered as inert escaped text by default. An actual clickable external
link is created only when the destination is fixed/trusted or independently
validated, no secret is present, the link is genuinely useful, and the
evidence classification is not strengthened by the link. The UI never
fetches LangSmith; nothing claims service-side visibility where it does
not exist.

### Reviewer guidance content

Per-mode, evidence-labelled panels explaining: what Module 6 demonstrates;
how Demo mode works and what a run proves; how live/BYOK differs (real
local inference, fresh-per-run authorization, evidence classes and
limitations, honest unavailability); what each result view means
(including `denied`, `timed_out`, projection statuses,
`unverified_write`/`service_read`/`accepted_only` distinctions); what the
evidence does NOT prove; and where LangSmith (specialist AI/agent tracing)
and Grafana (specialist operations drill-down) fit. Static, deterministic,
test-visible. Both layers are covered: the guidance panels are implemented
during S6, while the committed stale `app.py` wording is reconciled in the
appropriate story (S2/S4).

### Error/redaction behavior

All failures render from validated sanitized contracts (`failure_text`,
closed categories); no exception text, provider diagnostics, prompt or
model payload is rendered; denial/failure states are first-class
presentations; stale session results age out per the accepted console
rules.

## B4 — Final code-quality closeout (explicit, auditable)

The closing quality gate — after the stories' functional code — requires
evidence of each of the following, not reference to an absent list:

- Google-style docstrings for appropriate modules, classes, public
  functions and public methods.
- `Args:`/`Returns:`/`Raises:` sections where applicable.
- Type hints on public interfaces.
- Intentional exception handling only at real failure boundaries;
  specific, actionable, sanitized error reporting; exception chaining
  where appropriate.
- Expected failure-path tests for every new failure behavior.
- No blanket exception swallowing.
- Ruff `check .` clean.
- Relevant focused test suites green.
- Complete Module 6 pytest green.
- Complete root (repository) pytest green.
- `python -m compileall` over module source/tests and the app clean.
- Final `git diff --check` and line-ending/BOM verification clean.

S6 keeps two explicitly distinct parts: (a) implementation work — reviewer
guidance/polish panels and page tests; (b) the closing quality gate listed
above, performed and reported as its own auditable sequence.

## Implementation stories (bounded; Builder -> Reviewer -> commit)

- **S1 — Cockpit evidence/view/state contracts:** `cockpit_view.py` with
  the B3 composition (no enum proliferation beyond what the accepted
  vocabulary requires), `CockpitState` with the B2 Operations
  activation/query state, the recorded-historical static source
  definition, and guidance text; tests prove every view invariant
  (payload-free view models), redaction, no-execution-on-import, and that
  historical items are labelled recorded/historical.
- **S2 — Demo tab integration:** refactor `app.py` to the tabbed cockpit;
  demo/ops flows run through existing service methods only; every view
  labelled with its B3 class; Demo rendering performs zero localhost /
  external observability requests; reconcile the stale
  specialist-observability wording in the same story; existing console,
  live and console-app tests keep passing unchanged.
- **S3 — Operational observability aggregation:** `cockpit_ops.py` behind
  the explicit activation/query state; bounded current-host loopback
  probing with closed failure categories; `unavailable` states; separate,
  clearly labelled recorded/historical operational evidence block;
  deployed-host 127.0.0.1 never labelled operator-workstation evidence.
- **S4 — LangSmith aggregation:** tracing tab fed by validated
  projection/delivery records; exact committed vocabulary
  (`unverified_write`, `service_read`, `accepted_only`, `not_sent`); no
  fetch, no iframe; inert escaped identifiers by default with the
  fixed/trusted-link rules; bounded-attribute and injection tests.
- **S5 — Secure local live/BYOK presentation:** explicit-submit live panel
  composing the committed real path with fresh per-execution
  `LiveAuthorization` (NORMAL bounds) and optional single explicit
  delivery with explicit config; the full B1 deployment posture (10
  numbered rules) enforced.
- **S6 — Reviewer guidance/polish, then explicit final code-quality
  closeout:** guidance panels and page tests; then the B4 closing quality
  gate as its own auditable sequence (Ruff, focused, full Module 6, full
  root, compileall, diff/whitespace).
- **S7 — Documentation/traceability reconciliation:** record the delivered
  cockpit; traceability rows for presentation evidence; release-phase
  hooks retained for human browser acceptance, deployment verification,
  root README reconciliation, publication/release and recruiter-facing
  closeout — all explicitly later gates, not implied by cockpit
  completion.

### Story-level acceptance tests (security-adversarial minimum)

- Deployed/untrusted-session posture: live execution unavailable; no model
  execution occurs; no external LangSmith write occurs; a server-side
  credential's mere presence cannot make live execution available to an
  untrusted session; credential absence produces an honest unavailable
  state, not fabricated success.
- Demo rendering performs zero localhost/external requests; Operations
  rendering without the explicit query action performs zero requests; the
  explicit bounded local query returns current-host evidence only when
  genuinely available; a closed/unavailable loopback yields the honest
  unavailable state; hostile/invalid responses fail closed; deployed-host
  loopback is never labelled operator-workstation evidence; no public
  endpoint is ever substituted.

## Claim boundaries

The cockpit record must never claim: production deployment
(pre-verification), hosted operational observability (not built), SLA/SLO
attainment, statistical reliability (sparse populations remain floors),
hosted-model portability (not demonstrated), or Module 6 completion
(human browser acceptance, requirements reconciliation, release remain
open). Historical events keep their accepted classifications verbatim;
labels and limitations are carried from the accepted records, never
strengthened.
