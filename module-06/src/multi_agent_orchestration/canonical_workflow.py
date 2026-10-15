"""Canonical application entry point; no import/startup or implicit inference.

The approved runtime owns the graph, validation, budgets and process lifecycle.
This service connects explicit operator authority to the reviewed local adapter,
classifies injected execution conservatively, and emits local-only observations.
No UI, credential lookup, provider discovery or network call happens here.
"""

import asyncio
from collections.abc import Callable
from uuid import UUID, uuid4

from .canonical_contracts import (
    CanonicalWorkflowReceipt,
    EvidenceSource,
    LiveWorkflowEvent,
)
from .contracts import GraphRole
from .live_contracts import LiveFailure, require_live_authorization
from .live_errors import LiveExecutionError, LiveFailureCategory, LiveValidationError
from .live_execution import LiveRuntimeError, execute_live_workflow
from .live_validation import validate_live_data
from .local_model_gateway import LocalModelGateway
from .model_gateway import ModelGateway
from .observability import Observability

CANONICAL_PROVIDER = "ollama"
CANONICAL_MODEL = "qwen2.5-coder:7b"


def _local_gateway() -> ModelGateway:
    """Construct the reviewed adapter only inside the authorized gateway child."""
    return LocalModelGateway()


class CanonicalWorkflowError(LiveRuntimeError):
    """Accepted sanitized failure with application-owned gateway provenance."""

    def __init__(self, failure: LiveFailure, source: EvidenceSource) -> None:
        super().__init__(failure)
        self.evidence_source = source


async def _execute_canonical_workflow(
    instruction: str,
    *,
    authorization: object = None,
    gateway_factory: Callable[[], ModelGateway] | None = None,
    observer: Observability | None = None,
    workflow_id: UUID | str | None = None,
    task_id: UUID | str | None = None,
) -> CanonicalWorkflowReceipt:
    """Execute the fixed three-role plan under explicit application authority.

    Args:
        instruction: Bounded task data, not routing or execution policy.
        authorization: Exact accepted LiveAuthorization; absence refuses execution.
        gateway_factory: Trusted source-backed offline dependency injection. Every
            override is classified synthetic; omit only for separately authorized
            real local execution. No callable is accepted from model output.
        observer: Optional trusted bounded local Observability instance.
        workflow_id: Optional application correlation identifier.
        task_id: Optional application task identifier.

    Returns:
        Accepted typed runtime result plus conservative evidence provenance.

    Raises:
        CanonicalWorkflowError: Closed refusal/execution failure with safe counters.
        LiveValidationError: Invalid input or application correlation identifiers.
        asyncio.CancelledError: Cancellation after supervised child cleanup.

    Availability/configuration never authorizes this call. This implementation
    task authorizes no real execution; fresh human HITL is still required.
    """
    source = (
        EvidenceSource.LOCAL_PROVIDER_EXECUTION
        if gateway_factory is None
        else EvidenceSource.SYNTHETIC_OFFLINE
    )
    identity = validate_live_data(
        LiveFailure,
        {
            "workflow_id": uuid4() if workflow_id is None else workflow_id,
            "task_id": uuid4() if task_id is None else task_id,
            "category": LiveFailureCategory.AUTHORIZATION_REFUSED,
        },
    )

    def emit(
        phase: str,
        *,
        role: GraphRole | None = None,
        calls: int | None = 0,
        repairs: int | None = 0,
        category: LiveFailureCategory | None = None,
    ) -> None:
        if observer is None:
            return
        try:
            observer.emit_live(
                LiveWorkflowEvent(
                    workflow_id=identity.workflow_id,
                    task_id=identity.task_id,
                    evidence_source=source,
                    phase=phase,
                    role=role,
                    model_calls=calls,
                    repair_attempts=repairs,
                    category=category,
                )
            )
        except (Exception, asyncio.CancelledError):
            # Observation failures cannot replace canonical workflow outcomes.
            pass

    def validated(role: GraphRole, calls: int, repairs: int) -> None:
        emit("role_validated", role=role, calls=calls, repairs=repairs)

    error = None
    try:
        auth = require_live_authorization(authorization)
        if (
            auth.selection.provider != CANONICAL_PROVIDER
            or auth.selection.model != CANONICAL_MODEL
        ):
            raise LiveRuntimeError(identity)
        emit("started")
        result = await execute_live_workflow(
            instruction,
            authorization=auth,
            gateway_factory=_local_gateway
            if gateway_factory is None
            else gateway_factory,
            workflow_id=identity.workflow_id,
            task_id=identity.task_id,
            role_validated=validated,
        )
        receipt = None
        try:
            receipt = CanonicalWorkflowReceipt(evidence_source=source, result=result)
        except (ValueError, TypeError, AttributeError):
            pass
        if receipt is None:
            raise LiveValidationError() from None
    except asyncio.CancelledError:
        emit("cancelled", calls=None, repairs=None)
        raise asyncio.CancelledError() from None
    except LiveRuntimeError as failure:
        error = CanonicalWorkflowError(failure.failure, source)
    except LiveExecutionError as failure:
        refused = validate_live_data(
            LiveFailure,
            {
                **identity.model_dump(),
                "category": failure.category,
            },
        )
        error = CanonicalWorkflowError(refused, source)
    except LiveValidationError:
        emit("invalid_input")
        raise
    if error is not None:
        emit(
            "failed",
            calls=error.failure.model_calls,
            repairs=error.failure.repair_attempts,
            category=error.category,
        )
        try:
            raise error from None
        except CanonicalWorkflowError as safe:
            safe.__context__ = None
            safe.__cause__ = None
            safe.__suppress_context__ = True
            raise
    accounting = result.evidence.accounting
    emit("completed", calls=accounting.model_calls, repairs=accounting.repair_attempts)
    return receipt


async def execute_canonical_workflow(
    instruction: str,
    *,
    authorization: object = None,
    gateway_factory: Callable[[], ModelGateway] | None = None,
    observer: Observability | None = None,
    workflow_id: UUID | str | None = None,
    task_id: UUID | str | None = None,
) -> CanonicalWorkflowReceipt:
    """Run the canonical API with the accepted sanitized public failure boundary.

    Args:
        instruction: Bounded untrusted task text.
        authorization: Explicit accepted LiveAuthorization; no default authority.
        gateway_factory: Trusted source-backed synthetic override. Omit only for
            separately authorized real local execution through the reviewed adapter.
        observer: Optional bounded synchronous local observation infrastructure.
        workflow_id: Optional application-owned correlation identifier.
        task_id: Optional application-owned task identifier.

    Returns:
        Strict runtime content/evidence with application-owned source provenance.

    Raises:
        CanonicalWorkflowError: Sanitized refusal or execution failure.
        LiveValidationError: Sanitized invalid input.
        asyncio.CancelledError: Cancellation after supervised cleanup.
    """
    try:
        return await _execute_canonical_workflow(
            instruction,
            authorization=authorization,
            gateway_factory=gateway_factory,
            observer=observer,
            workflow_id=workflow_id,
            task_id=task_id,
        )
    except (
        CanonicalWorkflowError,
        LiveValidationError,
        asyncio.CancelledError,
    ) as error:
        error.__context__ = None
        error.__cause__ = None
        error.__suppress_context__ = True
        raise
