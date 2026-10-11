"""Application semantics for bounded local delegation, work, and validation."""

from pydantic import ValidationError

from .contracts import (
    OrchestrationMessage,
    OrchestrationRole,
    OrchestrationState,
    RuntimeId,
    WorkflowRequest,
)
from .errors import InvalidRuntimeOutputError, StepBudgetExceededError


def expected_orchestration(
    request: WorkflowRequest,
) -> tuple[OrchestrationMessage, ...]:
    """Canonical results independently derived from caller-owned input."""
    size = len(request.task.instruction)
    roles = tuple(OrchestrationRole)
    contents = (
        f"Delegated {size} characters to adk_specialist.",
        f"Specialist counted {size} characters.",
        f"ADK validation accepted {size} characters.",
    )
    return tuple(
        OrchestrationMessage(
            workflow_id=request.workflow_id,
            task_id=request.task.task_id,
            role=role,
            sequence=index + 1,
            sources=roles[:index],
            content=contents[index],
        )
        for index, role in enumerate(roles)
    )


def validate_orchestration_state(
    raw: object, expected: WorkflowRequest, count: int
) -> OrchestrationState:
    """Revalidate every framework handoff against request retained outside it."""
    try:
        state = OrchestrationState.model_validate(
            raw.model_dump() if isinstance(raw, OrchestrationState) else raw
        )
    except ValidationError as exc:
        raise InvalidRuntimeOutputError(
            "ADK state failed contract validation."
        ) from exc
    if (
        expected.runtime != RuntimeId.GOOGLE_ADK
        or state.request != expected
        or count not in range(4)
        or state.messages != expected_orchestration(expected)[:count]
    ):
        raise InvalidRuntimeOutputError("ADK state contradicts authorized context.")
    if count > min(
        expected.limits.max_steps,
        expected.limits.max_tasks,
        expected.limits.max_messages,
    ):
        raise StepBudgetExceededError(
            "ADK state exceeds its authorized resource bounds."
        )
    return state


def advance_orchestration(
    raw: object, expected: WorkflowRequest, role: OrchestrationRole
) -> OrchestrationState:
    """Delegate once, consume that assignment, then validate the worker's message."""
    index = tuple(OrchestrationRole).index(role)
    state = validate_orchestration_state(raw, expected, index)
    if index + 1 > min(
        expected.limits.max_steps,
        expected.limits.max_tasks,
        expected.limits.max_messages,
    ):
        raise StepBudgetExceededError("ADK role lacks an authorized step/task/message.")
    # Downstream roles must actually consume framework-transported upstream data.
    if index == 0:
        size = len(state.request.task.instruction)
        content = f"Delegated {size} characters to adk_specialist."
    elif index == 1:
        size = int(state.messages[0].content.split()[1])
        content = f"Specialist counted {size} characters."
    else:
        size = int(state.messages[1].content.split()[2])
        content = f"ADK validation accepted {size} characters."
    message = expected_orchestration(expected)[index].model_copy(
        update={"content": content}
    )
    candidate = OrchestrationState(
        request=state.request, messages=(*state.messages, message)
    )
    return validate_orchestration_state(candidate, expected, index + 1)
