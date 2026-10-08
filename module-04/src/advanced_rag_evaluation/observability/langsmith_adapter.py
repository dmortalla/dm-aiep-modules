"""Genuine LangSmith runs with an offline transport and content exclusion.

Only numeric summaries cross the telemetry boundary. Original evidence remains
local, by identity. No prompt, answer, chunk text, identifier, tag, metadata,
judge response, stage name, or exception message is transmitted.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

import requests
from requests.adapters import BaseAdapter

from ..evaluation.ragas_adapter import EvaluationResult
from ..telemetry.latency import LatencyReport

logger = logging.getLogger(__name__)
_ENDPOINT = "https://langsmith.invalid"


class TraceInputError(ValueError):
    """Trace evidence does not match the accepted local contracts."""


class TraceIntegrationError(RuntimeError):
    """The genuine SDK failed; original cause retained but never logged."""


class OfflineTransport(BaseAdapter):
    """Capture serialized SDK requests without opening any socket.

    Args:
        failure: Optional application-injected transport failure for tests.
    """

    def __init__(self, failure: Exception | None = None) -> None:
        self.records: list[tuple[str, str, dict]] = []
        self.failure = failure

    def send(
        self, request: requests.PreparedRequest, **kwargs: object
    ) -> requests.Response:
        """Accept only the fixed offline runs endpoint; return a fixture response.

        Raises:
            RuntimeError: For an unexpected SDK destination or method.
            Exception: The explicitly injected transport failure.
        """
        if (
            request.url is None
            or not request.url.startswith(_ENDPOINT + "/runs")
            or request.method not in ("POST", "PATCH")
        ):
            raise RuntimeError("Offline transport rejected an unexpected request.")
        if self.failure is not None:
            raise self.failure
        payload = json.loads(request.body)
        self.records.append((request.method, request.url, payload))
        response = requests.Response()
        response.status_code = 200
        response._content = b"{}"
        response.request = request
        return response

    def close(self) -> None:
        """No sockets or background resources exist to close."""


@dataclass(frozen=True, slots=True)
class TraceEvidence:
    """Local provenance and truthful SDK execution evidence.

    No success value attests remote delivery. Offline requests are inspectable
    on the transport; an unsuccessful call may have emitted a partial workflow.
    """

    run_id: UUID
    child_ids: tuple[UUID, ...]
    sdk_version: str
    success: bool
    latency: LatencyReport = field(repr=False)
    evaluation: EvaluationResult | None = field(repr=False)
    failure: TraceIntegrationError | None = field(default=None, repr=False)
    evidence_kind: str = field(default="deterministic_offline", init=False)
    remote_delivery_verified: bool = field(default=False, init=False)


class LangSmithTracer:
    """Explicit offline SDK tracing, independent of ambient tracing settings.

    Args:
        transport: Application-owned offline transport; never selected by data.

    Raises:
        TraceInputError: For a transport other than the exact offline boundary.
    """

    def __init__(self, transport: OfflineTransport) -> None:
        if type(transport) is not OfflineTransport:
            raise TraceInputError("Supply the application-owned offline transport.")
        from langsmith import Client, __version__

        session = requests.Session()
        session.trust_env = False
        session.mount("https://", transport)
        session.mount("http://", transport)
        self._client = Client(
            api_url=_ENDPOINT,
            api_key="offline-fixture-no-secret",
            session=session,
            auto_batch_tracing=False,
            timeout_ms=1000,
            omit_traced_runtime_info=True,
            tracing_sampling_rate=1.0,
            info={"version": "offline"},
        )
        # Client installs its own adapters during initialization.
        session.mount("https://", transport)
        session.mount("http://", transport)
        self._version = __version__

    def trace(
        self,
        latency: LatencyReport,
        evaluation: EvaluationResult | None = None,
        *,
        metadata: dict[str, str] | None = None,
        tags: tuple[str, ...] = (),
    ) -> TraceEvidence:
        """Emit a root workflow and ordered children through real SDK methods.

        Args:
            latency: Accepted Story 6 report, retained unchanged locally.
            evaluation: Optional accepted Story 7 result, retained unchanged.
            metadata: Untrusted annotations, validated and excluded entirely.
            tags: Untrusted tags, validated and excluded entirely.

        Returns:
            Offline evidence, including nonfatal sanitized integration failure.

        Raises:
            TraceInputError: For malformed evidence or annotation shape.
        """
        if type(latency) is not LatencyReport or (
            evaluation is not None and type(evaluation) is not EvaluationResult
        ):
            raise TraceInputError("Supply accepted latency/evaluation evidence.")
        if metadata is not None and (
            type(metadata) is not dict
            or len(metadata) > 32
            or any(
                type(k) is not str
                or type(v) is not str
                or len(k) > 256
                or len(v) > 1024
                for k, v in metadata.items()
            )
        ):
            raise TraceInputError("Supply bounded string metadata; it is excluded.")
        if (
            type(tags) is not tuple
            or len(tags) > 32
            or any(type(tag) is not str or len(tag) > 256 for tag in tags)
        ):
            raise TraceInputError("Supply bounded string tags; they are excluded.")
        root = uuid4()
        children = tuple(uuid4() for _ in latency.stages)
        summary = {"total_seconds": latency.total_seconds}
        if evaluation is not None:
            summary.update(
                faithfulness=evaluation.scores.faithfulness,
                context_precision=evaluation.scores.context_precision,
                response_relevancy=evaluation.scores.response_relevancy,
                evaluation_evidence_kind=evaluation.evidence_kind,
            )
        try:
            self._client.create_run(
                "module-4-workflow",
                {},
                "chain",
                id=root,
                project_name="module-4-offline",
                start_time=datetime.now(UTC),
            )
            for child, timing in zip(children, latency.stages, strict=True):
                self._client.create_run(
                    "measured-stage",
                    {"sequence": timing.sequence},
                    "chain",
                    id=child,
                    parent_run_id=root,
                    project_name="module-4-offline",
                    start_time=datetime.now(UTC),
                )
                self._client.update_run(
                    child,
                    outputs={"elapsed_seconds": timing.elapsed_seconds},
                    end_time=datetime.now(UTC),
                )
            self._client.update_run(root, outputs=summary, end_time=datetime.now(UTC))
        except Exception as exc:
            # Preserve causal context without emitting credentials/payload/errors.
            try:
                raise TraceIntegrationError(
                    "LangSmith tracing failed; inspect the application transport."
                ) from exc
            except TraceIntegrationError as failure:
                logger.warning("LangSmith tracing failed; workflow evidence retained.")
                return TraceEvidence(
                    root, children, self._version, False, latency, evaluation, failure
                )
        return TraceEvidence(root, children, self._version, True, latency, evaluation)
