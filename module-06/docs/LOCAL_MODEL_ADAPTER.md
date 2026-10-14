# Local Model Provider Adapter — Offline Implementation

The original offline implementation record below is historical. That adapter
was independently accepted and committed at
`b7b2d353da7dcb8cd9d60066ba4e358c471df223`. The separately authorized real probe
and the current offline repair candidate are recorded in the final section;
earlier no-provider-call statements apply to the original offline milestone.

Implementation candidate, 2026-10-14. Independent acceptance is pending.
Baseline: `feature/module-06-architecture`,
`71b08c49d7bd49ced0728658b379bdf3d41f26b5`, clean and nothing staged.
The accepted Story 1 contracts and supervised Live Runtime Enforcement remain
unchanged. ADR-004 and ADR-007 govern this additive implementation.

## Boundary and use

`local_model_gateway.LocalModelGateway` implements `ModelGateway.complete` with
the existing HTTPX dependency. It targets the nonstreaming Ollama chat protocol,
`POST /api/chat`. This protocol shape is verified against test-owned synthetic
responses only; no service documentation lookup, real-service contact or actual
provider compatibility is claimed.

Application authorization/selection/budget -> accepted process runtime ->
ModelGateway -> adapter -> HTTP transport remains the execution boundary.
The adapter has no authorization, selection, routing, budget, evidence or final
acceptance authority. It does not parse or repair role-output JSON. The parent
owns the three-role plan, at most one repair, maximum four calls, zero transport
retries, per-call/overall deadlines, forced termination and worker cleanup.

Trusted application code can supply an importable source-backed zero-argument
factory that constructs `LocalModelGateway()` in the child. No live factory is
wired into the application, console or commands in this milestone. Construction
and imports perform no provider I/O. The gateway never reads environment or
dotenv configuration. A factory creates a synthetic transport inside the child
for tests; no parent transport instance, closure or hidden authority crosses IPC.
Only the existing bounded request/reply JSON crosses the process boundary.

## Endpoint and transport

The only accepted endpoint is exactly
`http://127.0.0.1:11434/api/chat`. The constructor's endpoint argument is an
allowlist check, not endpoint choice; the HTTP call always uses the fixed
application constant. Alternate loopback names/addresses, ports and paths,
remote hosts, URLs with userinfo/credentials, queries/fragments, unsafe schemes,
control characters and URL-normalization aliases are refused before transport.
Numeric loopback avoids hostname resolution/rebinding. No remote/hosted fallback
exists. This deliberately narrow policy is not a configurable SSRF client.

The default transport is `AsyncHTTPTransport(retries=0, trust_env=False)`.
The client also has `trust_env=False`, `follow_redirects=False` and an explicit
HTTPX timeout derived from `ModelRequest.timeout_ms`. All non-200 statuses,
including every redirect, fail without reading the body or following Location.
An `asyncio.timeout` also bounds the entire cooperative operation, including
reading/closing the response. It is not a substitute for the accepted parent
supervisor: blocking code or cancellation suppression remains process-bounded
by that runtime. There is no client retry loop, worker restart or fallback.

Transport injection is trusted application/test code, never caller/model data.
An injected transport must obey the same one-attempt/lifecycle contract; it is
not an arbitrary-code sandbox. Tests use only HTTPX MockTransport and test-owned
streams. No sockets to a provider are opened.

## Translation and untrusted responses

The adapter revalidates exact `ModelRequest` instances and refuses undeclared
state and non-`ollama` provider identity. It sends only:

- the exact application-selected model name;
- one user message containing the complete application-authored role/task prompt;
- `stream: false`;
- `options.num_predict` from the application's output-token bound.

No authorization, budget object, evidence, credentials or unrelated metadata is
sent. Headers are HTTPX protocol defaults plus `Accept-Encoding: identity`; there
is no caller-header interface, proxy/environment configuration or logging of
prompts/responses in the adapter. The role-specific schema/task context already
resides in the accepted runtime prompt; the adapter neither rewrites it nor
creates its own system instructions, role schema, tools or repair request.

