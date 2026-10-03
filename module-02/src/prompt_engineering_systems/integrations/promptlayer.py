"""Bounded observability-only REST adapter; imports never acquire credentials.

Contracts checked against official documentation:
https://docs.promptlayer.com/reference/log-request
https://docs.promptlayer.com/reference/track-score
Logging uses synthetic Prompt Blueprints containing only Story 7 safe evidence.
Mock receipts are simulated, never proof of live storage. Caller-owned explicit
live mode is the only path that can contact PromptLayer; no automatic retries.
"""

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Literal, Self

import httpx
from pydantic import ConfigDict, Field, SecretStr, ValidationError, model_validator

from ..contracts import StrictContract, ValidationLimits
from ..errors import EvaluationError, StructuredOutputError
from ..evaluation.evidence import EvaluationReport, export_evidence
from ..structured.validation import parse_json_text

BASE_URL = "https://api.promptlayer.com"
LOG_PATH = "/log-request"
SCORE_PATH = "/rest/track-score"
type ContactMode = Literal["offline", "mocked", "live"]
type FailureCode = Literal[
    "configuration",
    "authentication",
    "permission",
    "rate_limit",
    "timeout",
    "connection",
    "http",
    "response",
    "budget",
]
type ScoreName = Literal[
    "completion", "structured_validity", "correctness", "safety_outcome"
]

_MESSAGES: dict[FailureCode, str] = {
    "configuration": "Correct bounded settings and explicit key/transport.",
    "authentication": "Authentication failed; check the caller-supplied key.",
    "permission": "PromptLayer denied access; check application account permissions.",
    "rate_limit": "Rate limit reached; application may retry later.",
    "timeout": "PromptLayer request timed out; retry later within application budgets.",
    "connection": "PromptLayer transport failed; check connectivity before retrying.",
    "http": "Unsupported HTTP status; inspect service availability.",
    "response": "Invalid or oversized response; verify the REST contract.",
    "budget": "Request/payload budget exhausted; reduce observability work.",
}


class PromptLayerError(ValueError):
    """Fixed content-safe failure classification; no remote messages or SDK objects."""

    def __init__(self, code: FailureCode) -> None:
        """Create an actionable static error for an expected integration failure."""
        self.code = code
        super().__init__(_MESSAGES[code])


class PromptLayerConfiguration(StrictContract):
    """Trusted REST settings; offline is default and needs neither key nor transport.

    Attributes:
        base_url: Official HTTPS origin only; alternate hosts are unsupported.
        mode: Explicit transport provenance, independent of evaluation provenance.
        timeout_seconds: Finite timeout for each transport phase, 0.1..60 seconds.
        max_requests: Cumulative attempts for this adapter, 0..5; default five.
        max_response_bytes: Decoded response limit, 1..65,536; default 16 KiB.
        max_payload_bytes: Outbound sanitized JSON limit, 1..131,072.
    """

    model_config = ConfigDict(frozen=True)
    base_url: Literal["https://api.promptlayer.com"] = BASE_URL
    mode: ContactMode = "offline"
    timeout_seconds: float = Field(default=10.0, ge=0.1, le=60.0)
    max_requests: int = Field(default=5, ge=0, le=5)
    max_response_bytes: int = Field(default=16384, ge=1, le=65536)
    max_payload_bytes: int = Field(default=131072, ge=1, le=131072)


class LogWindow(StrictContract):
    """Explicit caller-owned UTC artifact timing, never fabricated model latency.

    Times identify the evaluation artifact window, not a measured LLM call.
    Years 2000..2100 and duration at most one hour keep metadata bounded.
    """

    model_config = ConfigDict(frozen=True)
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def bounded(self) -> Self:
        """Require ordered bounded aware UTC timestamps."""
        if any(
            value.tzinfo is None
            or value.utcoffset() != UTC.utcoffset(value)
            or not 2000 <= value.year <= 2100
            for value in (self.start, self.end)
        ):
            raise ValueError("Supply bounded aware UTC artifact timestamps.")
        if not 0 <= (self.end - self.start).total_seconds() <= 3600:
            raise ValueError("Supply an ordered artifact window of at most one hour.")
        return self


