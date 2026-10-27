# Opt-In LangSmith Trace Delivery

> **Status note (S7).** Dated historical record. Where it says "Planned", "candidate" or "pending", that was true when written; current requirement status is in [TRACEABILITY.md](TRACEABILITY.md) and engineering status in [PROJECT_STATUS.md](PROJECT_STATUS.md). The body below is unchanged.

Verified starting branch: `feature/module-06-architecture`; clean HEAD
`9029e6eddc3f6c8f047a33415ea2f0de322fdb5b`, subject
`feat: expose local scaling benchmark in operations console`. A bounded real
LangSmith trace verification, outbound network access to LangSmith for it, and
use of the human's LangSmith credential from the local environment were
explicitly human-authorized on 2026-10-13. Model or provider inference, other
external calls, hosted deployment and any dependency change were not.

## Status

**Current-path external delivery verification independently accepted on
2026-10-22** (see
[Current-path delivery verification](#current-path-delivery-verification-2026-10-22):
one human-authorized, deterministic sanitized-trace delivery on this same
committed path, reviewed and accepted). The first live delivery was confirmed
on 2026-10-13: on the fifth human-authorized attempt LangSmith accepted the
batch (HTTP 202, four runs) and returned the delivered root run. The four
earlier attempts failed for one reason that had nothing to do with the
request: the credential variable held a single pasted control character
instead of the key. Neither the endpoint nor the payload was at fault, and the
batch path is not what fixed it. After the success, the adapter was hardened
offline to refuse a malformed credential locally before any request. M6-014
is unchanged and remains Planned until the separate status transition; no
model-backed LangSmith correlation is claimed or closed by either event. See
[Live verification](#live-verification).

## Purpose and boundaries

Before this story no code path could send anything to LangSmith: the accepted
`LocalLangSmith` adapter builds real SDK run trees and discards them. This story
adds the smallest path that can prove the fourth named tool was actually used:

```text
accepted deterministic workflow -> application RunTrace (already finished)
    -> LangSmithTraceDelivery -> Client.batch_ingest_runs
    -> POST /runs/batch (once) -> accepted -> root run read back
```

Nothing here runs by default. Workflows, the console, the benchmark, the
telemetry command and every test stay offline. `LocalLangSmith`, `Observability`,
`execute_observed_workflow`, all runtime source and the console are unchanged.
No dependency or lockfile change was needed: `langsmith` 0.14.3 was already
locked.

Evidence classes stay distinct:

| Class | What it is | Status |
| --- | --- | --- |
| Deterministic offline tests | Real SDK client and serialization with the network replaced in memory | Implemented and gated |
| Offline preview | The exact runs of the batch, printed without network or credential | Verified locally |
| Loopback transport check | The real HTTP stack against a local stand-in, with a dummy key | Verified locally, not part of pytest |
| Live LangSmith delivery | One real trace accepted and read back | **Achieved once, 2026-10-13, run by the human** |
| Current-path external delivery verification | One deterministic sanitized trace delivered through this committed path; independent Reviewer accepted | **Accepted, 2026-10-22** |
| Live-model live-run delivery | One real model-backed workflow trace projected (4 runs, trace UUID preserved) and delivered through the committed live-family delivery; `unverified_write` only; no service-read confirmation exists | **Recorded once, 2026-10-22** (Run 5; authority-consumption status operator-attested and not independently confirmed — see [Canonical live workflow](CANONICAL_LIVE_WORKFLOW.md#run-5-live-model-current-path-langsmith-delivery-verification)) |
| Model or LLM inference | Any model-backed execution | Recorded for local live runs (Run 4 NORMAL verification; Run 5 delivery verification); hosted/paid model execution remains not implemented and never authorized |

## SDK contract used

Derived from the installed `langsmith` 0.14.3 source and offline captures of its
requests, not from memory or external documentation.

- `Client.batch_ingest_runs(create=[...])` is a public, documented method. It
  takes run dictionaries that must carry `trace_id` and `dotted_order`,
  serializes them itself, and with batching off sends one synchronous
  `POST {api_url}/runs/batch` with the body `{"post": [...]}`.
- Its serializer removes `attachments` from every run, so that key never
  travels in a JSON batch.
- On a failed write the SDK does not raise. It retries by itself (up to three
  attempts, sleeping in between and honouring a `retry-after` header on 429)
  and logs a warning that includes the exception text, which can quote the
  reply. On a failed read it logs the exception text at debug level.
- `Client.request_with_retries("GET", "/runs/{id}")` reads a run back, one
  attempt by default.
- An explicit `api_url` overrides `LANGSMITH_ENDPOINT`; an explicit `api_key`
  disables profile-file authentication; `omit_traced_runtime_info` stops the
  SDK adding platform, package and `LANGCHAIN_*` environment metadata.
- The SDK source names only `https://api.smith.langchain.com` as the hosted
  default. No other origin was assumed.

## Design

`langsmith_delivery.py` adds `LangSmithDeliveryConfig`, `LangSmithTraceDelivery`,
`DeliveryReceipt`, `TraceDeliveryError`, `checked_batch`, `checked_body`,
`status_category` and `credential_configured`. `run_langsmith.py` is the
operator command.

**Selection is explicit.** Delivery exists only when trusted operator code
builds a `LangSmithDeliveryConfig` with the required `mode="langsmith-live"` (no
default) and calls `deliver`. A mapping, string, subclass or `model_construct`
forgery is refused. No environment variable, credential, workflow request field
or runtime output can enable delivery, choose a destination or path, or add to
the payload. The configuration has no endpoint, path, project or key field.

**Delivery happens after the workflow.** The adapter takes a finished
application `RunTrace`. It is not an observer adapter and is never called from
workflow execution, so a delivery fault cannot change, delay or fail a workflow
result. Domain and workflow code do not import it, and it follows the
repository's lazy SDK boundary: no module in the package imports `langsmith`
statically.

**The SDK serializes; the application chooses the fields.** A real SDK run tree
supplies identifiers, trace linkage and dotted order. The adapter then takes
only named fields from it into plain dictionaries and hands those to
`Client.batch_ingest_runs`. The wire format is the SDK's; nothing the SDK or
the environment attaches to a run tree can travel with the batch.

**The client is pinned.** Explicit origin and key, no background thread,
timeouts of 5 s connect and 10 s read, hidden inputs and outputs, sampling fixed
at 1.0, no runtime metadata, and a supplied empty service-info object so the SDK
makes no discovery call.

**The session owns every external effect.** A `requests.Session` subclass with
`trust_env=False` and redirects disabled permits exactly:

- one `POST https://api.smith.langchain.com/runs/batch`;
- after an accepted write, `GET` of the one delivered root run.

Every other method, origin, scheme or path is refused before anything is sent,
including the former `POST /runs`, `/runs/multipart`, `/info` and `/sessions`.
At most 7 requests and 60 s overall.

**A request means a request attempt.** The session keeps one counter, advanced
immediately before a request is handed to the transport. A request refused by
the session is not counted, because nothing was sent. A request that fails
before any response arrives is counted, because it was sent. The 7-request
bound and the receipt's `requests` field both read that one counter, so
`requests` is always the one write plus `read_attempts`. HTTP statuses of the
responses actually received are recorded separately and are never used as a
request count; there can be fewer of them than requests.

**No retry, enforced at the transport.** The session refuses a second write
outright. It also never shows the SDK a failed write: it records the real
outcome itself, as a status integer or an exception category, and hands the SDK
an empty accepted reply. The SDK therefore has nothing to retry and never
sleeps on a remote `retry-after` value. Each `deliver` call spends one unit of a
lifetime budget (default 1, maximum 3) whether it succeeds or fails; a missing
credential is refused before the budget is touched.

**Reply bodies of failures are not read, with one bounded exception.** Requests
are streamed. For a write, only the status code is taken and the reply is
closed; the exception is a 400 to 499 reply, of which at most 2048 bytes are
read once and reduced immediately to a closed classification (see
[Bounded inspection of a failed reply](#bounded-inspection-of-a-failed-reply)).
For a read that is not a 200, the reply is closed unread and the SDK receives
an empty reply with the same status. Only the body of a successful read of our
own run is read in full, and it is treated as untrusted.

**SDK logging is suppressed for the delivery.** A filter is attached to the
`langsmith.client` logger for the duration of one delivery and removed
afterwards. It covers the warning the SDK writes for a failed batch and the
debug record it writes for a failed read, both of which carry exception text.
No other logger is touched, and the filter is gone once `deliver` returns or
raises.

**The outgoing batch is revalidated at the wire.** `checked_batch` runs inside
the session on the bytes the SDK produced. It requires the envelope to be
exactly `{"post": [...]}` with one to four runs, one root first and only its
children after it, distinct identifiers, and every run inside the closed shape
enforced by `checked_body`: no field outside a closed set, empty inputs,
outputs and events, the fixed project, a name and metadata from closed
vocabularies, and at most 8192 bytes in total.

## Credential handling

- The only source is the `LANGSMITH_API_KEY` environment variable of the running
  process. The legacy `LANGCHAIN_API_KEY` name is deliberately not read.
- It is read inside `deliver`, passed to the SDK client and dropped with it. It
  is not stored on the adapter, written to disk, logged, printed, placed in an
  exception, a receipt or a URL, and is not accepted as a command-line argument.
- If it is unset or blank, `deliver` fails closed with a message that names the
  variable and sends nothing.
- No `.env` file is read by this code.

### Format validation before any request

Added after the live failures were traced to a credential variable that held the
single control character U+0016. The HTTP stack sends header text unchecked, so
the adapter now checks it first.

Order inside `deliver`, all before a session, an SDK client or a request exists:

1. The delivery budget is checked.
2. The variable is read. If it is unset or only whitespace, delivery is refused
   with `LANGSMITH_API_KEY is not set in this process. Nothing was sent.`
3. The text is normalized exactly as the installed SDK normalizes a key:
   surrounding whitespace is stripped, then surrounding double quotes, then
   surrounding single quotes, repeated until nothing changes. The result is the
   text the SDK would place in the header, so what is validated is what would
   be sent.
4. The normalized text must have more than one character and consist only of
   visible ASCII, U+0021 to U+007E. Otherwise delivery is refused with
   `LANGSMITH_API_KEY has an invalid format. Nothing was sent.`
5. Only then is the attempt counted and the request path entered, with the
   normalized text.

A refused credential spends no budget. The message is fixed: it carries no
content, fragment, length, position or character code. The validator performs
no input or output and keeps nothing. `credential_configured()` and
`credential_usable()` return booleans only, and the command prints one of
`not set`, `set (format valid)` or `set (format invalid)`.

A credential that looks valid authorizes nothing by itself. Delivery still
requires the explicit mode in trusted code and the explicit `--deliver` flag.
The check says nothing about whether LangSmith will accept the key; that is
still answered only by the service, as HTTP 401 or 403.

## Exact trace contents

One batch holding one root run named `module6.workflow` and one child run per
validated role (three for the sequential workflow the command uses). Every run
has:

| Field | Value |
| --- | --- |
| `session_name` (project) | `module6-verification` |
| `run_type` | `chain` |
| `inputs`, `outputs` | `{}` |
| `events` | `[]` |
| `id`, `trace_id`, `parent_run_id`, `dotted_order` | Generated by the SDK |
| `start_time`, `end_time` | Workflow start and end; child runs carry the end time |
| `error` | Absent on completion; otherwise the outcome word |
| `tags` | Root: `module6`, `deterministic`, `no-llm-inference`. Children: none |

Compared with the first design this is the same data or less: the fields are
identical except that the empty `attachments` key is no longer sent, and the
four runs travel in one request instead of four.

Metadata, closed vocabulary:

| Key | Value |
| --- | --- |
| `module` | `module-06` |
| `verification` | `deterministic_orchestration` |
| `inference` | `none` |
| `evidence_class` | `deterministic_offline_execution` |
| `runtime`, `topology`, `outcome` | Application enum values |
| `distributed` | `true` or `false` |
| `model_calls` | `0`, only when validated evidence established it |
| `workflow_id` | Application-generated random UUID |
| `observation`, `role_sequence` | Children only: `validated_completion`, 1 to 3 |

Never transmitted: instruction text, workflow output, task, trace or span
identifiers, worker PIDs, assignment identifiers, file paths, environment
contents, source code, exception text, platform or package information.

Request headers are those the SDK sets: user agent, accept, content type and the
`x-api-key` credential header. If `LANGSMITH_WORKSPACE_ID` is set the SDK also
sends it to LangSmith as `X-Tenant-Id`.

## Delivery accounting and confirmation

All runs of a trace travel in one write, so accounting is all or nothing and is
never inferred:

- write accepted (2xx): every run of the trace counts as accepted;
- write rejected or unanswered: zero runs count as accepted.

Local SDK object construction is not treated as delivery. A receipt is returned
only when LangSmith answered the write with a 2xx status. The adapter then
reads the root run back by identifier, up to six times two seconds apart, and
treats the reply as untrusted: identifier, trace, name and run type must match.
No read is made unless the write was accepted.

- `confirmation: "service_read"`: LangSmith returned the delivered run. This is
  the confirmation the story requires.
- `confirmation: "accepted_only"`: the write was accepted but the run was not
  readable in the window. `read_failure` holds the category of the last read
  attempt, with `not_found` for a run that is not yet readable. The command
  reports this as **not confirmed** and exits with status 3.

## Failure classification

A failed delivery raises `TraceDeliveryError` with a fixed message and four
structured attributes: `category`, `http_status`, `accepted_runs` and
`planned_runs`. They are built only from facts the transport observed itself:
the status code of a response, whether a request was attempted and answered,
and the type (never the text) of an exception.

| Category | Observed condition |
| --- | --- |
| `refused` | The adapter declined locally: budget spent, credential variable unset, input not an application trace, wire guard, destination pin, second write, request or time bound |
| `failed_before_send` | An exception before any request was attempted |
| `connection_failed` | The write got no response: DNS, refused or reset connection, proxy |
| `tls_failed` | The write got no response and the transport reported a TLS error |
| `timed_out` | The write got no response within the connect or read timeout |
| `authentication_rejected` | HTTP 401 |
| `authorization_rejected` | HTTP 403 |
| `request_rejected` | Any other HTTP 4xx, including 400, 404, 405, 409, 413 and 422 |
| `rate_limited` | HTTP 429 |
| `service_failed` | HTTP 5xx |
| `unexpected_response` | A status outside 2xx, 4xx and 5xx, such as a redirect |
| `unexpected_failure` | The write got no response for a reason outside the classes above |

The status code is shown as an integer, for example `(HTTP 400)`. It is a
number taken from the response line, carries no remote text and is what
separates the cases. Nothing else from a response is used: not its body,
headers or reason phrase. The public failure is raised outside the exception
handler, so no SDK or transport exception is attached as cause or context.

## Bounded inspection of a failed reply

Approved by the human on 2026-10-13 after the batch path also returned HTTP 400.
Its purpose is diagnostic classification of untrusted remote content, not
disclosure of the reply.

**When.** Only for the one pinned write, and only when its status is 400 to
499. Successful replies, redirects, 5xx replies and every read-back reply are
not inspected.

**How much.** One call that asks for at most 2048 bytes (`MAX_REPLY_BYTES`),
then the reply is closed. There is no second read, no retry and no second
request.

**What happens to the bytes.** They exist in one local variable inside the
pinned session and are reduced at once to a `ReplyHint`. They are never logged,
stored, written, returned, placed in an exception or chained to one. A fault
while reading or classifying yields the `unknown` classification.

**Decoding.** Strict UTF-8 only. If the buffer is full it may end inside a
character, so up to three trailing bytes may be dropped; nothing else is
tolerated. Content that does not decode is `unknown`. No replacement or escape
decoding is used, so no byte representation can appear in a diagnostic.

**Format classification.** Two closed values are kept:

| Field | Values | Source |
| --- | --- | --- |
| `declared` | `json`, `html`, `text`, `unknown` | The class of the content type; the header value itself is dropped |
| `observed` | `json`, `html`, `text`, `empty`, `unknown` | The bounded content |

Content that presents itself as JSON, by its content type or its first
character, and does not parse is `unknown` with no mentions.

**Mentions.** The decoded text is lower-cased and split into tokens of letters,
digits and underscores. A token counts only if it equals an entry of the closed,
source-controlled tuple `REPLY_TOKENS` exactly, so a listed word inside a longer
word does not count. The result is the sorted set of canonical names that
occurred. No count, position, value or neighbouring text is kept. `complete`
says whether fewer than 2048 bytes were available.

The 51 allowlisted names, all protocol or schema terms:

| Group | Names |
| --- | --- |
| Run fields this story transmits | `id`, `trace_id`, `parent_run_id`, `dotted_order`, `start_time`, `end_time`, `name`, `run_type`, `inputs`, `outputs`, `events`, `extra`, `metadata`, `tags`, `session_name` |
| Neighbouring schema terms | `session_id`, `session`, `project`, `run`, `runs`, `trace`, `batch` |
| Ingestion path and compatibility | `multipart`, `endpoint`, `method`, `deprecated`, `unsupported`, `version`, `upgrade` |
| Account scope | `workspace`, `tenant`, `organization` |
| Kinds of validation complaint | `required`, `missing`, `invalid`, `format`, `schema`, `json`, `body`, `payload`, `uuid`, `timestamp`, `datetime`, `future`, `duplicate`, `exists`, `empty`, `size`, `limit`, `quota`, `usage` |

Nothing that names a credential is listed: no `key`, `api`, `token`, `bearer`,
`authorization`, `auth`, `secret`, `password`, `credential` or `cookie`. A test
pins the tuple, so changing what a reply may reveal changes a test.

**Diagnostic only.** The hint is attached to `TraceDeliveryError.reply_hint` and
printed by the command with fixed labels. No code path reads it: it cannot
change the category, the message, the counts, the exit status, the budget, the
endpoint, the payload or whether anything is retried. A test asserts that no
conditional in the adapter refers to it, and the adversarial tests show
identical behaviour for every reply content.

One local fact is printed beside it: whether a workspace identifier was
configured and therefore sent (`workspace_header_sent`, yes or no). It comes
from the client configuration, not from the reply, and never includes the value.

**What a future 4xx can reveal, in full:**

```text
Delivery failed [request_rejected]: LangSmith rejected the request (HTTP 400). 0 of 4 runs were accepted.
Reply classification: declared json; observed json; complete: True; mentions: dotted_order, invalid
Workspace header sent: no
```

The first line is unchanged. In the second, each value is one of the closed
words above and `mentions` is a subset of the 51 names or `none`.

## Running it

From the repository root:

```powershell
uv run --locked --offline python module-06/run_langsmith.py --preview
uv run --locked --offline python module-06/run_langsmith.py --deliver
```

Without a flag the command prints a notice and exits 2. `--preview` runs the
deterministic workflow and prints the exact runs of the batch; it needs no
network and no credential. `--deliver` requires `LANGSMITH_API_KEY` in the
process environment. Exit status: 0 confirmed, 3 accepted but not confirmed, 1
failed or refused, 2 nothing requested. A failure is printed as
`Delivery failed [category]: message`, followed for a 4xx by the reply
classification and the workspace-header fact. The two flags are mutually
exclusive,
and there is no flag for a key, endpoint, path or project.

## Live verification

**Successful on the fifth attempt.** Every attempt was run by the human with the
credential set in their own terminal; the key was never shown to or read by the
implementing session.

| Attempt | Path at the time | Reported result | What it established |
| --- | --- | --- | --- |
| 1, 2026-10-13 | `POST /runs` per run | `Delivery failed: LangSmith could not be reached or refused the request.` exit 1 | A failure at a run-creation write. The adapter then had one generic message, so the cause was not determinable. A bounded classification was added afterwards. |
| 2, 2026-10-13 | `POST /runs` per run | `Delivery failed [request_rejected]: LangSmith rejected the request (HTTP 400). 0 of 4 runs were accepted.` exit 1 | The service answered the first write with HTTP 400. Network, TLS, authentication and authorization were therefore not the cause, and nothing was stored. |
| 3, 2026-10-13 | one `POST /runs/batch` | `Delivery failed [request_rejected]: LangSmith rejected the request (HTTP 400). 0 of 4 runs were accepted.` exit 1 | The batch endpoint returned HTTP 400 as well. The endpoint choice, the empty `attachments` key and `end_time` on creation are therefore not the cause. |
| 4, 2026-10-13 | one `POST /runs/batch`, with bounded reply inspection | The same failure line, then `Reply classification: declared html; observed html; complete: True; mentions: none` and `Workspace header sent: no` | The reply was a short HTML page naming no protocol term, not the API's JSON. That pointed away from the payload and towards a rejection in front of the API. |
| 5, 2026-10-13 | one `POST /runs/batch` | Receipt: `write_status` 202, `runs_accepted` 4, `confirmation` `service_read`, `read_attempts` 3, `requests` 4, `read_failure` null, trace `01a133ce-24d9-7cb0-b868-3a2e90f8e89c`; `Delivery confirmed: LangSmith returned the delivered root run.` exit 0 | LangSmith accepted the batch and returned the delivered root run. |

### Root cause of the four failures

Established by the human with a zero-network check in their own terminal and
reported to the implementing session, which never saw the credential. The
PowerShell secure prompt used to enter the key received Ctrl+V as the literal
control character U+0016 instead of pasting. The credential variable therefore
held one control character. The check reported one control character, code 22,
as both first and last character. Entering the key with right-click paste gave
text that was visible ASCII and longer than one character, and the very next
authorized request succeeded.

So the request line, endpoint, payload and workspace handling were never the
problem. The stack sent the control character as the `x-api-key` header, and
something answering for the service rejected that malformed request with an HTML
400 before API validation.

What this corrects in the earlier record: the first two diagnoses in this story
treated the 400 as a request-contract problem, and the move to the batch path
was made on that basis. Both were wrong about the cause. The batch path stays
because it is the SDK's documented method with a verified one-write boundary and
it is the path that has now been accepted, not because it repaired anything.

After attempt 2 an offline comparison showed that the request used the SDK's
non-batch fallback, which differs from the SDK's default batch request in two
ways: the endpoint, and an empty `attachments` key that the batch serializer
always removes. Relative to maintained callers of that endpoint it also set
`end_time` on creation. Which of these the service rejected was not
established, because the reply body is deliberately not read. Moving to
`Client.batch_ingest_runs` removes all three differences. That was a reasoned
repair and not a proven fix, and attempt 3 showed it was not a fix: the service
rejected the batch too. The differences were real but were not the cause.

Every authorized attempt is spent. Any further external request needs new human
authorization. The single-run endpoint was never retried with a valid
credential, so whether the service would accept it is unknown and no longer
matters to this story.

Expected cost is none within LangSmith's free allowance for four runs; pricing
was not checked from this offline environment and should be confirmed by the
credential owner.

## Current-path delivery verification (2026-10-22)

Classification: **current-path external LangSmith delivery verification**,
independently reviewed and **accepted** on 2026-10-22. One explicitly
human-authorized external delivery attempt executed this committed delivery
path against the deterministic sanitized trace only. No model inference was
involved; no automatic write retry or rerun occurred; no repository files were
modified during execution; no other external observability delivery was
attempted; the credential value was neither displayed nor recorded.

Observed receipt values:

| Receipt field | Value |
| --- | --- |
| Destination | `https://api.smith.langchain.com` |
| Project | `module6-verification` |
| Write path | `POST /runs/batch` (once) |
| Trace ID | `01a166fa-1c8d-7b40-9686-a08cfd14444f` |
| Runs accepted | 4 |
| Write status | 202 |
| Confirmation | `service_read` |
| Read attempts | 2 |
| Requests (write + reads) | 3 |
| Read failure | null |
| Root run | the delivered root run was returned by LangSmith |

Evidence artifact: `module-06-langsmith-current-path-delivery.txt`, held by the
authorized artifact holder outside the repository workspace (the Reviewer
intentionally did not access it under the workspace least-privilege boundary;
it is not stored in this repository). Artifact SHA-256:
`ED84729B851E875669597A1F7A0195A50DA61ED8EA66FEE88AAFD3126FD828D0`, verified
at capture time by the artifact holder.

Observation boundary: the implementing and reviewing agent sessions did not
independently observe the external LangSmith service response. The human
operator observed the execution, and the external evidence artifact preserves
the sanitized receipt above.

Scope and non-claims, preserved: this is one current-path external delivery
event on the deterministic sanitized trace. It does not prove live-model
LangSmith correlation, hosted-model execution, production readiness,
reliability or SLA performance, deployment readiness, or Module 6 completion.
It does not close live-model tracing or the M6-014 requirement, which remains
Planned; the model-backed LangSmith correlation and status-transition work
remain separate future authorized tasks. No NORMAL-profile, Ollama, model
digest or other real-local run facts belong to this event: it is orthogonal to
those, and no model was involved.

### Run 5 live-model delivery record (2026-10-22)

One real model-backed canonical workflow (local Ollama 0.40.9,
`qwen2.5-coder:7b`, LangGraph sequential Researcher -> Analyst -> Critic)
finalized a trusted `LiveTerminalObservation` whose projection (4 runs; root
trace UUID `e48944ac-1e67-4562-b6e7-e3cab5abbb4c`, preserved unchanged) was
externally delivered through the committed live-family
`LiveLangSmithDelivery` on this same batch endpoint and project: one write
(`POST /runs/batch`, status `accepted`), zero programmatic read-back
requests, committed evidence class **`unverified_write`** only. No
service-read confirmation exists for this event.

The full technical record, the mandatory pre-execution A2/A6 authority
history, the population-floor accounting and all non-claims are maintained in
the [canonical live workflow ledger](CANONICAL_LIVE_WORKFLOW.md). Summary of
the authority qualification, carried here because this file records
delivery: the event's authority-consumption status is operator-attested and
not independently confirmed; a prior model dispatch and/or prior LangSmith
batch write in an earlier indeterminate composition (A2) cannot be excluded,
so the one-inference and one-write global bounds are not independently
confirmed and the project must not be claimed to contain exactly one Run 5
trace/batch. No credential value is or was recorded in this file.

## Evidence

`tests/test_langsmith_delivery.py` has **510 passing cases** under the existing
guard that fails on any non-loopback DNS lookup or connection. The real SDK
client and its serialization are used; only `requests.Session.send` is replaced,
so real prepared requests are captured in memory. Every simulated reply carries
hostile text in its body and headers, including a credential-shaped string and a
very large `retry-after`, and counts any attempt to read its body. No test needs
a credential or reaches LangSmith. The tests cover:

- the required mode with no default, 12 invalid configurations and four forged
  configuration objects;
- the default application paths loading no delivery module and no provider SDK
  (checked in a subprocess), and no LangSmith client being constructed when a
  credential and tracing flags are merely present;
- three missing-credential forms failing closed before any request, with the
  legacy variable ignored and the budget untouched;
- the SDK batch method being the only write API used: `create_run`,
  `update_run`, multipart ingest, flush and run-tree post and patch are all
  forbidden in the test and never called;
- a successful delivery: exactly one write to `/runs/batch` and one read,
  streamed, redirects disabled, fixed timeouts, no proxy, the credential only in
  its header, the envelope and every run inside the closed shape, no
  `attachments` key, eleven kinds of private or environmental content absent,
  and the write reply body never read;
- the batch carrying exactly the previously approved run fields and metadata
  keys and no others;
- delivery failure leaving the workflow result and trace unchanged;
- 14 response statuses each classified from the status alone, with zero of four
  runs accepted, exactly one external write, completion in under five seconds
  despite the hostile `retry-after`, the reply body never read, no cause or
  context on the error, nothing remote or secret on any public surface or in
  the log, and no second attempt from the spent budget;
- seven no-response exception types classified by type, again with one write;
- an SDK-initiated second write refused at the transport, shown with the real
  SDK client calling its batch method twice on one pinned session;
- log suppression limited to the SDK client logger and to the call, restored
  afterwards and on error, with application records kept;
- a demonstration that the unprotected SDK call does retry three times and does
  log the hostile reply text, followed by the adapter making one write and
  logging none of it;
- eight unconfirmed read-backs returned as bounded receipts with a read-failure
  category, at exactly the request bound, with no failed reply body read;
- a contradictory read-back; read-back occurring only after an accepted batch;
- the lifetime budget; eleven ambient environment settings unable to redirect,
  expand or suppress delivery; failure before any request;
- a denied run delivered without invented accounting, and a distributed trace
  delivered without process or assignment identity; four non-trace inputs
  refused;
- 26 run mutations and 12 batch mutations refused by the wire guard;
- 19 disallowed destinations, paths and methods refused by the pinned session,
  including `/runs`, plus its single-write, request and time bounds;
- the SDK never receiving a failed reply from the transport;
- preview using no network and no credential; local refusals; the closed status
  vocabulary over every status from 100 to 599; 15 forged receipts rejected;
- the operator command sending nothing without `--deliver`, refusing key,
  endpoint and path arguments, and reporting success, unconfirmed delivery,
  rejection, TLS failure and a missing credential without secrets;
- bounded inspection of a failed reply:
  - the allowlist pinned as an exact tuple of 51 names, free of credential
    terms, and covering every run field the story transmits;
  - 22 hostile reply bodies run both through the classifier alone and through a
    full delivery and the operator command: a normal JSON error, a validation
    list, a JSON array, an HTML page with script, HTML declared as JSON, plain
    text, malformed JSON declared and undeclared, malformed UTF-8, empty and
    whitespace bodies, a body of exactly 2048 bytes, larger JSON and larger
    text, a character split at the bound, API-key-like and bearer-like secrets
    with authorization material, URLs and UUIDs, arbitrary prose, allowlisted
    words present only inside longer words, mixed-case tokens and an unknown
    content type. Each yields exactly the expected classification, one read of
    at most 2048 bytes, no unbounded read, one request, no retry, the same
    category, counts, message and exit status, and none of twelve hostile
    fragments on any public surface, in the log or in the command output;
  - seven malformed argument combinations never raising and never echoing;
  - every 4xx status read once and at most 2048 bytes; no 2xx, 3xx or 5xx write
    reply and no failed read-back reply inspected;
  - four kinds of fault while reading failing closed to `unknown`;
  - the workspace fact printed as yes or no and never as the value;
  - twelve forged hints rejected by the contract;
  - a source check that no conditional in the adapter refers to the hint;
- credential format validation:
  - every character code from 0 to 32, 127, 128 to 160 and 173 making text
    invalid alone, doubled and inside otherwise valid text; every visible ASCII
    character from U+0021 to U+007E accepted;
  - 31 malformed credentials, including U+0016 alone, doubled, inside, as prefix
    and as suffix, other control characters, DEL, an inner space, tab and line
    breaks, Latin-1 and Cyrillic text, a byte-order mark in both forms, a
    zero-width space, typographic quotes, single characters in four forms and
    quote-only text. Each is refused before a session or client exists, with
    zero requests, a fixed message containing no digit, no cause or context,
    none of the credential text on any public surface, log or command output,
    and no budget spent, after which a corrected credential delivers;
  - the U+0016 case reported as "invalid format" only, with no character code,
    count or description;
  - request accounting: one accepted write followed by six reads that fail
    before any response gives `requests` 7 with one recorded status; nine mixed
    sequences of answered and unanswered reads each give `requests` equal to one
    plus `read_attempts` and to the requests actually sent; a failed write is
    one attempt and no read; refused requests and refused credentials count
    zero; the bound stops the eighth attempt after seven unanswered ones; and a
    receipt whose `requests` is not one plus `read_attempts` is rejected;
  - nine well-formed credentials, including quoted and padded forms, passing
    and being sent normalized and only in the credential header, with the
    normalized text confirmed to be a fixed point of the SDK's own
    normalization;
  - non-text values never valid;
  - a valid-looking credential authorizing nothing without explicit delivery;
  - a source check that validation precedes the request path and that the
    validator performs no input or output.

A loopback run through the real HTTP stack, with a dummy key and external
access blocked, confirmed the same behaviour outside the in-memory stand-in:
one `POST /runs/batch` of four runs followed by one read on success; exactly
one request and the expected category for simulated 400, 403, 422, 429, 500 and
503 replies, none taking longer than a few hundredths of a second; a refused
connection classified `connection_failed`; and no reply text in any log record.
A second loopback run exercised the bounded inspection on real replies,
including a gzip-encoded one: JSON, HTML, text, oversized and empty 4xx bodies
each produced the expected classification with one request and no marker text
in any error or log, and a 500 produced no classification.

### Gates

- `ruff check .` passes. Ruff formatting was applied only to the three new
  Python files; no unsafe fixes were used.
- Complete Module 6 pytest: **1304 passed**, no skips (794 + 510).
- `compileall` over the Module 6 source, tests and commands passes.
- Root collection: **3425 tests** (2915 + 510).
- Complete root pytest: **3419 passed, 6 skipped, 3 warnings**; the
  skips and warnings are the existing Module 5 and Module 3 ones.
- History of this story's own test file: 94 cases at first implementation, 139
  after the failure-classification repair, 142 after the move to the batch
  path, 234 after the bounded reply inspection, 484 after the credential
  format validation, 510 after the request-accounting repair. For the
  inspection, one
  assertion in an existing story test was changed deliberately: a rejected 4xx
  reply is no longer "never read" but "read once, at most 2048 bytes, never
  unbounded". The move changed delivery from four writes to one, so the story's
  per-write and partial-delivery tests were replaced by single-write and
  all-or-nothing tests. No accepted test from an earlier story was touched.
- Genuine candidate defects found and repaired during this story:
  1. the new module first imported `langsmith` statically, which the accepted
     `test_standalone_source_and_domain_boundaries` forbids; it now uses the
     repository's lazy `import_module` convention;
  2. the public error kept the original SDK exception as context; it is now
     raised outside the handler;
  3. during the batch repair a test showed the SDK writing a debug record with
     exception text on a failed read; log suppression was widened from the
     write call to the whole delivery;
  4. independent acceptance found that the receipt's `requests` field counted
     responses received, not requests attempted, so one accepted write and six
     reads that failed before any response reported 1 where 7 were sent. The
     receipt now reads the session's attempt counter, the same one that
     enforces the 7-request bound, and a receipt must have `requests` equal to
     one plus `read_attempts`. The existing test already captured the seven
     attempts but did not assert the field; it now does. The live receipt of
     attempt 5 is unaffected: all four of its requests were answered.

## Requirements and Definition of Done

M6-014 now has a real, bounded, opt-in delivery path with offline proof of its
shape and controls, and one live delivery confirmed by service read-back, run by
the human and reported to the implementing session. That live evidence has not
yet been independently accepted. M6-016 gains one delivered payload-free trace.
All 26 source meanings and Planned statuses remain frozen; nothing is marked
complete or verified in this story.

Requirements: live evidence obtained, acceptance and status transition pending.
Product experience: an operator command with a preview. Real functionality: real
SDK client, serialization and requests; one real delivery accepted and read
back. Reliability: one write, bounded reads, time and attempts; no retry; no
effect on workflows. Security: explicit selection, pinned destination and path,
wire validation, credential format checked locally and confined to one header,
no reply text or SDK log text exposed. Cost: no paid service used. Evidence:
offline tests plus one human-run live delivery. Deployment: unverified.

## Unverified limitations

- Independent acceptance of the live delivery. The receipt was produced by the
  human's run; the implementing session did not observe the service.
- The live delivery was made before the credential format validation was added.
  The validation is proven offline only; it does not change a request made with
  a well-formed credential.
- The format check cannot tell a well-formed but wrong key from a right one.
- Which component answered the malformed requests with HTML is unknown.
- Read-back needed three attempts in the successful run; ingestion is
  asynchronous, and a slower service could exceed the six-attempt window.
- Only the default hosted origin is supported. An account in another LangSmith
  region would need a separately authorized origin.
- A `connection_failed` result does not separate DNS, a refused connection and
  a proxy; a `request_rejected` result gives the status but not the reason.
- LangSmith pricing, quotas and retention.
- The console does not deliver traces or show a LangSmith link.
- Child runs carry completion provenance, not native per-agent timing.
