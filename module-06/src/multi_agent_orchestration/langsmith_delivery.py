"""Explicit operator-selected delivery of one sanitized trace to LangSmith.

Nothing here runs by default. The accepted offline ``LocalLangSmith`` adapter is
unchanged and remains the only tracing used by workflows, the console and tests.
Delivery exists only when trusted operator code builds ``LangSmithTraceDelivery``
from a validated ``LangSmithDeliveryConfig`` and calls ``deliver`` with a trace
that a workflow has already finished producing. Workflow requests, runtime
output, a present credential and environment variables cannot select delivery,
choose its destination or add to its payload. No model or provider is involved.
"""

import json
import logging
import os
import re
import threading
import time
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from importlib import import_module
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from .contracts import Contract, GraphTopology, RuntimeId
from .observability_adapters import checked_trace
from .observability_contracts import Outcome, Role, RunTrace

API_KEY_VARIABLE = "LANGSMITH_API_KEY"
ORIGIN = "https://api.smith.langchain.com"
PROJECT = "module6-verification"
ROOT_NAME = "module6.workflow"
ROOT_TAGS = ("module6", "deterministic", "no-llm-inference")
WRITE_URL = "https://api.smith.langchain.com/runs/batch"
MAX_RUNS = 4
MAX_BODY_BYTES = 4096
MAX_BATCH_BYTES = 8192
READ_ATTEMPTS = 6
MAX_REQUESTS = 1 + READ_ATTEMPTS
READ_INTERVAL_S = 2.0
DEADLINE_S = 60.0
TIMEOUT_MS = (5_000, 10_000)
_PLACEHOLDER = "preview-placeholder-not-a-credential"
_STAMP = r"[0-9]{8}T[0-9]{12}Z[0-9a-f-]{36}"
_DOTTED = re.compile(rf"^{_STAMP}(\.{_STAMP})?$")
_BODY_KEYS = frozenset(
    {
        "dotted_order",
        "end_time",
        "error",
        "events",
        "extra",
        "id",
        "inputs",
        "name",
        "outputs",
        "parent_run_id",
        "run_type",
        "session_name",
        "start_time",
        "tags",
        "trace_id",
    }
)
_METADATA = {
    "module": ("module-06",),
    "verification": ("deterministic_orchestration",),
    "inference": ("none",),
    "evidence_class": ("deterministic_offline_execution",),
    "runtime": tuple(item.value for item in RuntimeId),
    "topology": tuple(item.value for item in GraphTopology),
    "distributed": (True, False),
    "outcome": tuple(item.value for item in Outcome),
    "model_calls": (0,),
    "observation": ("validated_completion",),
    "role_sequence": (1, 2, 3),
}


FailureCategory = Literal[
    "refused",
    "failed_before_send",
    "connection_failed",
    "tls_failed",
    "timed_out",
    "authentication_rejected",
    "authorization_rejected",
    "request_rejected",
    "rate_limited",
    "service_failed",
    "unexpected_response",
    "unexpected_failure",
]
_FAILURE_TEXT = {
    "failed_before_send": "Delivery failed before any request was sent.",
    "connection_failed": "No response from LangSmith: the connection failed.",
    "tls_failed": "No response from LangSmith: the TLS handshake failed.",
    "timed_out": "No response from LangSmith: the request timed out.",
    "authentication_rejected": "LangSmith rejected the credential",
    "authorization_rejected": "LangSmith refused permission for this credential",
    "request_rejected": "LangSmith rejected the request",
    "rate_limited": "LangSmith rate-limited the request",
    "service_failed": "LangSmith reported a service error",
    "unexpected_response": "LangSmith returned an unexpected response",
    "unexpected_failure": "No response from LangSmith, for an unclassified reason.",
}


