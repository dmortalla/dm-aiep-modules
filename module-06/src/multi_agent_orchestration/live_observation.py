"""Payload-free live observation siblings; no SDK, transport or authority."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .canonical_contracts import EvidenceSource
from .contracts import GraphRole, GraphTopology, RuntimeId
from .live_contracts import (
    LIVE_ROLES,
    MAX_DEADLINE_MS,
    CanonicalUUID,
    LiveContract,
    ModelSelection,
    ModelUsage,
)
from .live_errors import LiveFailureCategory, LiveValidationError
from .observability_contracts import Outcome, SpanId

Calls = Annotated[int, Field(strict=True, ge=0, le=4)]
Repairs = Annotated[int, Field(strict=True, ge=0, le=1)]
Stamp = Annotated[int, Field(strict=True, ge=1)]
# Work is bounded at 300 s; independent supervisor reaping may add 2 s.
Duration = Annotated[float, Field(strict=True, ge=0, le=MAX_DEADLINE_MS + 2000)]


class CleanupState(StrEnum):
    NOT_STARTED = "not_started"
    REAPED = "reaped"
    FAILED = "failed"
    UNKNOWN = "unknown"


class LiveRuntimeFacts(LiveContract):
    """Supervisor facts, including dispatch attempts, not provider completions."""

    model_calls: Calls | None
    repair_attempts: Repairs | None
    transport_retries: Annotated[int, Field(strict=True, ge=0, le=0)] = 0
    usage: ModelUsage = Field(default_factory=ModelUsage)
    cleanup: CleanupState

    @model_validator(mode="after")
    def accounting(self):
        if (self.model_calls is None) != (self.repair_attempts is None):
            raise ValueError("Accounting availability must be paired.")
        if self.model_calls is None:
            if self.cleanup != CleanupState.UNKNOWN or self.usage != ModelUsage():
                raise ValueError("Unknown accounting cannot invent usage or cleanup.")
            return self
        if (
            (self.repair_attempts and self.model_calls < 2)
            or self.model_calls > 3 + self.repair_attempts
            or (self.cleanup == CleanupState.NOT_STARTED and self.model_calls != 0)
            or (self.model_calls == 0 and self.usage != ModelUsage())
        ):
            raise ValueError("Inconsistent supervisor accounting.")
        return self


class LiveObservationIdentity(LiveContract):
    workflow_id: CanonicalUUID
    task_id: CanonicalUUID
    trace_id: CanonicalUUID
    span_id: SpanId
    evidence_source: EvidenceSource
    started_ns: Stamp

    @model_validator(mode="after")
    def nonzero(self):
        if self.trace_id.int == 0 or int(self.span_id, 16) == 0:
            raise ValueError("Observation identity must be nonzero.")
        return self


class LiveRoleCompletion(LiveContract):
    """Validated completion at one instant; never a claim of role latency."""

    role: Literal[GraphRole.RESEARCHER, GraphRole.ANALYST, GraphRole.CRITIC]
    sequence: Annotated[int, Field(strict=True, ge=1, le=3)]
    span_id: SpanId
    completed_ns: Stamp
    model_calls: Calls
    repair_attempts: Repairs

    @model_validator(mode="after")
    def completion(self):
        if (
            self.role != LIVE_ROLES[self.sequence - 1]
            or self.model_calls != self.sequence + self.repair_attempts
            or int(self.span_id, 16) == 0
        ):
            raise ValueError("Inconsistent role completion.")
        return self


class LiveTerminalObservation(LiveObservationIdentity):
    """Application facts only; deterministic RunTrace retains its zero-call rules."""

    runtime: Literal[RuntimeId.LANGGRAPH] = RuntimeId.LANGGRAPH
    topology: Literal[GraphTopology.SEQUENTIAL] = GraphTopology.SEQUENTIAL
    outcome: Outcome
    category: LiveFailureCategory | None = None
    selection: ModelSelection | None = None
    roles: Annotated[tuple[LiveRoleCompletion, ...], Field(max_length=3)] = ()
    facts: LiveRuntimeFacts
    ended_ns: Stamp
    duration_ms: Duration

    @model_validator(mode="after")
    def terminal(self):
        refused = (
            LiveFailureCategory.AUTHORIZATION_REFUSED,
            LiveFailureCategory.BUDGET_REFUSED,
        )
        expected = (
            Outcome.TIMED_OUT
            if self.category == LiveFailureCategory.TIMED_OUT
            else Outcome.DENIED
            if self.category in refused
            else Outcome.FAILED
            if self.category is not None
            else self.outcome
        )
        stamps = [self.started_ns, *(r.completed_ns for r in self.roles), self.ended_ns]
        spans = [self.span_id, *(r.span_id for r in self.roles)]
        if (
            self.outcome != expected
            or (
                self.outcome in (Outcome.FAILED, Outcome.TIMED_OUT)
                and self.category is None
            )
            or (
                self.outcome in (Outcome.COMPLETED, Outcome.CANCELLED)
                and self.category is not None
            )
            or stamps != sorted(stamps)
            or len(set(spans)) != len(spans)
            or tuple(r.sequence for r in self.roles)
            != tuple(range(1, len(self.roles) + 1))
            or (
                self.facts.model_calls is not None
                and any(
                    r.model_calls > self.facts.model_calls
                    or r.repair_attempts > self.facts.repair_attempts
                    for r in self.roles
                )
            )
            or any(
                a.model_calls >= b.model_calls or a.repair_attempts > b.repair_attempts
                for a, b in zip(self.roles, self.roles[1:], strict=False)
            )
            or (self.selection is None and (self.roles or self.facts.model_calls))
            or (
                self.selection is not None
                and (
                    self.selection.provider != "ollama"
                    or self.selection.model != "qwen2.5-coder:7b"
                )
            )
        ):
            raise ValueError("Inconsistent terminal observation.")
        if self.outcome == Outcome.COMPLETED and (
            len(self.roles) != 3
            or self.selection is None
            or self.facts.cleanup != CleanupState.REAPED
            or self.facts.model_calls is None
            or self.facts.model_calls != 3 + self.facts.repair_attempts
            or self.roles[-1].model_calls != self.facts.model_calls
            or self.roles[-1].repair_attempts != self.facts.repair_attempts
            or self.duration_ms > MAX_DEADLINE_MS
        ):
            raise ValueError("Completion requires validated roles and cleanup.")
        if self.outcome == Outcome.DENIED and (
            self.roles
            or self.facts.model_calls
            or self.facts.repair_attempts
            or self.facts.cleanup != CleanupState.NOT_STARTED
        ):
            raise ValueError("Denial cannot invent execution facts.")
        return self


_SCHEMAS = (
    LiveRuntimeFacts,
    LiveObservationIdentity,
    LiveRoleCompletion,
    LiveTerminalObservation,
)


def checked_observation(schema, value):
    """Rebuild exact declared nested data; expose no rejected diagnostics."""

    def plain(item):
        if isinstance(item, LiveContract):
            if type(item) not in (*_SCHEMAS, ModelSelection, ModelUsage) or set(
                item.__dict__
            ) != set(type(item).model_fields):
                raise ValueError("Unowned observation fields.")
            return {k: plain(v) for k, v in item.__dict__.items()}
        if type(item) is dict:
            return {k: plain(v) for k, v in item.items()}
        if type(item) is tuple:
            return tuple(plain(v) for v in item)
        return item

    try:
        if not any(schema is allowed for allowed in _SCHEMAS):
            raise ValueError("Unsupported observation schema.")
        return schema.model_validate(plain(value))
    except (ValueError, TypeError, AttributeError, RecursionError):
        pass
    raise LiveValidationError() from None