Successful responses must be uncompressed `application/json` (optional media
type parameters accepted). Raw bytes are accumulated only up to
`6 * request.max_reply_bytes + 4096`: six accounts for JSON escapes, and 4096
bounds envelope overhead. Reading stops on the chunk that would exceed that
bound; the response is closed. Actual content is independently bounded by the
request's UTF-8 byte limit, before constructing and checking `ModelReply`.
The maximum wire bound is 100,096 bytes, derived from the accepted 16,000-byte
content ceiling. Oversized wire/content produces `output_too_large`.

UTF-8/JSON decoding, duplicate keys, non-JSON numeric constants, deep malformed
structures, incomplete envelopes, missing/blank/nonstring content, wrong message
role and invalid Unicode fail closed. `done` must be exactly true; `model` must
exactly equal the selected name. No `:latest` normalization or other alias is
invented. An untagged name that a real service normalizes will be refused until
an explicitly selected exact identity is demonstrated in a later probe.

Top-level fields are limited to model, created_at, message, done, done_reason,
total_duration, load_duration, prompt_eval_count, prompt_eval_duration,
eval_count and eval_duration. Message fields must be exactly role/content; tool
calls, thinking/extra content and unknown fields are refused rather than granted
authority or silently forwarded. Known unused timing/completion metadata is
untrusted, bounded by the envelope and discarded, never evidence. This narrow
profile may refuse otherwise valid real-service variants; compatibility remains
unverified. The returned reply has the selected identity, text and validated
representable usage only. Model text remains untrusted role-output data.

`prompt_eval_count`/`eval_count` map independently to input/output tokens only
for exact integers in 0..1,000,000, then pass `ModelUsage` validation. Booleans,
negative/oversized counts, strings, floats, objects and missing counts remain
unavailable. No token estimates, money, latency or provider metadata are invented.

## Failures and adversarial verification

Connection/protocol failures map to `connection_failed`; socket/total timeout
to `timed_out`; 401/403/429 to the existing authentication/authorization/rate
categories; 5xx to `provider_service_failed`. Redirects, other statuses, invalid
endpoint/provider/model/envelope and other provider exceptions map to
`unexpected_provider_failure`. Envelope errors are not `malformed_output`, so
they cannot request role repair. Cancellation propagates for parent cleanup.

The public failure contains a closed category and fixed application message.
Raw body, prompt, arbitrary header, exception text, synthetic canary and internal
transport metadata are never retained in its message/args/attributes/cause or
context. Last-resort exception translation exists at the real provider boundary;
it always fails and never swallows a failure into success or retry. Caller
exception context is cleared as well.

87 focused tests cover exact request/body/header/timeout construction; identity;
17 refused endpoint forms; connection/socket timeout/other exception canaries;
status/redirect refusal; malformed/hostile JSON and shapes; raw/UTF-8 size limits;
stream stop/close; faithful or unavailable usage; role text remaining data;
unchecked request refusal; total timeout/cancellation; explicit no-retry/no-env
transport configuration; maximum JSON escaping; discarded metadata; and caller
exception context sanitization, including invalid-endpoint construction.

Four integration cases execute the actual adapter, native LangGraph and accepted
child supervisor using only synthetic transport: happy path (3 calls), repair
(4 calls), persistent malformed role output (2 calls then failure), and connection
failure (1 call). Tests verify exact selected identity, usage aggregation, minimal
child environment, one distinct worker PID, no fifth call/retry/restart and
completed process wait/closed stdin. Application evidence remains owned by the
runtime; these test outcomes are offline evidence even though they exercise the
contract for future local inference.

Self-review repaired a raw library-specific exception escape by translating all
ordinary provider-boundary exceptions to a closed failure, preserving cancellation
and removing caller context from call failures and endpoint construction. No
architecture or accepted runtime change was
needed. A new test harness initially assumed `LiveFailure` had the success-only
`transport_retries` field; it was corrected to assert success accounting and
actual failure-side call counts. No accepted tests or limits were altered.