MAX_REPLY_BYTES = 2048
ReplyFormat = Literal["json", "html", "text", "empty", "unknown"]
# Closed, source-controlled diagnostic vocabulary. A failed reply can only ever
# be described by names from this tuple; no word of the reply itself is kept.
# It holds protocol and schema terms only, and deliberately nothing that names
# a credential (no "key", "token", "bearer", "authorization" or "secret").
REPLY_TOKENS = (
    # Run fields this story transmits.
    "id",
    "trace_id",
    "parent_run_id",
    "dotted_order",
    "start_time",
    "end_time",
    "name",
    "run_type",
    "inputs",
    "outputs",
    "events",
    "extra",
    "metadata",
    "tags",
    "session_name",
    # Neighbouring schema terms of the run API.
    "session_id",
    "session",
    "project",
    "run",
    "runs",
    "trace",
    "batch",
    # Ingestion path and compatibility.
    "multipart",
    "endpoint",
    "method",
    "deprecated",
    "unsupported",
    "version",
    "upgrade",
    # Account scope.
    "workspace",
    "tenant",
    "organization",
    # Kinds of validation complaint.
    "required",
    "missing",
    "invalid",
    "format",
    "schema",
    "json",
    "body",
    "payload",
    "uuid",
    "timestamp",
    "datetime",
    "future",
    "duplicate",
    "exists",
    "empty",
    "size",
    "limit",
    "quota",
    "usage",
)
_REPLY_TOKEN_SET = frozenset(REPLY_TOKENS)
_WORD = re.compile(r"[a-z0-9_]+")


class ReplyHint(Contract):
    """Application-owned classification of one failed reply; diagnostic only.

    It holds no text, number, header or identifier taken from the reply. It is
    never read by delivery logic and cannot change what the adapter does.

    Attributes:
        declared: Class of the reply's content type; the header value is dropped.
        observed: Class of the bounded content itself.
        complete: Whether fewer than ``MAX_REPLY_BYTES`` bytes were available,
            so the classification saw the whole reply.
        mentions: Canonical names from ``REPLY_TOKENS`` that occurred as whole
            tokens, sorted. Nothing else can appear here.
    """

    declared: Literal["json", "html", "text", "unknown"]
    observed: ReplyFormat
    complete: Annotated[bool, Field(strict=True)]
    mentions: Annotated[
        tuple[Literal[REPLY_TOKENS], ...], Field(max_length=len(REPLY_TOKENS))
    ] = ()

    @model_validator(mode="after")
    def canonical(self):
        if list(self.mentions) != sorted(set(self.mentions)):
            raise ValueError("Mentions must be unique and sorted.")
        if self.observed in ("empty", "unknown") and self.mentions:
            raise ValueError("Unclassifiable content cannot carry mentions.")
        return self


def classify_reply(content_type: object, raw: object) -> ReplyHint:
    """Classify untrusted reply bytes into the closed vocabulary; never raises.

    Only the first ``MAX_REPLY_BYTES`` bytes are considered. Content that is not
    valid UTF-8, or that presents itself as JSON and does not parse, is reported
    as ``unknown`` with no mentions. A mention requires an exact, case-normalized
    token: a listed word inside a longer word does not count.
    """
    declared = "unknown"
    if type(content_type) is str:
        kind = content_type[:128].split(";", 1)[0].strip().lower()
        if kind == "application/json" or kind.endswith("+json"):
            declared = "json"
        elif kind == "text/html":
            declared = "html"
        elif kind.startswith("text/"):
            declared = "text"
    data = raw[:MAX_REPLY_BYTES] if type(raw) is bytes else b""
    complete = type(raw) is bytes and len(raw) < MAX_REPLY_BYTES

    def hint(observed, words=()):
        return ReplyHint(
            declared=declared, observed=observed, complete=complete, mentions=words
        )

    decoded = None
    # A full buffer may end inside a character; tolerate only that, and bounded.
    for trim in range(4 if not complete else 1):
        try:
            decoded = data[: len(data) - trim].decode("utf-8", errors="strict")
            break
        except UnicodeDecodeError:
            continue
    if decoded is None:
        return hint("unknown")
    lowered = decoded.lower()
    stripped = lowered.strip()
    if not stripped:
        return hint("empty")
    if stripped.startswith(("<!doctype html", "<html")) or "<html" in stripped:
        observed = "html"
    elif declared == "json" or stripped[0] in "{[":
        try:
            json.loads(decoded)
        except ValueError:
            return hint("unknown")  # Claims to be JSON and is not: fail closed.
        observed = "json"
    else:
        observed = "text"
    found = sorted(_REPLY_TOKEN_SET.intersection(_WORD.findall(lowered)))
    return hint(observed, tuple(found))


