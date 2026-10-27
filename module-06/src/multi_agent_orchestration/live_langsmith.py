"""Payload-free terminal projection and explicitly selected bounded delivery.

No workflow hooks, clients, inference, credential lookup or network effects occur
on import/projection. Projection lazily uses the installed SDK's pure formatter.
Delivery selects only retained finalized observations.
Neither projection nor a write response proves live vendor verification.
"""

import asyncio
import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib import import_module
from typing import Literal, Protocol
from uuid import UUID, uuid5

from .langsmith_delivery import (
    API_KEY_VARIABLE,
    PROJECT,
    ROOT_NAME,
    WRITE_URL,
    LangSmithDeliveryConfig,
    credential_format_valid,
    normalized_credential,
    status_category,
)
from .live_errors import LiveValidationError
from .live_observation import LiveTerminalObservation, checked_observation
from .observability import Observability
from .observability_contracts import Outcome

MAX_BATCH_BYTES = 8192
TIMEOUT_S = (5.0, 10.0)
DELIVERY_DEADLINE_S = 15.0
# Process-wide admission, including across delivery instances. No work queue and
# no replacement for a blocked worker: surviving I/O keeps its slot until exit.
_DELIVERY_SLOTS = threading.BoundedSemaphore(3)
TAGS = ("module6", "live-terminal-observation", "payload-free")
ROLE_NAMES = ("Researcher", "Analyst", "Critic")


@dataclass(frozen=True)
class LiveLangSmithProjection:
    """Immutable application projection; not execution or delivery evidence."""

    trace_id: UUID
    run_count: int
    batch: bytes