Verification launcher notes: sandboxed Windows asyncio stalled in its loopback
socketpair before executing tests. Guarded tests ran outside that restriction.
The first adapter integration run exceeded its unchanged 15-second deadline;
unchanged runtime control tests passed, and the adapter cases passed on rerun
without changing production code or deadlines for that timing issue. An initial
full suite stopped in an unchanged Streamlit test because the stripped launcher
omitted a home directory; a test-owned noncredential home was supplied and the
fail-fast sequence restarted. A subsequent run was deliberately interrupted to
include the final constructor-context repair before restarting the gates. The
next run blocked ChromaDB's dependency-level `dotenv_values` attempt before any
real `.env` read (that API does not honor the load-dotenv disable flag). The
launcher was corrected to return empty configuration for real dotenv paths while
preserving test-owned fixture paths, and gates restarted against the unchanged
candidate. Windows AppData resolution then required creating test-owned Local
and Roaming directories in that synthetic home; the unchanged CrewAI control
test passed and the full fail-fast sequence restarted. All full
gates below run with a fixed noncredential environment, real dotenv read guards,
external/provider socket guards and disabled tracing. Dependency synchronization
is disabled. These harness/environment failures are recorded, not acceptance.
After Module 6 passed, the first root run stopped at 545 passed because an
unchanged Module 3 provenance test could not find Git in the stripped PATH. A
fixed PATH for the existing virtual environment, installed Git and Windows
system tools was supplied, and the complete root gate rerun against the unchanged
candidate. No test, baseline or deadline was weakened for these launcher repairs.
The next root run stopped at 3,763 passed, 6 skipped and the three existing
ChromaDB warnings in 332.92 s: the unchanged runtime stalled-parent `delayed`
case missed its two-second startup/dispatch budget before synchronized dispatch.
That case does not use the adapter, passed in the complete Module 6 run, and
passed unchanged in isolation (12.47 s). The complete root gate was rerun without
altering candidate code, accepted runtime, assertions or deadlines. This is
recorded as a timing/environment failure rather than concealed as a source repair.

## Quality gates

Accepted baseline: Module 6 1,842 passed; root 3,957 passed, 6 skipped. The final
candidate adds 87 tests. The standalone focused run passed 86 before the final
constructor-context case; the complete Module 6 run verifies all 87.

| Gate | Result |
| --- | --- |
| `uv run --offline --no-sync ruff check module-06` | PASS |
| Complete Module 6 pytest, guarded offline launcher | 1,929 passed in 283.69 s |
| Complete root pytest, same guarded launcher | 4,044 passed, 6 skipped, 3 existing ChromaDB warnings in 347.08 s |
| compileall: Module 6 source/tests/app/four command paths | PASS |

The launcher uses the existing `.venv` interpreter, with pytest plugin autoload
disabled and the installed asyncio plugin explicitly loaded. No dependency is
installed, updated or synchronized. It is temporary verification infrastructure
and is removed with its test-owned files before delivery.

Final provenance: branch/HEAD remain the baseline. Exactly six scoped Module 6
files differ: new `local_model_gateway.py`, `test_local_model_gateway.py`,
`local_provider_cases.py` and this document; updated `README.md` and
`PROJECT_STATUS.md`. Temporary verification files are removed. Nothing is
staged, committed or pushed; dependency files and all accepted source/test files
are unchanged. `git diff --check` passes. The authoritative source-to-evidence
matrix has exactly 26 requirement rows, each still Planned.

## Evidence and Definition of Done

IMPLEMENTED / OFFLINE VERIFIED: adapter, fixed endpoint policy, request/response
translation, failure sanitization and accepted process-runtime compatibility.
Independent acceptance is not performed by the implementer. All M6-001..M6-026
source matrix statuses remain Planned; no requirement governance is changed.

| SOP gate | Scoped assessment |
| --- | --- |
| Requirements | Offline adapter contract implemented; accepted requirements intact |
| Product Experience | Narrow documented application API; live UI deferred |
| Real Functionality | HTTP translation and real child runtime exercised synthetically |
| Reliability | Bounded read/timeouts, closed failures, no retries; parent supervision retained |
| Security | Fixed local destination, no redirects/proxies, identity checks and canary tests |
| Cost | No paid operations or new budget authority; application bounds consumed |
| Evidence | Offline implementer verification only; acceptance pending |
| Deployment | No production deployment readiness claim |

NOT YET VERIFIED: actual Ollama service compatibility, installed model
compatibility, actual inference, model quality, live Streamlit model execution,
live-model LangSmith evidence, hosted-provider support and production deployment
readiness. No real credentials/environment credential presence or `.env` were
inspected; no Ollama/model/provider/LangSmith/external request was made. No
dependency, other-module, staging, commit or push change is part of this work.