class Score(StrictContract):
    """Named deterministic percentage, integer 0..100 as required by REST.

    These are rounded fixture metric percentages, never calibrated confidence.
    No arbitrary names or metadata are accepted.
    """

    model_config = ConfigDict(frozen=True)
    name: ScoreName
    value: int = Field(ge=0, le=100)


class OperationResult(StrictContract):
    """Content-free observability state; transport origin is explicit."""

    model_config = ConfigDict(frozen=True)
    mode: ContactMode
    state: Literal["skipped", "succeeded", "failed"]
    remote_id: str | None = Field(default=None, max_length=18)
    failure: FailureCode | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        """Reject contradictory receipt states and unvalidated identifiers."""
        if self.remote_id is not None:
            _remote_id(self.remote_id)
        if (self.state == "skipped" and self.mode != "offline") or (
            self.mode == "offline" and self.state == "succeeded"
        ):
            raise ValueError("Offline operations cannot claim transport success.")
        if (self.state == "succeeded") != (self.remote_id is not None):
            raise ValueError("Only successful operations carry validated identifiers.")
        if (self.state == "failed") != (self.failure is not None):
            raise ValueError("Only failures carry a failure classification.")
        return self


class ScoreResult(StrictContract):
    """One bounded score plus its separate submission outcome."""

    model_config = ConfigDict(frozen=True)
    score: Score
    outcome: OperationResult


class ObservabilityOutcome(StrictContract):
    """Separate observability receipt; authoritative evaluation is never altered."""

    model_config = ConfigDict(frozen=True)
    correlation_id: str = Field(pattern=r"^eval-[0-9a-f]{64}$")
    evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    logging: OperationResult
    scores: tuple[ScoreResult, ...] = Field(default=(), max_length=4)


def _remote_id(value: str) -> str:
    if type(value) is not str or re.fullmatch(r"[1-9][0-9]{0,17}", value) is None:
        raise PromptLayerError("response")
    return value


def _validated_evidence(report: EvaluationReport) -> tuple[EvaluationReport, str]:
    try:
        checked = EvaluationReport.model_validate(report)
        return checked, export_evidence(checked)
    except (ValidationError, EvaluationError):
        raise PromptLayerError("configuration") from None


