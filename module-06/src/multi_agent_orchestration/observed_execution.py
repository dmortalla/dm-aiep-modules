"""Opt-in observation of accepted services; identical results and exceptions."""

import asyncio
from collections.abc import Mapping

from .contracts import WorkflowRequest
from .distributed_execution import execute_distributed_workflow
from .errors import (
    ExecutionTimeoutError,
    InvalidRuntimeOutputError,
    InvalidWorkflowRequestError,
    StepBudgetExceededError,
)
from .execution import execute_workflow
from .observability import Observability
from .observability_contracts import Outcome


async def execute_observed_workflow(
    request: WorkflowRequest | Mapping[str, object],
    *,
    observer: Observability,
    distributed: bool = False,
    runtime=None,
):
    """No telemetry config in request data, no delivery or credential inspection.

    Invalid schemas without reliable correlation are rejected without emitting
    their content. Typed, correlated runtime/budget/validation denials are observed.
    Step traces describe validated completions, not inferred role start times.
    """
    try:
        data = (
            request.model_dump(warnings="error")
            if isinstance(request, WorkflowRequest)
            else request
        )
        explicitly_selected = (
            "runtime" in request.model_fields_set
            if isinstance(request, WorkflowRequest)
            else "runtime" in data
        )
        checked = WorkflowRequest.model_validate(data)
        checked = WorkflowRequest.model_validate(checked.model_dump())
        if not explicitly_selected or type(distributed) is not bool:
            raise ValueError("Explicit runtime/path selection is required.")
        if distributed and runtime is not None:
            raise ValueError("Distributed execution owns its runtime adapter.")
    except (ValueError, TypeError) as exc:
        raise InvalidWorkflowRequestError(
            "Observed request failed validation."
        ) from exc
    try:
        handle = observer.begin(checked, distributed)
    except (Exception, asyncio.CancelledError):
        handle = None  # Observation startup cannot prevent accepted execution.

    def finish(outcome, result=None):
        try:
            observer.finish(handle, outcome, result)
        except (Exception, asyncio.CancelledError):
            try:
                observer.abandon(handle)
            except (Exception, asyncio.CancelledError):
                pass  # Observation failures cannot replace execution outcomes.

    try:
        result = (
            await execute_distributed_workflow(checked)
            if distributed
            else await execute_workflow(checked, runtime=runtime)
        )
    except asyncio.CancelledError:
        finish(Outcome.CANCELLED)
        raise
    except ExecutionTimeoutError:
        finish(Outcome.TIMED_OUT)
        raise
    except (
        InvalidWorkflowRequestError,
        InvalidRuntimeOutputError,
        StepBudgetExceededError,
    ):
        finish(Outcome.DENIED)
        raise
    except Exception:
        finish(Outcome.FAILED)
        raise
    finish(Outcome.COMPLETED, result)
    return result