Before a local-model compatibility probe: obtain independent review/acceptance
of this candidate, then explicit human authorization for a bounded probe with
an exact application-selected model identity, fixed endpoint, stated call/output/
deadline bounds and a source-backed zero-argument child factory. Define the
expected protocol/identity/usage checks and failure/evidence handling before
calling. Record actual results separately from synthetic evidence; any required
material endpoint/protocol/security architecture change returns to human review.
Model quality, live UI/observation and deployment remain separate later work.
This milestone does not authorize or begin that probe.

## Bounded real-compatibility repair — offline candidate

Baseline: `feature/module-06-architecture`,
`b7b2d353da7dcb8cd9d60066ba4e358c471df223`, commit
`feat: add offline local model gateway`; starting worktree clean, nothing staged.
This is implementation/repair verification, not independent acceptance.

### Real provider evidence preceding this repair

A separately authorized probe made exactly one real local inference at
`http://127.0.0.1:11434/api/chat` using the already-installed exact tag
`qwen2.5-coder:7b`. HTTP 200, nonstreaming, no retry, repair, redirect or fallback;
requested and returned identities matched. The response was 343 raw bytes,
with nonblank string content of 11 UTF-8 bytes, message fields exactly
`role`/`content`, and `done` exactly true.

Observed top-level fields were `created_at`, `done`, `done_reason`, `eval_count`,
`eval_duration`, `load_duration`, `message`, `model`, `prompt_eval_cached_count`,
`prompt_eval_count`, `prompt_eval_duration` and `total_duration`.
`prompt_eval_cached_count` was an integer; its numeric value was not retained.
Representable usage fields were `prompt_eval_count = 40` and `eval_count = 6`.
The accepted pre-repair adapter rejected the extra cached-count field, giving
verdict **INCOMPATIBLE** with `unexpected_provider_failure`.

This is **REAL LOCAL PROVIDER COMPATIBILITY EVIDENCE** establishing the mismatch.
It is not evidence that the repaired adapter works against another real response.
No generated content or raw provider body is retained in this record.

### Narrow repair and offline evidence

Only `prompt_eval_cached_count` is added to the known top-level allowlist.
When present, it must satisfy the existing `_usage_count` representation:
exact `int`, not `bool`, in `0..MAX_TOKEN_COUNT` (0..1,000,000). The adapter
validates it, then removes it from the parsed envelope before reply construction;
invalid representations fail through the existing sanitized provider boundary.
Absence remains valid. Even valid values are explicitly discarded, never added
to `ModelReply`, application evidence, usage, cost or any policy decision.
No inferred relationship to prompt tokens is introduced: cached values cannot
replace, add to, subtract from, or fill unavailable `prompt_eval_count`.

All other unknown fields continue to be rejected. Message fields remain exactly
`role`/`content`; thinking, tool calls, images and attacker-named fields are
rejected at either level, including arbitrary siblings next to the cached count.
Exact identity, duplicate-key rejection, endpoint/redirect refusal, bounded
pre-parse reads, content bounds, sanitized failures and zero retries are unchanged.
No contract, authorization, budget, repair, evidence-classification or supervised
runtime implementation changes.

A synthetic fixture reproduces the observed field names/types and known model
identity/usage. Its content, timestamp, completion reason, durations and cached
count are explicitly synthetic placeholders, not copied provider output.
36 added cases cover optional absence; zero, positive and maximum count; negative,
boolean, float, string, null, oversized, object and list values; duplicate keys;
strict top/message sibling rejection; model/message invariants; unavailable usage;
raw/content bounds; and three additional real child-runtime scenarios.
All original 87 adapter cases and existing runtime assertions are preserved.

The extended synthetic child fixture exercises cached-count success (3 calls),
role repair (4 calls), and invalid cached metadata (1 call, no repair). Existing
usage totals remain derived solely from input/output token counts even with a
synthetic cached value of 100. Existing assertions verify one child, minimal
environment, no fifth call, zero success-side retry accounting, completed wait
and closed stdin. The underlying parent runtime remains unchanged.

Focused offline verification: **123 passed in 18.16 s**. Ruff passes after
correcting a single long fixture line. Full fail-fast results follow execution:

