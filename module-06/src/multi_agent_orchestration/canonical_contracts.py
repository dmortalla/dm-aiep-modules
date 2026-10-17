"""Application receipts and payload-free observations; never execution authority."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .contracts import GraphRole
from .live_contracts import (
    MAX_MODEL_CALLS,
    MAX_REPAIR_ATTEMPTS,
    PLANNED_MODEL_CALLS,
    CanonicalUUID,
    LiveContract,
    LiveWorkflowResult,
)
from .live_errors import LiveFailureCategory


class EvidenceSource(StrEnum):
    """Application-selected provenance, not a model claim or quality verdict."""

    SYNTHETIC_OFFLINE = "synthetic_offline"
    LOCAL_PROVIDER_EXECUTION = "local_provider_execution"


class CanonicalWorkflowReceipt(LiveContract):
    """Validated runtime result plus conservative gateway provenance.

    The inner accepted execution_class describes the authorized target. It is
    not proof of actual inference. Injected gateways always receive synthetic
    provenance, even if their selection names a real provider/model.
    """

    evidence_source: EvidenceSource
    result: LiveWorkflowResult = Field(repr=False)


class LiveWorkflowEvent(LiveContract):
    """Bounded local lifecycle observation, with no prompt or model content.

    Role validation is provisional; only completed follows authoritative worker
    cleanup/final checks. Observation never determines workflow acceptance.
    """

    workflow_id: CanonicalUUID
    task_id: CanonicalUUID
    trace_id: CanonicalUUID | None = None
    evidence_source: EvidenceSource
    phase: Literal[
        "started", "role_validated", "completed", "failed", "cancelled", "invalid_input"
    ]
    role: Literal[GraphRole.RESEARCHER, GraphRole.ANALYST, GraphRole.CRITIC] | None = (
        None
    )
    model_calls: Annotated[int, Field(strict=True, ge=0, le=MAX_MODEL_CALLS)] | None = (
        None
    )
    repair_attempts: (
        Annotated[int, Field(strict=True, ge=0, le=MAX_REPAIR_ATTEMPTS)] | None
    ) = None
    category: LiveFailureCategory | None = None

    @model_validator(mode="after")
    def consistent(self) -> "LiveWorkflowEvent":
        """Do not present provisional roles or failures as completed workflows."""
        if self.trace_id is not None and self.trace_id.int == 0:
            raise ValueError("Trace identity must be nonzero.")
        if (
            (self.phase == "role_validated") != (self.role is not None)
            or (self.phase == "failed") != (self.category is not None)
            or (self.phase == "cancelled") != (self.model_calls is None)
            or (self.model_calls is None) != (self.repair_attempts is None)
            or (
                self.model_calls is not None and self.repair_attempts > self.model_calls
            )
            or (self.phase == "started" and (self.model_calls or self.repair_attempts))
            or (
                self.phase == "completed"
                and self.model_calls != PLANNED_MODEL_CALLS + self.repair_attempts
            )
        ):
            raise ValueError("Inconsistent lifecycle observation.")
        return self
