# Story 9 — LangFuse monitoring and failure analysis

Status: implemented for independent human review. Stories 1–8 are accepted.
Authority: SOURCE_REQUIREMENTS.md, frozen ARCHITECTURE.md and its approved
Story 5 amendment, then accepted evidence contracts. No authority conflict or
new architecture decision was required. Story 10/11/12 work is not included.

## Requirement evidence

| Requirement | Implementation and evidence |
| --- | --- |
| M4-OBS-02 | `observability/langfuse_adapter.py`: workflow and measured-stage OTLP spans; safe numeric latency/evaluation summaries; real SDK serialization captured offline. |
| M4-TOOL-03 | Installed LangFuse 4.15.4 public `LangfuseAPI.opentelemetry.export_traces`, its real `OpentelemetryClient` and `RawOpentelemetryClient` execute; spies delegate to both original implementations. |
| M4-OBS-04 | `observability/failure_analysis.py`: immutable validated stage/category facts and deterministic domain-error mapping; fatality and retained-answer usability are derived. |

## Genuine integration and dependency decision

The manifest, installed graph and lockfile were inspected before adding anything.
LangFuse was absent. The smallest direct addition is `langfuse==4.15.4`, the
current stable version identified on [PyPI](https://pypi.org/project/langfuse/4.15.4/).
Normal `uv add` resolution added these packages only:

- LangFuse 4.15.4 (direct).
- backoff 2.2.1.
- opentelemetry-exporter-http-transport 0.66b0.
- opentelemetry-exporter-otlp-proto-http 1.45.0.
- wrapt 2.5.0.

Comparing the pre-Story-9 lock snapshot to the resulting lock found zero existing
version changes and zero removals. Accepted LangSmith remains 0.14.3, RAGAS
remains 0.3.1, and existing OpenTelemetry remains 1.45.0. The root project was
rebuilt normally. No dependency was downgraded or forced incompatible.

The installed SDK's public generated API exposes the native OTLP JSON monitoring
endpoint. This is a genuine installed SDK/API boundary, not a home-grown monitor
named LangFuse. Its SDK model objects, serializer, HTTP client, authentication,
response parser and public/raw export implementations all execute. Application
code constructs safe OTLP evidence; the SDK serializes the request. Only HTTP
transport and response are fixtures. No SDK behavior is replaced or patched.
See the [official API reference](https://python.reference.langfuse.com/langfuse/api/opentelemetry/client.html).

The synchronous API path avoids the high-level tracing client's ambient settings,
global tracing resources, singleton clients and background exporters. It also
avoids the SDK's deprecated legacy batch ingestion endpoint. This choice follows
the allowed controlled client boundary and does not claim high-level decorator,
observation context-manager, or OpenTelemetry exporter execution.

## Offline boundary and evidence semantics

`LangFuseMonitor` accepts only the exact `OfflineMonitoringTransport` type.
An explicit HTTPX client uses `trust_env=False`, no redirects, a one-second timeout,
fixed fixture Basic authentication and a fixed invalid HTTPS base URL. The
transport permits only POST to the exact `/api/public/otel/v1/traces` URL.
Application-owned request options disable retries. SDK/OTEL environment settings,
proxy settings, caller metadata and response content cannot redirect monitoring,
select credentials, enable tracing or grant retries. Importing either new module
does not load LangFuse/LangSmith or initialize a provider.

Each call sends one workflow span and ordered measured-stage children in one
OTLP request, including LangFuse observation type attributes, its native
`langfuse.observation.metadata.*` summary namespace and the v4 ingestion
header. IDs are fresh random SDK-compatible hex identifiers. A fixed synthetic
epoch anchor and durations provide inspectable fixture timestamps. Numeric
structure is deterministic; generated IDs vary. Durations outside the OTLP
timestamp range are rejected before SDK invocation. These are not production
wall-clock traces or production latency measurements.

`success` means the offline SDK export completed, independently of workflow
success. The SDK's response is discarded and never controls the workflow.
Evidence is always `deterministic_offline`; `remote_delivery_verified` is always
false. No live verification was performed, and no live path or credential loader
was added. Offline acceptance does not prove remote ingestion, SaaS availability,
remote validation of these spans, or real evaluation quality.

## Failure taxonomy and semantics

Application code supplies the closed `Stage` enum at the catch boundary. Neither
stage names in timing evidence nor raw exceptions determine stage authority.

| Category | Deterministic source |
| --- | --- |
| retrieval | M4 BM25, fusion, cache and dynamic-retrieval domain errors; M3 retrieval errors |
| reranking | M4 reranking domain errors |
| context_filtering | M4 context-filter domain errors |
| evaluation | M4 evaluation domain errors |
| generation_integration | M3 generation and LangChain integration domain errors |
| observability | New monitoring integration error or accepted LangSmith trace integration error |
| timeout | Python timeout or HTTPX timeout at any application-selected stage |
| other | Unknown exception type; no text parsing or guesses |

Known domain category/stage mismatches are rejected. Fatality derives from stage:
observability is nonfatal; other failed stages stop that workflow. An answer is
usable only when it already exists and the failed stage is optional observability.
`monitor(..., result_available=True)` is an explicit application fact, not inferred
from the presence of a latency report; the default is false. A supplied workflow
failure and a monitoring failure are separate facts. Successful monitoring of a
fatal workflow failure is possible and truthfully labeled.

Sanitized evidence consists of enum stage/category, boolean result availability,
derived fatality and usability, plus numeric/structural workflow summaries.
Raw exception messages, stack traces and arbitrary instructions are not inspected
to classify failure. Exceptions are not stored by failure-analysis objects.
SDK failures return unsuccessful nonfatal monitoring evidence with a fixed warning
and fixed actionable `MonitoringIntegrationError` chained to the actual SDK cause.
The cause is deliberately local debug evidence and may contain sensitive details;
it must not be rendered, logged or serialized. No traceback is logged.

## Security and provenance

Before the SDK boundary, metadata/tags must have bounded primitive shapes and
are then excluded entirely, even if they contain endpoint, credential, execution,
filesystem, enablement or retry instructions. Prompts, answers, references, chunk
content, chunk identifiers, source paths, case/model identifiers, judge output,
original stage names and raw error text are excluded. Only fixed names, new
application identifiers, numeric scores/durations, sequence numbers, fixed
evidence labels and safe failure facts are emitted.

Original Story 6 latency and Story 7 evaluation objects, case, chunks and provenance
stay local by identity and are hidden from monitoring evidence representations.
The adapter does not mutate them, reconstruct provenance or replace upstream
results. Story 8 source/tests/contracts are unchanged. Telemetry remains evidence,
with no imports, execution, filesystem operations or privileged decisions derived
from external content. No generalized shared observability abstraction was added.

## Runnable demonstration

Run `uv run python module-04/examples/langfuse_monitoring_demo.py`.
It explains what/how/expected/actual/why and shows SDK 4.15.4, `success=True`, one
request, two spans, 0.08 fixture seconds and a fatal reranking failure analysis.
It labels the evidence offline, denies a remote-delivery claim and explicitly
leaves Story 11 dashboard/UI as future work. The executable test blocks outbound
sockets while running this same script.

## Tests and bounded repairs

74 new deterministic cases cover public/raw genuine SDK invocation and serialized
OTLP structure, child relationships, fixed credentials/headers, numeric propagation,
evaluation/chunk identity, sensitive content exclusion before SDK invocation,
malformed evidence/metadata/tags, hostile annotations and ambient SDK/OTEL/proxy
settings, socket isolation, sealed transport and destination authority, zero
retries, SDK timeout/connection/unexpected failures, HTTP error responses, untrusted
success responses, sanitized logging/repr, exception chaining, failure mappings,
timeout across stages, fatality/usability, enum validation and immutability,
timestamp bounds, import isolation and the executable demo.

Bounded repairs affected only new Story 9 files: safe Ruff import cleanup and
formatting, and correcting the new evaluation test fixture to use the accepted
M3 `source_key`, `FixedConfig(size=...)`, `ChunkingResult.chunks` and explicit replay
judge contract. Final SDK source inspection also aligned summary attribute keys
with LangFuse's native observation metadata namespace; its exact serialized keys
are tested. The complete sequence was restarted after this bounded adjustment.
No accepted tests or behavior were altered. A sandbox PyPI socket
denial was resolved by the approved dependency-install escalation. Initial focused
tests also reported sandbox denial writing the existing pytest cache; the formal
full-suite gate uses filesystem access for existing test temp/cache directories.
No unsafe Ruff fixes were used.

## Quality gates

Final complete fail-fast sequence — October 5, 2026:

1. `uv run ruff check .` — exit 0, all checks passed.
2. `uv run pytest` — exit 0, **1654 passed / 0 failed**, 3 existing ChromaDB
   deprecation warnings, 42.43 seconds. Accepted baseline 1580 + 74 Story 9 cases.
3. `uv run python -m compileall module-01 module-02 module-03 module-04` —
   exit 0, compilation successful.
4. `git diff --check` — exit 0; existing LF-to-CRLF normalization notices only.

Module 4 was already untracked at task start. Ordinary Git diff checking does
not inspect its new files. Supplemental `git diff --no-index --check` against
`NUL` checks each of the five new Story 9 files separately. Those comparisons
return status 1 because each file differs from `NUL`; they emitted only line-ending
normalization notices, with no whitespace error diagnostics. The runnable demo
also completed successfully with SDK 4.15.4,
one request and two spans; remote delivery remained unverified.

Story 9 added five Module 4 files and changed only the root manifest/lockfile
for its dependency addition. All earlier user changes remain in place.

## Limitations and training observations

No live-service delivery or remote semantic acceptance is verified. The fixed
offline transport has no sockets; the one-second client timeout does not hard-cancel
an arbitrarily blocking custom transport. Result usability is a caller-provided
application fact; Story 10 must supply it at the actual catch boundary. This story
provides the analysis/monitoring capability, not final orchestration or a UI.

- **Agent policy:** verify installed public SDK semantics and dependency impact;
  label SDK completion separately from workflow success and remote delivery.
- **Reusable provider-neutral skill:** use safe application-owned facts and minimal
  summaries, preserve original evidence identity, inject below real serialization.
- **Deterministic automation:** test genuine methods with delegating spies,
  hostile ambient configuration, outbound socket guards and executable demos;
  compare pre/post lock package versions and run fail-fast gates.
- **Human authority:** independent Story 9 acceptance remains outstanding.
  No source reinterpretation, frozen architecture change or new authority decision
  was required. Live verification and later stories need their own explicit scope.

No commits, merges, tags, releases, deployments or Story 10 work were performed.