def project_live_observation(
    observation: LiveTerminalObservation,
) -> LiveLangSmithProjection:
    """Project a revalidated terminal snapshot into at most four fixed runs.

    Role timestamps are completion instants, never invented role latencies.
    Dotted-order timestamps are observed instants at SDK microsecond precision.
    A validated ordinal in each child UUID breaks precision ties without
    changing timestamps. Application span IDs and the root UUID are unchanged.
    Provider/model selection is validated but deliberately omitted.

    Args:
        observation: Exact application terminal contract, not a vendor trace.

    Returns:
        Bounded immutable JSON batch with empty inputs and outputs.

    Raises:
        LiveValidationError: Malformed data, unowned fields or unusable timing.
    """
    projection = None
    try:
        if type(observation) is not LiveTerminalObservation:
            raise ValueError("Terminal contract required.")
        checked = checked_observation(LiveTerminalObservation, observation)
        # Canonical JSON discards caller primitive identity/custom behavior.
        checked = LiveTerminalObservation.model_validate_json(checked.model_dump_json())

        def stamp(ns: int) -> datetime:
            return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(microseconds=ns // 1000)

        root_id = str(checked.trace_id)
        start, end = stamp(checked.started_ns), stamp(checked.ended_ns)

        # Installed SDK 0.14.3: timestamp + run UUID; no client or RunTree effects.
        order = import_module("langsmith.run_trees")._create_current_dotted_order
        root_order = order(start, checked.trace_id)

        def body(run_id, name, at, until, metadata):
            return {
                "id": run_id,
                "trace_id": root_id,
                "name": name,
                "run_type": "chain",
                "session_name": PROJECT,
                "start_time": at.isoformat(),
                "end_time": until.isoformat(),
                "inputs": {},
                "outputs": {},
                "events": [],
                "tags": [],
                "extra": {"metadata": metadata},
            }

        root = body(
            root_id,
            ROOT_NAME,
            start,
            end,
            {
                "module": "module-06",
                "observation": "live_terminal",
                "dotted_order_semantics": "observed_time_sequence_uuid",
                "evidence_source": checked.evidence_source.value,
                "runtime": checked.runtime.value,
                "topology": checked.topology.value,
                "workflow_id": str(checked.workflow_id),
                "task_id": str(checked.task_id),
                "span_id": checked.span_id,
                "outcome": checked.outcome.value,
                "category": (
                    None if checked.category is None else checked.category.value
                ),
                "model_calls": checked.facts.model_calls,
                "repair_attempts": checked.facts.repair_attempts,
                "transport_retries": checked.facts.transport_retries,
                "input_tokens": checked.facts.usage.input_tokens,
                "output_tokens": checked.facts.usage.output_tokens,
                "duration_ms": checked.duration_ms,
                "cleanup": checked.facts.cleanup.value,
            },
        )
        root["tags"], root["dotted_order"] = list(TAGS), root_order
        if checked.outcome != Outcome.COMPLETED:
            root["error"] = checked.outcome.value
        runs = [root]
        for role in checked.roles:
            seed = uuid5(checked.trace_id, "role:" + role.span_id)
            # The SDK suffix IS the run UUID, not a separate ordering token.
            # Reserve its first byte for the validated ordinal (01/02/03),
            # retaining the other 120 namespace/span-derived bits and UUID form.
            child_uuid = UUID(bytes=bytes((role.sequence,)) + seed.bytes[1:])
            child_id = str(child_uuid)
            at = stamp(role.completed_ns)
            child = body(
                child_id,
                ROLE_NAMES[role.sequence - 1],
                at,
                at,
                {
                    "observation": "validated_completion",
                    "dotted_order_semantics": "observed_time_sequence_uuid",
                    "role_sequence": role.sequence,
                    "span_id": role.span_id,
                    "model_calls": role.model_calls,
                    "repair_attempts": role.repair_attempts,
                },
            )
            child["parent_run_id"] = root_id
            child["dotted_order"] = root_order + "." + order(at, child_uuid)
            runs.append(child)
        if len({run["id"] for run in runs}) != len(runs):
            raise ValueError("Run identity collision.")
        batch = json.dumps(
            {"post": runs}, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        if len(batch) > MAX_BATCH_BYTES:
            raise ValueError("Batch exceeds bound.")
        projection = LiveLangSmithProjection(checked.trace_id, len(runs), batch)
    except (ValueError, TypeError, AttributeError, OverflowError, LiveValidationError):
        pass
    if projection is None:
        raise LiveValidationError() from None
    return projection


class LiveBatchTransport(Protocol):
    """Trusted one-shot bounded infrastructure; injected transports are synthetic."""

    def write(self, batch: bytes) -> int:
        """Write one batch without retries; return only the HTTP status."""
        ...


def _bounded_write(write, batch: bytes) -> int:
    """Bound caller latency and surviving work, including DNS and injected I/O.

    Python cannot safely cancel arbitrary blocking threads. At most three daemon
    workers may survive a deadline process-wide; saturation fails immediately.
    A worker owns only its bounded batch and private completion cell, never any
    observer, replay set or returned evidence. Late results are discarded.
    """
    if type(batch) is not bytes or len(batch) > MAX_BATCH_BYTES:
        raise LiveValidationError() from None
    deadline = time.monotonic() + DELIVERY_DEADLINE_S
    if not _DELIVERY_SLOTS.acquire(blocking=False):
        raise RuntimeError() from None
    completed = threading.Event()
    result = [None, "transport_failed"]

    def execute():
        try:
            status = write(batch)
            # Retain no arbitrary transport-owned object or diagnostic.
            if type(status) is int:
                result[0] = status
            else:
                result[1] = "unexpected_response"
        except TimeoutError:
            result[1] = "timed_out"
        except BaseException:
            pass
        finally:
            _DELIVERY_SLOTS.release()
            completed.set()

    worker = threading.Thread(target=execute, name="module6-delivery", daemon=True)
    try:
        worker.start()
    except BaseException:
        _DELIVERY_SLOTS.release()
        raise RuntimeError() from None
    if (
        not completed.wait(max(0.0, deadline - time.monotonic()))
        or time.monotonic() >= deadline
    ):
        raise TimeoutError() from None
    if result[0] is not None:
        return result[0]
    if result[1] == "timed_out":
        raise TimeoutError() from None
    if result[1] == "unexpected_response":
        return False
    raise RuntimeError() from None


class _ProductionTransport:
    def write(self, batch: bytes) -> int:
        return _bounded_write(self._request, batch)

    def _request(self, batch: bytes) -> int:
        # Reachable only after explicit config, finalized lookup and budget claim.
        import requests

        raw = os.environ.get(API_KEY_VARIABLE)
        if not credential_format_valid(raw):
            raise LiveValidationError() from None
        with requests.Session() as session:
            session.trust_env = False
            session.max_redirects = 0
            # Requests' default adapters have zero retries. No SDK/background queue.
            try:
                reply = session.post(
                    WRITE_URL,
                    data=batch,
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": normalized_credential(raw),
                    },
                    timeout=TIMEOUT_S,
                    allow_redirects=False,
                    stream=True,
                )
            except requests.Timeout:
                raise TimeoutError() from None
            try:
                return reply.status_code
            finally:
                reply.close()  # Never read/log/retain reply content or headers.


DeliveryFailure = Literal[
    "refused",
    "invalid_observation",
    "budget_spent",
    "already_attempted",
    "transport_failed",
    "timed_out",
    "authentication_rejected",
    "authorization_rejected",
    "request_rejected",
    "rate_limited",
    "service_failed",
    "unexpected_response",
]


@dataclass(frozen=True)
class LiveLangSmithDeliveryResult:
    """Separate observational result; never changes application evidence.

    Accepted means only that the transport returned a 2xx status. Injected
    transports always remain synthetic; production responses are unverified.
    No state can claim live vendor verification or reinterpret execution source.
    """

    trace_id: UUID | None
    status: Literal["refused", "failed", "accepted"]
    evidence_class: Literal["not_sent", "synthetic_transport", "unverified_write"]
    failure: DeliveryFailure | None = None
    planned_runs: int = 0
    write_attempts: int = 0


class LiveLangSmithDelivery:
    """Explicit post-workflow delivery, no hooks into inference or its deadline.

    Args:
        config: Explicit operator selection; missing/forged configuration refuses.
        transport: Optional trusted bounded fake; always classified synthetic.

    At most three lifetime attempts, one write per trace, no retries/readback,
    no queued work or retained completed payloads/results. Timed-out I/O is
    globally limited to three daemon workers. The small attempt set
    is never evicted, preventing automatic replay after failed writes.
    """

    def __init__(
        self,
        config: LangSmithDeliveryConfig | None = None,
        *,
        transport: LiveBatchTransport | None = None,
    ) -> None:
        self._limit = 0
        try:
            if type(config) is LangSmithDeliveryConfig and set(config.__dict__) == set(
                LangSmithDeliveryConfig.model_fields
            ):
                self._limit = LangSmithDeliveryConfig.model_validate(
                    dict(config.__dict__)
                ).max_traces
        except (ValueError, TypeError, AttributeError):
            pass
        self._transport = transport
        self._attempted: set[UUID] = set()
        self._lock = threading.Lock()

    def deliver(
        self,
        observer: Observability,
        trace_id: UUID,
    ) -> LiveLangSmithDeliveryResult:
        """Select a finalized retained trace, then claim one bounded write attempt.

        Args:
            observer: Application-owned Slice 1 retention after workflow return.
            trace_id: Exact trusted UUID selecting a retained terminal observation.

        Returns:
            Safe separate delivery result, including failures without diagnostics.
        """
        if not self._limit:
            return LiveLangSmithDeliveryResult(None, "refused", "not_sent", "refused")
        projection = None
        try:
            if type(observer) is not Observability or type(trace_id) is not UUID:
                raise ValueError("Owned retention and UUID required.")
            terminal = next(
                item
                for item in observer.live_terminal_records
                if item.trace_id == trace_id
            )
            projection = project_live_observation(terminal)
        except (
            ValueError,
            TypeError,
            AttributeError,
            StopIteration,
            LiveValidationError,
        ):
            pass
        if projection is None:
            return LiveLangSmithDeliveryResult(
                None, "refused", "not_sent", "invalid_observation"
            )
        with self._lock:
            failure = (
                "already_attempted"
                if trace_id in self._attempted
                else "budget_spent"
                if len(self._attempted) >= self._limit
                else None
            )
            if failure:
                return LiveLangSmithDeliveryResult(
                    trace_id, "refused", "not_sent", failure, projection.run_count
                )
            self._attempted.add(trace_id)
        evidence = (
            "synthetic_transport"
            if self._transport is not None
            else "unverified_write"
        )
        category = "transport_failed"
        status = None
        try:
            transport = (
                self._transport
                if self._transport is not None
                else _ProductionTransport()
            )
            status = (
                transport.write(projection.batch)
                if self._transport is None
                else _bounded_write(transport.write, projection.batch)
            )
        except TimeoutError:
            category = "timed_out"
        except (Exception, asyncio.CancelledError):
            pass  # Exception text/context cannot escape this boundary.
        if type(status) is int and 200 <= status <= 299:
            return LiveLangSmithDeliveryResult(
                trace_id, "accepted", evidence, None, projection.run_count, 1
            )
        if status is not None:
            category = (
                status_category(status)
                if type(status) is int and 400 <= status <= 599
                else "unexpected_response"
            )
        return LiveLangSmithDeliveryResult(
            trace_id, "failed", evidence, category, projection.run_count, 1
        )
