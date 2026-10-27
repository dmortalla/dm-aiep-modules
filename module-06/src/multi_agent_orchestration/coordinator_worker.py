"""Pure application-owned coordinator-worker state semantics and validation."""

from pydantic import ValidationError

from .contracts import (
    AgentTaskResult,
    ExecutionStatus,
    RuntimeId,
    TaskInput,
    WorkflowPhase,
    WorkflowRequest,
    WorkflowState,
    WorkflowTransition,
)
from .errors import InvalidRuntimeOutputError, StepBudgetExceededError


def worker_output(task: TaskInput) -> str:
    """Process bounded task context as data, never as instructions to a provider.

    Args:
        task: Validated task whose text is counted, not interpreted or echoed.

    Returns:
        A deterministic, payload-free result describing the character count.
    """
    return f"Deterministic worker processed {len(task.instruction)} characters."


def validate_state(
    raw: object,
    expected: WorkflowRequest,
    phase: WorkflowPhase,
) -> WorkflowState:
    """Revalidate schema, request identity/bounds, phase, delegation, and history.

    Args:
        raw: Untrusted graph state, including constructed Pydantic instances.
        expected: Request retained outside graph output by trusted adapter code.
        phase: Required application state at this boundary.

    Returns:
        A fresh immutable state matching the application workflow semantics.

    Raises:
        InvalidRuntimeOutputError: State is malformed or contradicts the request/flow.
    """
    try:
        state = WorkflowState.model_validate(
            raw.model_dump() if isinstance(raw, WorkflowState) else raw
        )
    except ValidationError as exc:
        raise InvalidRuntimeOutputError(
            "Graph state failed contract validation."
        ) from exc
    phases = tuple(WorkflowPhase)
    index = phases.index(phase)
    trail = tuple(WorkflowTransition)[:index]
    if (
        state.request != expected
        or state.request.runtime != RuntimeId.LANGGRAPH
        or state.phase != phase
        or state.transitions != trail
        or state.delegated_to != (None if index == 0 else "deterministic_worker")
    ):
        raise InvalidRuntimeOutputError(
            "Graph state contradicts application context/transition."
        )
    if index < 2:
        if state.result is not None:
            raise InvalidRuntimeOutputError("Worker output cannot precede delegation.")
    elif (
        state.result is None
        or state.result.task_id != expected.task.task_id
        or state.result.agent_id != "deterministic_worker"
        or state.result.output != worker_output(expected.task)
    ):
        raise InvalidRuntimeOutputError("Worker result failed application validation.")
    return state


def advance(
    raw: object,
    expected: WorkflowRequest,
    phase: WorkflowPhase,
) -> WorkflowState:
    """Apply one finite application transition under the caller's step budget.

    Args:
        raw: Untrusted node input.
        expected: Validated request retained outside the graph state.
        phase: The required current phase for this node.

    Returns:
        Next immutable state; worker output is generated only in the worker step.

    Raises:
        InvalidRuntimeOutputError: State or transition is invalid.
        StepBudgetExceededError: No authorized step remains.
    """
    state = validate_state(raw, expected, phase)
    steps = len(state.transitions)
    if steps >= expected.limits.max_steps:
        raise StepBudgetExceededError(
            "Coordinator-worker step budget exhausted; allow three steps."
        )
    if phase == WorkflowPhase.COMPLETED:
        raise InvalidRuntimeOutputError("Completed workflow cannot advance.")
    result = state.result
    if phase == WorkflowPhase.DELEGATED:
        result = AgentTaskResult(
            task_id=expected.task.task_id,
            agent_id="deterministic_worker",
            status=ExecutionStatus.COMPLETED,
            output=worker_output(state.request.task),
        )
    return WorkflowState(
        request=expected,
        phase=tuple(WorkflowPhase)[steps + 1],
        delegated_to="deterministic_worker",
        result=result,
        transitions=state.transitions + (tuple(WorkflowTransition)[steps],),
    )
