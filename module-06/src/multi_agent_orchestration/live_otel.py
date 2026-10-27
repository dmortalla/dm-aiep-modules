"""Explicit finalized live projection into the existing local OTel boundary.

No transport, workflow hooks, globals, credentials, queues or model calls.
This infrastructure function owns neither execution nor acceptance evidence.
"""

import asyncio
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from .live_observation import LiveTerminalObservation, checked_observation
from .observability import Observability
from .observability_adapters import LocalOpenTelemetry

MAX_ATTEMPTS = 32
MAX_TIMESTAMP_NS = (1 << 64) - 1  # OTLP fixed64 nanoseconds, no datetime conversion.
ROLE_NAMES = ("Researcher", "Analyst", "Critic")


@dataclass(frozen=True)
class LiveOTelResult:
    """Local collection result only; failed attempts may leave partial spans."""

    trace_id: UUID | None
    status: Literal["recorded", "refused", "failed"]
    failure: (
        Literal[
            "invalid_observation",
            "busy",
            "closed",
            "already_attempted",
            "capacity_spent",
            "sdk_disabled",
            "collection_failed",
        ]
        | None
    ) = None
    planned_spans: int = 0
    evidence_class: Literal["local_sdk_collection"] = "local_sdk_collection"


def project_live_observation(
    observer: Observability, trace_id: UUID, *, adapter: LocalOpenTelemetry
) -> LiveOTelResult:
    """Project a retained terminal once per adapter, after workflow return.

    At most 32 lifetime attempts and four spans per attempt, no replay eviction.
    Admission never waits for concurrent adapter work. Only the built-in local
    adapter is supported; replacing its private provider/exporter with blocking
    plugins is outside this contract. There is no I/O or cancellable late work.
    """
    if type(adapter) is not LocalOpenTelemetry:
        return LiveOTelResult(None, "refused", "invalid_observation")
    if not adapter._lock.acquire(blocking=False):
        return LiveOTelResult(None, "refused", "busy")
    try:
        if adapter._closed:
            return LiveOTelResult(None, "refused", "closed")
        if type(observer) is not Observability or type(trace_id) is not UUID:
            return LiveOTelResult(None, "refused", "invalid_observation")
        if not observer._lock.acquire(blocking=False):
            return LiveOTelResult(None, "refused", "busy")
        try:
            try:
                terminal = next(
                    item
                    for item in observer.live_terminal_records
                    if item.trace_id == trace_id
                )
            finally:
                observer._lock.release()
            if type(terminal) is not LiveTerminalObservation:
                raise ValueError
            checked = checked_observation(LiveTerminalObservation, terminal)
            checked = LiveTerminalObservation.model_validate_json(
                checked.model_dump_json()
            )
            if checked.ended_ns > MAX_TIMESTAMP_NS:
                raise ValueError
        except (Exception, asyncio.CancelledError):
            return LiveOTelResult(None, "refused", "invalid_observation")
        count = 1 + len(checked.roles)
        if trace_id in adapter._live_attempted:
            return LiveOTelResult(trace_id, "refused", "already_attempted", count)
        if len(adapter._live_attempted) >= MAX_ATTEMPTS:
            return LiveOTelResult(trace_id, "refused", "capacity_spent", count)
        adapter._live_attempted.add(trace_id)
        token = adapter._identity.set((trace_id.int, int(checked.span_id, 16)))
        try:
            from opentelemetry.context import Context
            from opentelemetry.trace import Status, StatusCode, set_span_in_context

            attributes = {
                "observation": "live_terminal",
                "evidence_source": checked.evidence_source.value,
                "runtime": checked.runtime.value,
                "topology": checked.topology.value,
                "outcome": checked.outcome.value,
                "cleanup": checked.facts.cleanup.value,
                "duration_ms": checked.duration_ms,
            }
            if checked.category is not None:
                attributes["category"] = checked.category.value
            if checked.facts.model_calls is not None:
                attributes["model_calls"] = checked.facts.model_calls
                attributes["repair_attempts"] = checked.facts.repair_attempts
            before = adapter._collection_failure_marker
            root = adapter._tracer.start_span(
                "module6.workflow",
                context=Context(),
                start_time=checked.started_ns,
                attributes=attributes,
                record_exception=False,
                set_status_on_exception=False,
            )
            if not root.is_recording():
                return LiveOTelResult(trace_id, "failed", "sdk_disabled", count)
            root.set_status(
                Status(
                    StatusCode.OK
                    if checked.outcome.value == "completed"
                    else StatusCode.ERROR
                )
            )
            parent = set_span_in_context(root, Context())
            root.end(end_time=checked.ended_ns)
            for role in checked.roles:
                adapter._identity.set((trace_id.int, int(role.span_id, 16)))
                child = adapter._tracer.start_span(
                    ROLE_NAMES[role.sequence - 1],
                    context=parent,
                    start_time=role.completed_ns,
                    attributes={
                        "observation": "validated_completion",
                        "role": role.role.value,
                        "sequence": role.sequence,
                        "model_calls": role.model_calls,
                        "repair_attempts": role.repair_attempts,
                    },
                    record_exception=False,
                    set_status_on_exception=False,
                )
                child.end(end_time=role.completed_ns)
            if adapter._collection_failure_marker is not before:
                return LiveOTelResult(trace_id, "failed", "collection_failed", count)
            return LiveOTelResult(trace_id, "recorded", planned_spans=count)
        except (Exception, asyncio.CancelledError):
            return LiveOTelResult(trace_id, "failed", "collection_failed", count)
        finally:
            adapter._identity.reset(token)
    finally:
        adapter._lock.release()
