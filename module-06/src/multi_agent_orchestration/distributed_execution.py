"""Explicit application service for offline local multi-process ADK execution."""

import asyncio
import os

from .distributed import make_assignments, validate_request, validate_responses
from .distributed_contracts import DistributedEvidence, DistributedResult, WorkerRecord
from .errors import (
    ExecutionFailureError,
    ExecutionTimeoutError,
    RuntimeFoundationError,
)


async def execute_distributed_workflow(request: object) -> DistributedResult:
    """Validate two independent worker responses before creating trusted evidence.

    This explicit service requires Google ADK; existing execute_workflow and its
    runtime registry/defaults are unchanged. No credentials authorize this path.
    """
    expected = validate_request(request)
    coordinator_pid = os.getpid()
    assignments = make_assignments(expected, coordinator_pid)
    from ._distributed_processes import dispatch_workers

    try:
        async with asyncio.timeout(expected.limits.timeout_ms / 1000):
            raw, pids = await dispatch_workers(assignments)
            responses = validate_responses(raw, assignments, pids)
    except TimeoutError as exc:
        raise ExecutionTimeoutError(
            "Distributed deadline expired; worker processes were terminated and reaped."
        ) from exc
    except RuntimeFoundationError:
        raise
    except Exception as exc:
        raise ExecutionFailureError(
            "Distributed execution failed; inspect the internal cause."
        ) from exc
    characters = sum(item.characters for item in responses)
    evidence = DistributedEvidence(
        workflow_id=expected.workflow_id,
        task_id=expected.task.task_id,
        coordinator_pid=coordinator_pid,
        limits=expected.limits,
        workers=tuple(
            WorkerRecord(
                assignment_id=item.assignment_id,
                worker=item.worker,
                role=item.role,
                sequence=item.sequence,
                pid=item.pid,
            )
            for item in responses
        ),
    )
    return DistributedResult(
        workflow_id=expected.workflow_id,
        task_id=expected.task.task_id,
        characters=characters,
        output=f"Distributed synthesis accepted {characters} characters.",
        evidence=evidence,
    )
