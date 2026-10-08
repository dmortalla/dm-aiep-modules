"""Real LangFuse OTLP API serialization over a sealed offline HTTP boundary."""

import json
import logging
import math
from dataclasses import dataclass, field
from importlib.metadata import version
from uuid import uuid4

import httpx

from ..evaluation.ragas_adapter import EvaluationResult
from ..telemetry.latency import LatencyReport
from .failure_analysis import (
    FailureAnalysis,
    MonitoringIntegrationError,
    Stage,
    analyze_failure,
)

logger = logging.getLogger(__name__)
_ENDPOINT = "https://langfuse.invalid"


class MonitoringInputError(ValueError):
    """Supply validated upstream evidence and bounded annotations."""


class OfflineMonitoringTransport(httpx.BaseTransport):
    """Capture real SDK HTTP bodies with no socket or external destination.

    Args:
        failure: Optional trusted exception fixture for integration tests.
        status_code: Trusted HTTP response fixture.
        response: Trusted response fixture, excluded from monitoring evidence.
    """

    def __init__(
        self,
        failure: Exception | None = None,
        *,
        status_code: int = 200,
        response: dict | None = None,
    ) -> None:
        self.records: list[dict] = []
        self.failure = failure
        self.status_code = status_code
        self.response = {} if response is None else response

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Reject every destination except the exact fixed monitoring endpoint.

        Raises:
            RuntimeError: For an unexpected method or destination.
            Exception: The application-injected failure fixture.
        """
        if (
            str(request.url) != _ENDPOINT + "/api/public/otel/v1/traces"
            or request.method != "POST"
        ):
            raise RuntimeError("Offline monitoring destination rejected.")
        self.records.append(json.loads(request.content))
        if self.failure is not None:
            raise self.failure
        return httpx.Response(self.status_code, json=self.response, request=request)


@dataclass(frozen=True, slots=True)
class MonitoringEvidence:
    """Local evidence and SDK completion; never a remote delivery claim.

    Success means the offline SDK request completed, independently of any
    workflow failure. Exception causes remain local and must not be rendered.

    Raises:
        MonitoringInputError: For invalid evidence or inconsistent outcomes.
    """

    sdk_version: str
    success: bool
    latency: LatencyReport = field(repr=False)
    evaluation: EvaluationResult | None = field(repr=False)
    workflow_failure: FailureAnalysis | None
    monitoring_failure: FailureAnalysis | None = None
    error: MonitoringIntegrationError | None = field(default=None, repr=False)
    evidence_kind: str = field(default="deterministic_offline", init=False)
    remote_delivery_verified: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Validate outcome consistency without rendering source evidence."""
        if (
            type(self.sdk_version) is not str
            or not self.sdk_version
            or type(self.success) is not bool
            or type(self.latency) is not LatencyReport
            or (
                self.evaluation is not None
                and type(self.evaluation) is not EvaluationResult
            )
            or (
                self.workflow_failure is not None
                and type(self.workflow_failure) is not FailureAnalysis
            )
            or (
                self.monitoring_failure is not None
                and type(self.monitoring_failure) is not FailureAnalysis
            )
            or (
                self.error is not None
                and type(self.error) is not MonitoringIntegrationError
            )
        ):
            raise MonitoringInputError("Retain validated monitoring evidence.")
        if self.success:
            if self.monitoring_failure is not None or self.error is not None:
                raise MonitoringInputError(
                    "Successful SDK completion has no SDK error."
                )
        elif (
            self.monitoring_failure is None
            or self.error is None
            or self.monitoring_failure.stage is not Stage.OBSERVABILITY
        ):
            raise MonitoringInputError(
                "Failed SDK completion requires safe error facts."
            )