class TraceDeliveryError(RuntimeError):
    """Delivery was refused or failed; every part is fixed and holds no secret.

    Attributes:
        category: Closed application vocabulary. ``refused`` means the adapter
            declined locally and nothing was sent by that call.
        http_status: Status code of the response that ended delivery, if any.
        accepted_runs: Runs LangSmith accepted. All runs travel in one batch
            write, so this is zero unless that write was accepted.
        planned_runs: Runs the trace holds, once that was known.
        reply_hint: Bounded classification of a 4xx reply to the write, if any.
            Diagnostic evidence for a person; no code path consults it.
        workspace_header_sent: Whether a workspace identifier was configured
            locally and therefore sent; never its value.
    """

    def __init__(
        self,
        message: str,
        *,
        category: FailureCategory = "refused",
        http_status: int | None = None,
        accepted_runs: int | None = None,
        planned_runs: int | None = None,
        reply_hint: ReplyHint | None = None,
        workspace_header_sent: bool | None = None,
    ):
        super().__init__(message)
        self.category = category
        self.http_status = http_status
        self.accepted_runs = accepted_runs
        self.planned_runs = planned_runs
        self.reply_hint = reply_hint
        self.workspace_header_sent = workspace_header_sent


def status_category(status: int, *, reading: bool = False) -> str:
    """Map a status code to the closed vocabulary; the reply body is never used."""
    if reading and status == 404:
        return "not_found"
    if status == 401:
        return "authentication_rejected"
    if status == 403:
        return "authorization_rejected"
    if status == 429:
        return "rate_limited"
    if 500 <= status <= 599:
        return "service_failed"
    if 400 <= status <= 499:
        return "request_rejected"
    return "unexpected_response"


def _transport_category(error: BaseException | None) -> str:
    """Classify a failure that produced no response, by exception type alone."""
    requests = import_module("requests").exceptions
    connection = import_module("langsmith.utils").LangSmithConnectionError
    found = "unexpected_failure"
    for _ in range(6):  # Bounded walk; exception text is never read.
        if error is None:
            break
        if isinstance(error, requests.SSLError):
            return "tls_failed"
        if isinstance(error, requests.Timeout):
            return "timed_out"
        if isinstance(error, requests.ConnectionError | connection):
            found = "connection_failed"
        error = error.__cause__ or error.__context__
    return found


def _failure(
    category: str,
    status: int | None,
    accepted: int,
    planned: int | None,
    hint: ReplyHint | None = None,
    workspace: bool | None = None,
) -> TraceDeliveryError:
    """Build the public failure from structured facts and fixed wording only."""
    text = _FAILURE_TEXT[category]
    if status is not None:
        text = f"{text} (HTTP {status})."
    if planned is not None:
        text = f"{text} {accepted} of {planned} runs were accepted."
    return TraceDeliveryError(
        text,
        category=category,
        http_status=status,
        accepted_runs=accepted,
        planned_runs=planned,
        reply_hint=hint,
        workspace_header_sent=workspace,
    )


