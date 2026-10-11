"""Request/output validation and bounded execution at the application boundary."""

import asyncio
from collections.abc import Mapping

from pydantic import ValidationError

from .contracts import (
    ExecutionEvidence,
    ExecutionStatus,
    RuntimeId,
    RuntimeOutput,
    ValidatedWorkflowResult,
    WorkflowRequest,
)
from .errors import (
    ExecutionFailureError,
    ExecutionTimeoutError,
    InvalidRuntimeOutputError,
    InvalidWorkflowRequestError,
    RuntimeFoundationError,
    RuntimeUnavailableError,
)
from .registry import create_runtime
from .runtime import Runtime


async def execute_workflow(
    request: WorkflowRequest | Mapping[str, object],
    *,
    runtime: Runtime | None = None,
) -> ValidatedWorkflowResult:
    """Validate and execute one fixture task; build evidence outside runtime output.

    Args:
        request: Untrusted input, including already-created Pydantic objects.
        runtime: Optional trusted code dependency injection, never request/model data.

    Returns:
        Validated result with application-created, payload-free evidence.

    Raises:
        InvalidWorkflowRequestError: Input schema or explicit runtime selection fails.
        RuntimeUnavailableError: Framework execution is not implemented.
        InvalidRuntimeOutputError: Output schema, identity, or fixture content fails.
        ExecutionTimeoutError: Cooperative async execution exceeds the deadline.
        ExecutionFailureError: Adapter execution fails unexpectedly.
    """
    try:
        # Revalidate to catch model_construct/model_copy bypasses, including nesting.
        data = request.model_dump() if isinstance(request, WorkflowRequest) else request
        validated = WorkflowRequest.model_validate(data)
    except ValidationError as exc:
        raise InvalidWorkflowRequestError(
            "Workflow request failed contract validation; check UUIDs, runtime, "
            "nonblank task input, and bounded execution limits."
        ) from exc

    selected = runtime if runtime is not None else create_runtime(validated.runtime)
    if selected.info.runtime != validated.runtime:
        raise InvalidWorkflowRequestError("Requested and selected runtimes must match.")
    if validated.runtime != RuntimeId.FIXTURE or not selected.info.execution_available:
        raise RuntimeUnavailableError(
            "Framework execution is not implemented; "
            "explicitly select fixture for offline use."
        )
    try:
        async with asyncio.timeout(validated.limits.timeout_ms / 1000):
            raw = await selected.execute(validated)
    except TimeoutError as exc:
        raise ExecutionTimeoutError(
            "Workflow execution exceeded its deadline."
        ) from exc
    except RuntimeFoundationError:
        raise
    except Exception as exc:
        # Translate failures only at the adapter invocation boundary; retain context.
        raise ExecutionFailureError(
            "Runtime execution failed; inspect the internal cause."
        ) from exc

    try:
        output = RuntimeOutput.model_validate(
            raw.model_dump() if isinstance(raw, RuntimeOutput) else raw
        )
    except ValidationError as exc:
        raise InvalidRuntimeOutputError(
            "Runtime output failed contract validation."
        ) from exc
    if (
        output.workflow_id != validated.workflow_id
        or output.result.task_id != validated.task.task_id
        or output.runtime != validated.runtime
        or output.result.output
        != "Fixture task completed; no model or external calls were made."
    ):
        raise InvalidRuntimeOutputError(
            "Runtime output contradicts the fixture request/contract."
        )

    return ValidatedWorkflowResult(
        result=output.result,
        evidence=ExecutionEvidence(
            workflow_id=validated.workflow_id,
            task_id=validated.task.task_id,
            requested_runtime=validated.runtime,
            actual_runtime=output.runtime,
            status=ExecutionStatus.COMPLETED,
            limits=validated.limits,
        ),
    )