class PromptLayerAdapter:
    """Sequential session owner of bounded HTTP attempts and an explicit credential.

    Mocked mode requires injected httpx.MockTransport; live mode creates a transport
    with zero retries only on explicit live construction. Clients disable redirects,
    ambient environment settings and retries. Call close or use a context manager.
    Python application code owns transport selection; remote content cannot do so.
    """

    def __init__(
        self,
        configuration: PromptLayerConfiguration | None = None,
        *,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Configure an offline, mocked or explicitly live observability session.

        Args:
            configuration: Trusted bounded settings; offline defaults.
            api_key: Explicit key, 1..256 visible ASCII characters, never exported.
            transport: Injected MockTransport for mocked mode; None for offline/live.

        Raises:
            PromptLayerError: Invalid settings/key/transport, without sensitive details.
        """
        try:
            self._configuration = PromptLayerConfiguration.model_validate(
                configuration
                if configuration is not None
                else PromptLayerConfiguration()
            )
        except ValidationError:
            raise PromptLayerError("configuration") from None
        mode = self._configuration.mode
        self._client: httpx.Client | None = None
        self._key: SecretStr | None = None
        self._calls = 0
        if mode == "offline":
            if api_key is not None or transport is not None:
                raise PromptLayerError("configuration")
            return
        if (
            type(api_key) is not str
            or not 1 <= len(api_key) <= 256
            or any(not 33 <= ord(char) <= 126 for char in api_key)
        ):
            raise PromptLayerError("configuration")
        if mode == "mocked" and not isinstance(transport, httpx.MockTransport):
            raise PromptLayerError("configuration")
        if mode == "live" and transport is not None:
            raise PromptLayerError("configuration")
        self._key = SecretStr(api_key)
        self._client = httpx.Client(
            transport=transport
            if transport is not None
            else httpx.HTTPTransport(retries=0, trust_env=False),
            timeout=self._configuration.timeout_seconds,
            trust_env=False,
            follow_redirects=False,
        )

    @property
    def used_requests(self) -> int:
        """Return cumulative attempts including transport/response failures."""
        return self._calls

    @property
    def mode(self) -> ContactMode:
        """Return configured contact provenance, never evaluation provenance."""
        return self._configuration.mode

    def close(self) -> None:
        """Close owned client resources; performs no observability request."""
        if self._client is not None:
            self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _post(
        self, path: str, payload: dict[str, object], expected_status: int
    ) -> dict[str, object]:
        if self._calls >= self._configuration.max_requests:
            raise PromptLayerError("budget")
        encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode(
            "utf-8"
        )
        if len(encoded) > self._configuration.max_payload_bytes:
            raise PromptLayerError("budget")
        if self._client is None or self._key is None:
            raise PromptLayerError("configuration")
        self._calls += 1
        try:
            with self._client.stream(
                "POST",
                self._configuration.base_url + path,
                content=encoded,
                headers={
                    "X-API-KEY": self._key.get_secret_value(),
                    "Content-Type": "application/json",
                    "Accept-Encoding": "identity",
                },
                timeout=self._configuration.timeout_seconds,
                follow_redirects=False,
            ) as response:
                code = {
                    401: "authentication",
                    403: "permission",
                    429: "rate_limit",
                }.get(response.status_code)
                if code is not None:
                    raise PromptLayerError(code)
                if response.status_code != expected_status:
                    raise PromptLayerError("http")
                if response.headers.get("content-encoding", "identity") != "identity":
                    raise PromptLayerError("response")
                body = bytearray()
                # Mock responses can be preloaded; live streams stay raw so
                # compressed data cannot expand before the byte ceiling check.
                chunks = (
                    (response.content,)
                    if response.is_stream_consumed
                    else response.iter_raw(chunk_size=4096)
                )
                for chunk in chunks:
                    if len(body) + len(chunk) > self._configuration.max_response_bytes:
                        raise PromptLayerError("response")
                    body.extend(chunk)
        except httpx.TimeoutException:
            raise PromptLayerError("timeout") from None
        except httpx.TransportError:
            raise PromptLayerError("connection") from None
        try:
            value = parse_json_text(
                body.decode("utf-8"),
                limits=ValidationLimits(
                    max_text_bytes=self._configuration.max_response_bytes,
                    max_nodes=256,
                    max_depth=16,
                ),
            )
        except (UnicodeError, StructuredOutputError):
            raise PromptLayerError("response") from None
        if type(value) is not dict:
            raise PromptLayerError("response")
        return value

    def log(self, report: EvaluationReport, window: LogWindow) -> OperationResult:
        """Log a sanitized evaluation artifact with synthetic Prompt Blueprints.

        Args:
            report: Already validated Story 7 evidence; revalidated before contact.
            window: Explicit caller-owned artifact timestamps, not model latency.

        Returns:
            Skipped offline or validated transport receipt. Remote extras are discarded.

        Raises:
            PromptLayerError: Expected input/transport/status/response failure.
            Exception: Unexpected programming failures propagate unchanged.
        """
        checked, evidence = _validated_evidence(report)
        try:
            window = LogWindow.model_validate(window)
        except ValidationError:
            raise PromptLayerError("configuration") from None
        if self.mode == "offline":
            return OperationResult(mode="offline", state="skipped")
        digest = hashlib.sha256(evidence.encode("utf-8")).hexdigest()
        status = "SUCCESS" if checked.metrics.failed == 0 else "WARNING"
        payload: dict[str, object] = {
            "provider": "module-02-synthetic",
            "model": "evaluation-evidence-v1",
            "input": {
                "type": "chat",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Sanitized artifact; raw content omitted.",
                            }
                        ],
                    }
                ],
            },
            "output": {
                "type": "chat",
                "messages": [
                    {
                        "role": "assistant",
                        "content": [{"type": "text", "text": evidence}],
                    }
                ],
            },
            "request_start_time": window.start.isoformat(),
            "request_end_time": window.end.isoformat(),
            "status": status,
            "tags": ["module-02", "sanitized-evaluation"],
            "metadata": {
                "correlation_id": "eval-" + digest,
                "evidence_digest": digest,
                "timing_kind": "caller-owned-artifact-window",
                "contact_mode": self.mode,
                "evidence_modes": ",".join(
                    sorted({item.mode for item in checked.results})
                ),
            },
        }
        value = self._post(LOG_PATH, payload, 201)
        identity = value.get("id")
        if (
            type(identity) is not int
            or not 1 <= identity <= 999999999999999999
            or value.get("status") != status
        ):
            raise PromptLayerError("response")
        return OperationResult(
            mode=self.mode, state="succeeded", remote_id=_remote_id(str(identity))
        )

    def submit_score(self, remote_id: str, score: Score) -> OperationResult:
        """Submit a validated named integer score without changing local evaluation.

        Args:
            remote_id: Canonical positive decimal identifier, at most 18 digits.
            score: Approved deterministic metric percentage, integer 0..100.

        Returns:
            Skipped offline or validated score receipt for the same identifier.

        Raises:
            PromptLayerError: Invalid inputs or expected REST failure; no raw body.
        """
        identity = _remote_id(remote_id)
        try:
            score = Score.model_validate(score)
        except ValidationError:
            raise PromptLayerError("configuration") from None
        if self.mode == "offline":
            return OperationResult(mode="offline", state="skipped")
        value = self._post(
            SCORE_PATH,
            {"request_id": int(identity), "score": score.value, "name": score.name},
            200,
        )
        if value.get("success") is not True:
            raise PromptLayerError("response")
        return OperationResult(mode=self.mode, state="succeeded", remote_id=identity)


def observe_evaluation(
    report: EvaluationReport, adapter: PromptLayerAdapter, window: LogWindow
) -> ObservabilityOutcome:
    """Log accepted evidence and its existing metrics; keep partial failures explicit.

    Args:
        report: Authoritative Story 7 evidence, never changed by observability.
        adapter: Application-owned offline/mocked/explicit-live bounded REST session.
        window: Explicit artifact timestamps needed by the documented log endpoint.

    Returns:
        Separate logging and score receipts. Failed logging prevents scoring;
        a score failure preserves successful logging and other score outcomes.

    Raises:
        PromptLayerError: Invalid evidence before orchestration.
        Exception: Unexpected programming defects propagate unchanged.
    """
    checked, evidence = _validated_evidence(report)
    digest = hashlib.sha256(evidence.encode("utf-8")).hexdigest()
    try:
        logging = adapter.log(checked, window)
    except PromptLayerError as error:
        logging = OperationResult(mode=adapter.mode, state="failed", failure=error.code)
    results = []
    if logging.state == "succeeded":
        metrics = checked.metrics
        for name, rate in (
            ("completion", metrics.completion_rate),
            ("structured_validity", metrics.validity_rate),
            ("correctness", metrics.correctness_rate),
            ("safety_outcome", metrics.safety_rate),
        ):
            if rate is None:
                continue
            score = Score(name=name, value=round(rate * 100))
            try:
                outcome = adapter.submit_score(logging.remote_id, score)
            except PromptLayerError as error:
                outcome = OperationResult(
                    mode=adapter.mode, state="failed", failure=error.code
                )
            results.append(ScoreResult(score=score, outcome=outcome))
    return ObservabilityOutcome(
        correlation_id="eval-" + digest,
        evidence_digest=digest,
        logging=logging,
        scores=tuple(results),
    )