class LangFuseMonitor:
    """Explicit offline LangFuse public API client; no ambient SDK authority.

    Args:
        transport: Exact application-owned offline transport.

    Raises:
        MonitoringInputError: For a different transport type.
    """

    def __init__(self, transport: OfflineMonitoringTransport) -> None:
        if type(transport) is not OfflineMonitoringTransport:
            raise MonitoringInputError("Supply the sealed offline transport.")
        self._transport = transport

    def monitor(
        self,
        latency: LatencyReport,
        evaluation: EvaluationResult | None = None,
        *,
        failure: FailureAnalysis | None = None,
        result_available: bool = False,
        metadata: dict[str, str] | None = None,
        tags: tuple[str, ...] = (),
    ) -> MonitoringEvidence:
        """Export structural evidence through genuine LangFuse OTLP SDK methods.

        Args:
            latency: Story 6 evidence, retained locally by identity.
            evaluation: Optional Story 7 evidence, retained by identity.
            failure: Optional sanitized application-owned failure facts.
            result_available: Explicit application fact that an answer exists.
            metadata: Bounded untrusted strings, excluded entirely.
            tags: Bounded untrusted strings, excluded entirely.

        Returns:
            SDK execution evidence; integration failures are nonfatal.

        Raises:
            MonitoringInputError: For malformed evidence or annotations.
        """
        if (
            type(latency) is not LatencyReport
            or (evaluation is not None and type(evaluation) is not EvaluationResult)
            or (failure is not None and type(failure) is not FailureAnalysis)
            or type(result_available) is not bool
        ):
            raise MonitoringInputError("Supply validated workflow evidence.")
        if not math.isfinite(latency.total_seconds) or latency.total_seconds > 1e10:
            raise MonitoringInputError("Require finite timing within OTLP bounds.")
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
            raise MonitoringInputError("Supply bounded string metadata.")
        if (
            type(tags) is not tuple
            or len(tags) > 32
            or any(type(t) is not str or len(t) > 256 for t in tags)
        ):
            raise MonitoringInputError("Supply bounded string tags.")
        # Lazy public SDK/API imports initialize no background tracing client.
        from langfuse.api.client import LangfuseAPI
        from langfuse.api.opentelemetry.types import (
            OtelAttribute,
            OtelAttributeValue,
            OtelResource,
            OtelResourceSpan,
            OtelScope,
            OtelScopeSpan,
            OtelSpan,
        )

        sdk_version = version("langfuse")

        def attribute(key: str, value: str | float | bool | int) -> OtelAttribute:
            # Native LangFuse metadata namespace, as used by its observation SDK.
            if key != "service.name" and not key.startswith("langfuse."):
                key = "langfuse.observation.metadata." + key
            if type(value) is str:
                wrapped = OtelAttributeValue(string_value=value)
            elif type(value) is bool:
                wrapped = OtelAttributeValue(bool_value=value)
            elif type(value) is int:
                wrapped = OtelAttributeValue(int_value=value)
            else:
                wrapped = OtelAttributeValue(double_value=value)
            return OtelAttribute(key=key, value=wrapped)

        attributes = [
            attribute("langfuse.observation.type", "span"),
            attribute("evidence_kind", "deterministic_offline"),
            attribute("remote_delivery_verified", False),
            attribute("total_seconds", latency.total_seconds),
        ]
        if evaluation is not None:
            for name in ("faithfulness", "context_precision", "response_relevancy"):
                attributes.append(attribute(name, getattr(evaluation.scores, name)))
            attributes.append(
                attribute("evaluation_evidence_kind", evaluation.evidence_kind)
            )
        if failure is not None:
            attributes.extend(
                [
                    attribute("failure_stage", failure.stage.value),
                    attribute("failure_category", failure.category.value),
                    attribute("failure_fatal", failure.fatal),
                    attribute("result_usable", failure.result_usable),
                ]
            )
        trace_id, root_id = uuid4().hex, uuid4().hex[:16]
        # Fixed epoch anchor is synthetic, not a claim about real execution time.
        anchor = 1_700_000_000_000_000_000
        spans = [
            OtelSpan(
                trace_id=trace_id,
                span_id=root_id,
                name="module-4-workflow",
                kind=1,
                start_time_unix_nano=str(anchor),
                end_time_unix_nano=str(anchor + int(latency.total_seconds * 1e9)),
                attributes=attributes,
            )
        ]
        elapsed = 0
        for timing in latency.stages:
            duration = int(timing.elapsed_seconds * 1e9)
            spans.append(
                OtelSpan(
                    trace_id=trace_id,
                    span_id=uuid4().hex[:16],
                    parent_span_id=root_id,
                    name="measured-stage",
                    kind=1,
                    start_time_unix_nano=str(anchor + elapsed),
                    end_time_unix_nano=str(anchor + elapsed + duration),
                    attributes=[
                        attribute("langfuse.observation.type", "span"),
                        attribute("sequence", timing.sequence),
                        attribute("elapsed_seconds", timing.elapsed_seconds),
                    ],
                )
            )
            elapsed += duration
        resource = OtelResourceSpan(
            resource=OtelResource(
                attributes=[attribute("service.name", "module-4-offline")]
            ),
            scope_spans=[
                OtelScopeSpan(
                    scope=OtelScope(name="module-4-langfuse", version=sdk_version),
                    spans=spans,
                )
            ],
        )
        try:
            with httpx.Client(
                transport=self._transport,
                trust_env=False,
                follow_redirects=False,
                timeout=1,
            ) as http:
                client = LangfuseAPI(
                    base_url=_ENDPOINT,
                    username="offline-public",
                    password="offline-no-secret",
                    httpx_client=http,
                    headers={"x-langfuse-ingestion-version": "4"},
                )
                # SDK response is discarded: it never authorizes workflow decisions.
                client.opentelemetry.export_traces(
                    resource_spans=[resource],
                    request_options={"max_retries": 0, "timeout_in_seconds": 1},
                )
        except Exception as exc:
            # Catch at the optional external integration boundary only.
            try:
                raise MonitoringIntegrationError(
                    "LangFuse monitoring failed; inspect the offline boundary."
                ) from exc
            except MonitoringIntegrationError as error:
                category_error = (
                    TimeoutError() if isinstance(exc, httpx.TimeoutException) else error
                )
                analysis = analyze_failure(
                    Stage.OBSERVABILITY,
                    category_error,
                    result_available=result_available,
                )
                logger.warning(
                    "LangFuse monitoring failed; upstream evidence retained."
                )
                return MonitoringEvidence(
                    sdk_version, False, latency, evaluation, failure, analysis, error
                )
        return MonitoringEvidence(sdk_version, True, latency, evaluation, failure)
