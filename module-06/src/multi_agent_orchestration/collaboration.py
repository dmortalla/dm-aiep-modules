"""Application-owned bounded collaboration semantics, independent of CrewAI."""

from pydantic import ValidationError

from .contracts import (
    CollaborationMessage,
    CollaborationState,
    CollaboratorRole,
    RuntimeId,
    WorkflowRequest,
)
from .errors import InvalidRuntimeOutputError, StepBudgetExceededError


def expected_messages(request: WorkflowRequest) -> tuple[CollaborationMessage, ...]:
    """Return the exact deterministic contributions authorized by this request."""
    size = len(request.task.instruction)
    contents = (
        f"Research: {size} characters.",
        f"Analysis: {size} characters; nonempty input.",
        f"Collaborative review accepted {size} characters.",
    )
    roles = tuple(CollaboratorRole)
    return tuple(
        CollaborationMessage(
            workflow_id=request.workflow_id,
            task_id=request.task.task_id,
            role=role,
            sequence=index + 1,
            sources=roles[:index],
            content=contents[index],
        )
        for index, role in enumerate(roles)
    )


def next_message(
    state: CollaborationState, expected: WorkflowRequest
) -> CollaborationMessage:
    """Research input, analyze research, or synthesize validated analysis.

    Downstream roles derive their count from upstream contributions, not task
    text. Contribution insertion independently validates the derived result.
    """
    state = validate_shared_state(state, expected)
    index = len(state.messages)
    if index >= min(
        3,
        expected.limits.max_steps,
        expected.limits.max_tasks,
        expected.limits.max_messages,
    ):
        raise StepBudgetExceededError("No collaborative task/message/step remains.")
    if index == 0:
        content = f"Research: {len(state.request.task.instruction)} characters."
    elif index == 1:
        count = int(state.messages[0].content.split()[1])
        content = f"Analysis: {count} characters; nonempty input."
    else:
        count = int(state.messages[1].content.split()[1])
        content = f"Collaborative review accepted {count} characters."
    return CollaborationMessage.model_validate(
        {
            **expected_messages(expected)[index].model_dump(),
            "content": content,
        }
    )


def validate_shared_state(raw: object, expected: WorkflowRequest) -> CollaborationState:
    """Revalidate immutable shared state against retained identity/context/bounds.

    Raises:
        InvalidRuntimeOutputError: A schema, identity, context, or provenance mismatch.
    """
    try:
        state = CollaborationState.model_validate(
            raw.model_dump() if isinstance(raw, CollaborationState) else raw
        )
    except ValidationError as exc:
        raise InvalidRuntimeOutputError(
            "Collaboration state failed validation."
        ) from exc
    if (
        state.request != expected
        or expected.runtime != RuntimeId.CREWAI
        or state.messages != expected_messages(expected)[: len(state.messages)]
    ):
        raise InvalidRuntimeOutputError(
            "Collaboration state contradicts authorized context/provenance."
        )
    if len(state.messages) > min(
        expected.limits.max_steps,
        expected.limits.max_tasks,
        expected.limits.max_messages,
    ):
        raise StepBudgetExceededError(
            "Collaboration exceeds its authorized resource budget."
        )
    return state


def contribute(
    raw: object, state: CollaborationState, expected: WorkflowRequest
) -> CollaborationState:
    """Validate one untrusted contribution before replacing shared state.

    Raises:
        InvalidRuntimeOutputError: Output schema, ownership, content, or order fails.
        StepBudgetExceededError: No task/message/step remains.
    """
    state = validate_shared_state(state, expected)
    count = len(state.messages)
    if count >= min(
        3,
        expected.limits.max_steps,
        expected.limits.max_tasks,
        expected.limits.max_messages,
    ):
        raise StepBudgetExceededError(
            "Collaboration task/message/step budget exhausted."
        )
    try:
        message = CollaborationMessage.model_validate(
            raw.model_dump() if isinstance(raw, CollaborationMessage) else raw
        )
    except ValidationError as exc:
        raise InvalidRuntimeOutputError(
            "Collaborator output failed validation."
        ) from exc
    if message != expected_messages(expected)[count]:
        raise InvalidRuntimeOutputError(
            "Collaborator output contradicts task ownership/provenance."
        )
    return CollaborationState(request=expected, messages=state.messages + (message,))
