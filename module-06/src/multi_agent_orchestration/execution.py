"""Request/output validation and bounded execution at the application boundary."""

import asyncio
from collections.abc import Mapping

from pydantic import ValidationError

from .collaboration import expected_messages
from .contracts import (
    ContributionRecord,
    ExecutionEvidence,
    ExecutionStatus,
    RuntimeId,
    RuntimeOutput,
    ValidatedWorkflowResult,
    WorkflowRequest,
    WorkflowTransition,
)
from .coordinator_worker import worker_output
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
    """Validate bounded local execution; build evidence outside runtime output.

    Args:
        request: Untrusted input, including already-created Pydantic objects.
        runtime: Optional trusted code dependency injection, never request/model data.

    Returns:
        Validated result with application-created, payload-free evidence.

    Raises:
        InvalidWorkflowRequestError: Input schema or explicit runtime selection fails.
        RuntimeUnavailableError: Selected runtime execution is not implemented.
        InvalidRuntimeOutputError: Output schema, identity, content, or history fails.
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
    if (
        validated.runtime
        not in (RuntimeId.FIXTURE, RuntimeId.LANGGRAPH, RuntimeId.CREWAI)
        or not selected.info.execution_available
    ):
        raise RuntimeUnavailableError("Selected runtime execution is not implemented.")
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
    graph = validated.runtime == RuntimeId.LANGGRAPH
    crew = validated.runtime == RuntimeId.CREWAI
    messages = expected_messages(validated) if crew else ()
    transitions = tuple(WorkflowTransition) if graph else ()
    if (
        output.workflow_id != validated.workflow_id
        or output.result.task_id != validated.task.task_id
        or output.runtime != validated.runtime
        or output.result.agent_id
        != ("critic" if crew else "deterministic_worker" if graph else "fixture_agent")
        or output.transitions != transitions
        or output.collaboration != messages
        or output.result.output
        != (
            messages[-1].content
            if crew
            else worker_output(validated.task)
            if graph
            else "Fixture task completed; no model or external calls were made."
        )
        or ((graph or crew) and validated.limits.max_steps < 3)
        or (crew and min(validated.limits.max_tasks, validated.limits.max_messages) < 3)
    ):
        raise InvalidRuntimeOutputError(
            "Runtime output contradicts the application request/contract."
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
            steps_consumed=3 if graph or crew else 1,
            transitions=transitions,
            collaboration=tuple(
                ContributionRecord.model_validate(
                    message.model_dump(exclude={"content"})
                )
                for message in messages
            ),
        ),
    )