| Gate | Result |
| --- | --- |
| `uv run --offline --no-sync ruff check module-06` | PASS |
| Complete Module 6 pytest | 1,965 passed in 358.05 s |
| Complete root pytest | 4,080 passed, 6 skipped, 3 existing ChromaDB warnings in 424.15 s |
| compileall: source/tests/app/four command paths | PASS |

Gates use the existing interpreter/dependencies, an explicit noncredential
environment with test-owned home/AppData/temp paths and fixed executable PATH,
disabled dotenv/tracing, guarded real dotenv reads and blocked external/provider
connections (including port 11434). Only synthetic/test-owned loopback and IPC
are allowed. Temporary verification infrastructure is removed before delivery.
No real Ollama, model, provider, LangSmith or external request occurs in this
repair task; no credential or real credential-variable presence/.env inspection,
dependency change, staging, commit or push is authorized or performed.

The first full Module 6 gate stopped at 206 passed in 95.98 s: the unchanged
CrewAI console demonstration returned its existing timeout outcome. Causality
checks found no repaired gateway reference in the console/CrewAI execution path;
those source/test files were unchanged. The exact case passed unchanged in
isolation (17.85 s), then the full fail-fast sequence restarted at Ruff against
the unchanged candidate. This timing/environment observation is recorded, not
silently attributed to noise or repaired by changing accepted limits/assertions.
During final source review the full rerun was deliberately interrupted to make
the validation/discard order literal: validate the cached value first, then
remove the field. This preserves the already-tested representation and public
behavior; gates restarted from Ruff against the final candidate.
The first root gate stopped at 3,765 passed, 6 skipped and the three existing
ChromaDB warnings in 481.15 s. The unchanged cleanup `happy` case exhausted its
50 ms per-call bound after one call instead of reaching the expected three;
it also failed in isolation (4.74 s). Its unchanged child fixture directly
returns ModelReply and does not import or call the repaired adapter. This was
not automatically dismissed as suite-load noise. Moving test-owned fixture
storage from the OneDrive workspace to a uniquely named OS-temp directory made
that exact case pass unchanged (3.20 s), supporting a filesystem/timing
contribution. The complete root gate was rerun with that launcher-only location
change against the unchanged candidate. No test, deadline, runtime or security
guard was weakened; no real provider request was used to diagnose the failure.
The next root run passed that cleanup case and the adapter tests, then stopped
at 3,901 passed, 6 skipped and the same three warnings in 411.04 s: an unchanged
CrewAI observability comparison timed out in `execution.py`/`adapters.py` while
awaiting its separate CrewAI subprocess. That path does not use the repaired
Ollama adapter; its source/tests are unchanged and it passed in the complete
Module 6 gate. The exact case passed unchanged in isolation (39.54 s). The
complete root suite was rerun again against the unchanged candidate and guards,
without skipping, extending, deleting or weakening any test or deadline.

Self-review checks the narrow allowlist change, strict integer representation,
duplicate keys, discarded metadata/unchanged usage and authority, identity,
sanitization, endpoint/redirect/read bounds, retries and process-runtime invariants.
The SOP assessment remains scoped: requirements fidelity is preserved; the
documented adapter API remains the product surface; real-provider evidence is
historical and the repair is synthetic; reliability/security/cost controls are
unchanged; evidence is implementer verification pending independent acceptance;
deployment readiness is not established. All 26 source statuses remain Planned.

**NOT YET VERIFIED:** repaired adapter against a second real Ollama response,
full live multi-agent workflow, model quality, live Streamlit inference,
live-model LangSmith evidence, hosted-provider compatibility or production
deployment readiness. Required next steps are fresh independent acceptance of
this repair and separate explicit authorization for a bounded post-repair real
compatibility probe. No such probe is performed or independently authorized here.

Final repair provenance: exactly four modified Module 6 files (the adapter,
its test file, child fixture and this document); branch/HEAD unchanged; nothing
staged, committed or pushed. Temporary launcher and both task-owned fixture
directories are removed. Accepted contracts/runtime code and dependency files
are unchanged. `git diff --check` passes; the authoritative source-to-evidence
matrix still has exactly 26 rows, all Planned. Final self-review found no
remaining defect within this repair scope; independent acceptance remains pending.