class LangSmithDeliveryConfig(Contract):
    """Operator-owned delivery selection; never part of workflow or runtime data.

    Attributes:
        mode: Required explicit selection. There is no default and no
            environment variable that supplies it.
        max_traces: Delivery attempts this adapter may make in its lifetime.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    mode: Literal["langsmith-live"]
    max_traces: Annotated[int, Field(strict=True, ge=1, le=3)] = 1


class DeliveryReceipt(Contract):
    """Non-secret evidence of one delivery; never authority or a workflow result.

    All runs of the trace are sent in one batch write, so ``runs_accepted`` is
    the whole trace. ``requests`` counts request attempts made through the
    pinned session, including any that received no response: always the one
    write plus ``read_attempts``. ``service_read`` means LangSmith returned the
    delivered root run by its identifier. ``accepted_only`` means the write was accepted
    but the run could not be read back inside the bounded window;
    ``read_failure`` then holds the closed category of the last read attempt.
    """

    destination: Literal["https://api.smith.langchain.com"] = ORIGIN
    write_path: Literal["/runs/batch"] = "/runs/batch"
    project: Literal["module6-verification"] = PROJECT
    trace_id: UUID
    runs_accepted: Annotated[int, Field(strict=True, ge=1, le=MAX_RUNS)]
    write_status: Annotated[int, Field(strict=True, ge=200, le=299)]
    confirmation: Literal["service_read", "accepted_only"]
    read_attempts: Annotated[int, Field(strict=True, ge=0, le=READ_ATTEMPTS)]
    requests: Annotated[int, Field(strict=True, ge=1, le=MAX_REQUESTS)]
    read_failure: (
        Literal[
            "not_found",
            "connection_failed",
            "tls_failed",
            "timed_out",
            "authentication_rejected",
            "authorization_rejected",
            "request_rejected",
            "rate_limited",
            "service_failed",
            "unexpected_response",
            "unexpected_failure",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def consistency(self):
        if (
            self.requests != 1 + self.read_attempts
            or (self.confirmation == "service_read" and self.read_attempts < 1)
            or (self.confirmation == "service_read") != (self.read_failure is None)
        ):
            raise ValueError("Receipt contradicts the bounded delivery.")
        return self


def credential_configured() -> bool:
    """Whether the credential variable is present; its value is never returned."""
    return bool((os.environ.get(API_KEY_VARIABLE) or "").strip())


def normalized_credential(text: object) -> str:
    """Apply the SDK's own credential normalization until it changes nothing.

    The installed SDK strips surrounding whitespace, then surrounding double
    quotes, then surrounding single quotes. Repeating that to a fixed point
    gives exactly the text the SDK would put in the request header, so what is
    validated is what would be sent. Bounded: each pass removes a character.
    """
    value = text if type(text) is str else ""
    while True:
        cleaned = value.strip().strip('"').strip("'")
        if cleaned == value:
            return value
        value = cleaned


def credential_format_valid(text: object) -> bool:
    """Whether credential text is usable in an HTTP header; nothing else is told.

    After normalization it must have more than one character and consist only of
    visible ASCII, U+0021 to U+007E. A control character such as U+0016, DEL,
    an inner space or any non-ASCII character makes it invalid. Neither the
    text nor its length is returned, logged or kept.
    """
    value = normalized_credential(text)
    return len(value) > 1 and all("\u0021" <= char <= "\u007e" for char in value)


def credential_usable() -> bool:
    """Whether the configured credential has a valid format; never its value."""
    return credential_format_valid(os.environ.get(API_KEY_VARIABLE))


def _uuid(value: object) -> UUID:
    if type(value) is not str:
        raise ValueError("Identifier must be text.")
    return UUID(value)


def _bytes(data: object, limit: int) -> bytes:
    raw = data.encode("utf-8") if type(data) is str else data
    if type(raw) is not bytes or len(raw) > limit:
        raise ValueError("Body is missing or exceeds the hard bound.")
    return raw


def checked_batch(data: object) -> list[dict]:
    """Validate the one outgoing batch at the wire; anything unexpected is refused.

    The SDK serializes the request, so this is the last point at which added
    fields, payloads or runs the application did not choose can be caught. The
    batch must hold only new runs: exactly one root first, then its children.
    """
    batch = json.loads(_bytes(data, MAX_BATCH_BYTES))
    if type(batch) is not dict or set(batch) != {"post"}:
        raise ValueError("Batch carries operations other than run creation.")
    runs = batch["post"]
    if type(runs) is not list or not 1 <= len(runs) <= MAX_RUNS:
        raise ValueError("Batch run count is outside the hard bound.")
    for run in runs:
        checked_body(json.dumps(run))
    root = runs[0]
    if (
        "parent_run_id" in root
        or any(run.get("parent_run_id") != root["id"] for run in runs[1:])
        or len({run["id"] for run in runs}) != len(runs)
    ):
        raise ValueError("Batch must be one root run followed by its children.")
    return runs


def checked_body(data: object) -> dict:
    """Validate one run of the batch against the closed, payload-free shape."""
    body = json.loads(_bytes(data, MAX_BODY_BYTES))
    if type(body) is not dict or not set(body) <= _BODY_KEYS:
        raise ValueError("Run body carries unexpected fields.")
    root = "parent_run_id" not in body
    metadata = body["extra"]["metadata"]
    if (
        set(body["extra"]) != {"metadata"}
        or type(metadata) is not dict
        or body["inputs"] != {}
        or body["outputs"] != {}
        or body["events"] != []
        or body["run_type"] != "chain"
        or body["session_name"] != PROJECT
        or body["tags"] != (list(ROOT_TAGS) if root else [])
        or body["name"]
        not in ((ROOT_NAME,) if root else tuple(role.value for role in Role))
        or body.get("error") not in (None, *(item.value for item in Outcome))
        or type(body["dotted_order"]) is not str
        or not _DOTTED.fullmatch(body["dotted_order"])
        or ("." in body["dotted_order"]) == root
    ):
        raise ValueError("Run body is outside the closed trace shape.")
    for key, value in metadata.items():
        if key == "workflow_id":
            _uuid(value)
        elif key not in _METADATA or not any(
            type(value) is type(allowed) and value == allowed
            for allowed in _METADATA[key]
        ):
            raise ValueError("Run metadata is outside the closed vocabulary.")
    owner = body["id"] if root else body["parent_run_id"]
    if _uuid(owner) != _uuid(body["trace_id"]) or _uuid(body["id"]).int == 0:
        raise ValueError("Every run must belong to the single root trace.")
    for key in ("start_time", "end_time"):
        datetime.fromisoformat(body[key])
    return body


def _session(offline: bool, started: float):
    """A ``requests`` session that owns every external effect of one delivery.

    It permits exactly one write, ``POST {ORIGIN}/runs/batch``, and afterwards
    reads of the one delivered root run. It, not the SDK, decides what happened:
    the real outcome of the write is recorded here as a status integer or an
    exception category, and the SDK is handed an empty accepted reply. The SDK
    therefore has no failure to retry, no reply text to log and no reply body
    to read. The body of a failed reply is discarded without being read.
    """
    import requests

    def empty(status: int):
        response = requests.Response()
        response.status_code, response._content = status, b"{}"
        return response

    class Pinned(requests.Session):
        def __init__(self):
            super().__init__()
            # No proxy, netrc or certificate settings from the environment.
            self.trust_env = False
            self.max_redirects = 0
            self.posted: list[dict] = []
            self.statuses: list[tuple[str, int]] = []
            # ``attempted`` is the one definition of a request attempt: it is
            # advanced immediately before a request is handed to the transport,
            # never for a request refused here, and whether or not a response
            # ever arrives. The budget check and the receipt both read it.
            # ``statuses`` records responses actually received, which can be
            # fewer, and is never used as a request count.
            self.attempted = self.writes = 0
            self.write_status: int | None = None
            self.write_category: str | None = None
            self.reply_hint: ReplyHint | None = None
            self.readable: str | None = None
            self.unanswered = False
            self.refusal: str | None = None

        def refuse(self, reason: str):
            # Kept on the session because the SDK may wrap or swallow the raise.
            self.refusal = self.refusal or reason
            raise TraceDeliveryError(reason)

        def request(self, method, url, **kwargs):
            if (
                self.attempted >= MAX_REQUESTS
                or time.monotonic() - started > DEADLINE_S
            ):
                self.refuse("Delivery exceeded its request or time bound.")
            if method == "POST" and url == WRITE_URL:
                return self._write(url, kwargs)
            if method == "GET" and url == self.readable and self.readable:
                return self._read(url, kwargs)
            self.refuse(
                "Delivery refused: the request is not a fixed LangSmith run path."
            )

        @staticmethod
        def _discard(reply):
            """Release a streamed reply without ever reading its body."""
            try:
                reply.close()
            except Exception:
                pass  # Closing is housekeeping; it cannot change the outcome.

        @staticmethod
        def _inspect(reply) -> ReplyHint:
            """One bounded read of a 4xx reply, reduced at once to a classification.

            The bytes exist only in this frame. Nothing is logged, stored or
            raised from them, and any fault yields the ``unknown`` classification.
            """
            try:
                raw = reply.raw.read(MAX_REPLY_BYTES, decode_content=True)
                return classify_reply(reply.headers.get("content-type"), raw)
            except Exception:
                return ReplyHint(declared="unknown", observed="unknown", complete=False)

        def _write(self, url, kwargs):
            if self.writes:
                # The SDK retries this call by itself; a delivery writes once.
                self.refuse("Delivery refused: a second write was attempted.")
            try:
                self.posted = checked_batch(kwargs.get("data"))
            except (ValueError, KeyError, TypeError):
                self.refuse(
                    "Delivery refused: the outgoing batch is not the closed "
                    "sanitized shape."
                )
            self.writes += 1
            self.attempted += 1
            if offline:
                self.write_status = 202
            else:
                kwargs.update(allow_redirects=False, stream=True)
                try:
                    reply = super().request("POST", url, **kwargs)
                except Exception as exc:
                    # Only its type is kept; the exception is not retained.
                    self.write_category = _transport_category(exc)
                else:
                    self.write_status = reply.status_code
                    if 400 <= reply.status_code <= 499:
                        self.reply_hint = self._inspect(reply)
                    self._discard(reply)
            if self.write_status is not None:
                self.statuses.append(("POST", self.write_status))
            return empty(202)

        def _read(self, url, kwargs):
            self.attempted += 1
            self.unanswered = True
            kwargs.update(allow_redirects=False, stream=True)
            reply = super().request("GET", url, **kwargs)
            self.unanswered = False
            self.statuses.append(("GET", reply.status_code))
            if reply.status_code != 200:
                self._discard(reply)
                return empty(reply.status_code)
            return reply

        def read_failure(self, error: BaseException | None) -> str:
            """Category of the newest read, from structured facts only."""
            if self.unanswered:
                return _transport_category(error)
            return status_category(self.statuses[-1][1], reading=True)

    return Pinned()


@contextmanager
def _silenced_sdk():
    """Drop records of the SDK client logger for the duration of one delivery.

    The SDK reports failures by logging exception text, which can quote a reply
    or a request. Only that logger is filtered, and only inside the block;
    application logging and every other logger are untouched.
    """

    class Drop(logging.Filter):
        def filter(self, record):
            return False

    sdk_logger, drop = logging.getLogger("langsmith.client"), Drop()
    sdk_logger.addFilter(drop)
    try:
        yield
    finally:
        sdk_logger.removeFilter(drop)


def _timestamp(nanoseconds: int) -> datetime:
    return datetime.fromtimestamp(nanoseconds / 1_000_000_000, UTC)


def _runs(trace: RunTrace) -> list[dict]:
    """Closed, payload-free run fields for ``Client.batch_ingest_runs``.

    A real SDK run tree supplies the identifiers, trace linkage and dotted
    order. Only named fields are then taken from it, so nothing the SDK or the
    environment attaches to a run tree can travel with the batch.
    """
    # Match the repository's lazy SDK boundary; no module-level SDK import.
    RunTree = import_module("langsmith.run_trees").RunTree

    metadata = {
        "module": "module-06",
        "verification": "deterministic_orchestration",
        "inference": "none",
        "evidence_class": "deterministic_offline_execution",
        "runtime": trace.runtime.value,
        "topology": trace.topology.value,
        "distributed": trace.distributed,
        "outcome": trace.outcome.value,
        "workflow_id": str(trace.workflow_id),
    }
    if trace.accounting.model_calls == 0:
        metadata["model_calls"] = 0
    tree = RunTree(
        name=ROOT_NAME,
        run_type="chain",
        project_name=PROJECT,
        inputs={},
        outputs={},
        extra={"metadata": metadata},
        start_time=_timestamp(trace.started_ns),
        end_time=_timestamp(trace.ended_ns),
        error=None if trace.outcome == Outcome.COMPLETED else trace.outcome.value,
        tags=list(ROOT_TAGS),
        replicas=[],
        attachments={},
    )
    children = [
        tree.create_child(
            name=step.role.value,
            run_type="chain",
            inputs={},
            outputs={},
            start_time=_timestamp(trace.ended_ns),
            end_time=_timestamp(trace.ended_ns),
            extra={
                "metadata": {
                    "observation": "validated_completion",
                    "role_sequence": step.sequence,
                }
            },
        )
        for step in trace.steps
    ]
    if any(run.address is not None or run.replicas for run in (tree, *children)):
        raise TraceDeliveryError(
            "Delivery refused: ambient LangSmith routing settings are present."
        )

    def fields(run, tags):
        body = {
            "id": run.id,
            "trace_id": run.trace_id,
            "dotted_order": run.dotted_order,
            "name": run.name,
            "run_type": "chain",
            "session_name": PROJECT,
            "start_time": run.start_time,
            "end_time": run.end_time,
            "inputs": {},
            "outputs": {},
            "events": [],
            "tags": list(tags),
            "extra": {"metadata": dict(run.extra["metadata"])},
        }
        if run.parent_run_id is not None:
            body["parent_run_id"] = run.parent_run_id
        if run.error is not None:
            body["error"] = run.error
        return body

    return [fields(tree, ROOT_TAGS), *(fields(child, ()) for child in children)]


class LangSmithTraceDelivery:
    """Sends one finished application trace to LangSmith, synchronously and bounded.

    The installed SDK serializes and posts the runs through its documented
    ``Client.batch_ingest_runs`` method, as one ``POST /runs/batch``, on a
    client pinned to the fixed LangSmith origin: explicit URL and key, no
    background thread, no redirect, no environment proxy, no runtime-environment
    metadata, hidden inputs and outputs. The pinned session permits one write,
    revalidates the outgoing batch at the wire, and keeps failures away from
    the SDK, so the SDK can neither retry nor log reply text. Delivery runs
    after the workflow has returned, so it cannot change a workflow result.

    Args:
        config: A validated ``LangSmithDeliveryConfig`` built by operator code.

    Raises:
        TraceDeliveryError: The configuration is not an owned, valid instance.
    """

    def __init__(self, config: LangSmithDeliveryConfig):
        if type(config) is not LangSmithDeliveryConfig or set(config.__dict__) != set(
            LangSmithDeliveryConfig.model_fields
        ):
            raise TraceDeliveryError("Delivery requires an operator configuration.")
        try:
            self.config = LangSmithDeliveryConfig.model_validate(dict(config.__dict__))
        except ValueError:
            raise TraceDeliveryError("Delivery configuration is invalid.") from None
        self._attempts = 0
        self._lock = threading.Lock()

    def preview(self, trace: RunTrace) -> tuple[dict, ...]:
        """Exact run bodies ``deliver`` would post. No network, no credential."""
        return tuple(self._run(trace, _PLACEHOLDER, offline=True))

    def deliver(self, trace: RunTrace) -> DeliveryReceipt:
        """Post the trace and read its root run back from LangSmith.

        Raises:
            TraceDeliveryError: The budget is spent, the credential variable is
                unset or its text has an invalid format, the trace or an
                outgoing body is not the closed shape, or LangSmith could not
                be reached or refused the request.
        """
        with self._lock:
            if self._attempts >= self.config.max_traces:
                raise TraceDeliveryError("This adapter's delivery budget is spent.")
            raw = os.environ.get(API_KEY_VARIABLE) or ""
            if not raw.strip():
                raise TraceDeliveryError(
                    f"{API_KEY_VARIABLE} is not set in this process. Nothing was sent."
                )
            # Checked before any session, client or request exists. A credential
            # that is not plain visible ASCII would otherwise travel in a header
            # and be rejected remotely, as a pasted control character once was.
            # The message is fixed: no content, length or position is disclosed.
            if not credential_format_valid(raw):
                raise TraceDeliveryError(
                    f"{API_KEY_VARIABLE} has an invalid format. Nothing was sent."
                )
            key = normalized_credential(raw)
            self._attempts += 1  # Failed attempts count, so there is no retry loop.
            return self._run(trace, key, offline=False)

    def _run(self, trace: RunTrace, key: str, *, offline: bool):
        try:
            trace = checked_trace(trace)
        except (ValueError, TypeError, AttributeError):
            raise TraceDeliveryError(
                "Delivery refused: not an application trace."
            ) from None
        sdk = import_module("langsmith")
        schemas = import_module("langsmith.schemas")
        from urllib3.util import Retry

        session = _session(offline, time.monotonic())
        planned = failure = None
        # The SDK logs failures with exception text: a rejected batch at warning
        # level and a failed read at debug level. The session already keeps
        # write failures from it; this filter covers the rest. It is limited to
        # the SDK client logger and to this one delivery.
        quiet = ExitStack()
        quiet.enter_context(_silenced_sdk())
        try:
            client = sdk.Client(
                api_url=ORIGIN,
                api_key=key,
                auto_batch_tracing=False,
                session=session,
                retry_config=Retry(total=0),
                timeout_ms=TIMEOUT_MS,
                omit_traced_runtime_info=True,
                hide_inputs=True,
                hide_outputs=True,
                hide_metadata=False,
                tracing_sampling_rate=1.0,
                info=schemas.LangSmithInfo(),
                tracing_mode="langsmith",
                disable_prompt_cache=True,
            )
            if client.api_url != ORIGIN or client.tracing_queue is not None:
                raise TraceDeliveryError("Delivery refused: client is not pinned.")
            runs = _runs(trace)
            planned, root = len(runs), runs[0]["id"]
            client.batch_ingest_runs(create=runs)
            if session.refusal is not None:
                raise TraceDeliveryError(session.refusal)
            if not session.writes:
                raise _failure("failed_before_send", None, 0, planned)
            status = session.write_status
            if status is None:
                raise _failure(session.write_category, None, 0, planned)
            if not 200 <= status <= 299:
                # One batch carries every run, so a rejected write accepted none.
                # The hint is attached for a person to read; nothing below or
                # elsewhere branches on it.
                raise _failure(
                    status_category(status),
                    status,
                    0,
                    planned,
                    session.reply_hint,
                    client.workspace_id is not None,
                )
            if offline:
                return session.posted
            session.readable = f"{ORIGIN}/runs/{root}"
            confirmed, attempts, unread = False, 0, None
            while attempts < READ_ATTEMPTS and not confirmed:
                attempts += 1
                problem = None
                try:
                    stored = client.request_with_retries("GET", f"/runs/{root}").json()
                except Exception as exc:
                    if session.refusal is not None:
                        raise
                    # Often just not readable yet; ingestion is asynchronous.
                    stored, problem = None, session.read_failure(exc)
                if type(stored) is dict:
                    # The reply is untrusted: it must describe exactly this run.
                    if (
                        stored.get("id") != str(root)
                        or stored.get("trace_id") != str(root)
                        or stored.get("name") != ROOT_NAME
                        or stored.get("run_type") != "chain"
                    ):
                        raise TraceDeliveryError(
                            "LangSmith returned a run that contradicts the delivery."
                        )
                    confirmed = True
                else:
                    unread = problem or "unexpected_response"
                    if attempts < READ_ATTEMPTS:
                        time.sleep(READ_INTERVAL_S)
            return DeliveryReceipt(
                trace_id=root,
                runs_accepted=planned,
                write_status=status,
                confirmation="service_read" if confirmed else "accepted_only",
                read_attempts=attempts,
                requests=session.attempted,
                read_failure=None if confirmed else unread,
            )
        except TraceDeliveryError:
            raise
        except Exception as exc:
            # Classified from recorded status codes, counts and exception types.
            # SDK and transport messages can quote URLs, replies or a masked
            # key, so no text is read from them and the exception is not kept.
            if session.refusal is not None:
                failure = TraceDeliveryError(session.refusal)
            elif not session.writes:
                failure = _failure("failed_before_send", None, 0, planned)
            else:
                accepted = 200 <= (session.write_status or 0) <= 299
                failure = _failure(
                    _transport_category(exc), None, planned if accepted else 0, planned
                )
        finally:
            session.close()
            quiet.close()
        # Raised outside the handler so the original exception is not attached
        # as context to the public failure.
        raise failure
