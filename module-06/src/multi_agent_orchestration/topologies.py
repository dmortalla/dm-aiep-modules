"""Finite application-owned graph plans, state, delegation, and contribution checks."""

from dataclasses import dataclass

from pydantic import ValidationError

from .contracts import (
    GraphDelegation,
    GraphMessage,
    GraphRole,
    GraphTopology,
    RuntimeId,
    TopologyState,
    WorkflowRequest,
)
from .errors import (
    InvalidRuntimeOutputError,
    InvalidWorkflowRequestError,
    StepBudgetExceededError,
)


@dataclass(frozen=True)
class TopologyPlan:
    """Closed topology policy, independent of caller/agent-produced control data."""

    roles: tuple[GraphRole, ...]
    parents: tuple[GraphRole | None, ...]
    sources: tuple[tuple[GraphRole, ...], ...]
    steps: int
    concurrency: int
    depth: int


def topology_plan(topology: GraphTopology) -> TopologyPlan:
    """Select one exact finite plan; no unsupported-topology fallback."""
    if topology == GraphTopology.SEQUENTIAL:
        roles = (GraphRole.RESEARCHER, GraphRole.ANALYST, GraphRole.CRITIC)
        return TopologyPlan(
            roles, (None, None, None), ((), roles[:1], roles[:2]), 3, 1, 0
        )
    if topology == GraphTopology.PARALLEL:
        roles = (GraphRole.LEFT, GraphRole.RIGHT, GraphRole.AGGREGATOR)
        return TopologyPlan(
            roles, (roles[2], roles[2], None), ((), (), roles[:2]), 4, 2, 1
        )
    if topology == GraphTopology.HIERARCHICAL:
        roles = (GraphRole.SPECIALIST, GraphRole.LEAD, GraphRole.SUPERVISOR)
        return TopologyPlan(
            roles, (roles[1], roles[2], None), ((), roles[:1], roles[1:2]), 5, 1, 2
        )
    raise InvalidWorkflowRequestError(
        "An explicit supported expanded topology is required."
    )


def check_topology_budget(request: WorkflowRequest) -> None:
    """Reject insufficient work/concurrency/depth before graph construction/work."""
    plan = topology_plan(request.topology)
    limits = request.limits
    if request.runtime != RuntimeId.LANGGRAPH:
        raise InvalidWorkflowRequestError("Graph topology requires explicit LangGraph.")
    if (
        limits.max_steps < plan.steps
        or limits.max_tasks < 3
        or limits.max_messages < 3
        or limits.max_concurrency < plan.concurrency
        or limits.max_hierarchy_depth < plan.depth
    ):
        raise StepBudgetExceededError(
            "Topology lacks authorized work/concurrency/depth."
        )


def expected_graph_messages(request: WorkflowRequest) -> tuple[GraphMessage, ...]:
    """Independently compute canonical contributions from authorized input."""
    plan = topology_plan(request.topology)
    size = len(request.task.instruction)
    if request.topology == GraphTopology.SEQUENTIAL:
        contents = (
            f"Research counted {size} characters.",
            f"Analysis accepted {size} characters.",
            f"Sequential synthesis accepted {size} characters.",
        )
    elif request.topology == GraphTopology.PARALLEL:
        contents = (
            f"Left counted {size} characters.",
            f"Right counted {size} characters.",
            f"Parallel synthesis accepted {size} characters.",
        )
    else:
        contents = (
            f"Specialist counted {size} characters.",
            f"Lead validated {size} characters.",
            f"Supervisor synthesis accepted {size} characters.",
        )
    return tuple(
        GraphMessage(
            workflow_id=request.workflow_id,
            task_id=request.task.task_id,
            role=role,
            sequence=index + 1,
            parent=plan.parents[index],
            sources=plan.sources[index],
            content=contents[index],
        )
        for index, role in enumerate(plan.roles)
    )


def expected_delegations(request: WorkflowRequest) -> tuple[GraphDelegation, ...]:
    """Only the application's supervisor roles may own these closed assignments."""
    if request.topology == GraphTopology.PARALLEL:
        return tuple(
            GraphDelegation(parent=GraphRole.AGGREGATOR, child=role, depth=1)
            for role in (GraphRole.LEFT, GraphRole.RIGHT)
        )
    if request.topology == GraphTopology.HIERARCHICAL:
        return (
            GraphDelegation(parent=GraphRole.SUPERVISOR, child=GraphRole.LEAD, depth=1),
            GraphDelegation(parent=GraphRole.LEAD, child=GraphRole.SPECIALIST, depth=2),
        )
    return ()


def validate_topology_state(
    raw: object, expected: WorkflowRequest, phase: int
) -> TopologyState:
    """Revalidate framework state against retained request and exact finite history."""
    try:
        state = TopologyState.model_validate(
            raw.model_dump() if isinstance(raw, TopologyState) else raw
        )
        state = TopologyState.model_validate(state.model_dump())
    except ValidationError as exc:
        raise InvalidRuntimeOutputError(
            "Topology state failed contract validation."
        ) from exc
    check_topology_budget(expected)
    messages = expected_graph_messages(expected)
    if expected.topology == GraphTopology.SEQUENTIAL:
        counts, assignments = (0, 1, 2, 3), (0, 0, 0, 0)
    elif expected.topology == GraphTopology.PARALLEL:
        counts, assignments = (0, 0, 3), (0, 2, 2)
    else:
        counts, assignments = (0, 0, 0, 1, 2, 3), (0, 1, 2, 2, 2, 2)
    if (
        phase not in range(len(counts))
        or state.phase != phase
        or state.request != expected
        or state.delegations != expected_delegations(expected)[: assignments[phase]]
        or state.contributions != messages[: counts[phase]]
    ):
        raise InvalidRuntimeOutputError(
            "Topology context/ownership/history is invalid."
        )
    return state


def validate_graph_message(
    raw: object, expected: WorkflowRequest, role: GraphRole
) -> GraphMessage:
    """Check exact role/task/parent/source/content before shared insertion."""
    try:
        message = GraphMessage.model_validate(
            raw.model_dump() if isinstance(raw, GraphMessage) else raw
        )
    except ValidationError as exc:
        raise InvalidRuntimeOutputError(
            "Topology contribution failed validation."
        ) from exc
    canonical = expected_graph_messages(expected)
    plan = topology_plan(expected.topology)
    if role not in plan.roles or message != canonical[plan.roles.index(role)]:
        raise InvalidRuntimeOutputError(
            "Topology contribution contradicts ownership/provenance."
        )
    return message


def merge_contributions(left: tuple, right: tuple) -> tuple[GraphMessage, ...]:
    """Pure bounded reducer; independent of completion order, no shared mutation."""
    try:
        merged = tuple(
            GraphMessage.model_validate(
                item.model_dump() if isinstance(item, GraphMessage) else item
            )
            for item in (*left, *right)
        )
    except (ValidationError, TypeError) as exc:
        raise InvalidRuntimeOutputError(
            "Topology reducer received invalid contributions."
        ) from exc
    if (
        len(merged) > 3
        or len({item.role for item in merged}) != len(merged)
        or len({item.sequence for item in merged}) != len(merged)
    ):
        raise InvalidRuntimeOutputError(
            "Duplicate or excessive topology contributions."
        )
    return tuple(sorted(merged, key=lambda item: item.sequence))


def validate_node_update(raw: object, canonical: dict) -> dict:
    """Validate before LangGraph can discard unknown channel/control fields."""
    if not isinstance(raw, dict) or set(raw) != set(canonical):
        raise InvalidRuntimeOutputError("Topology node returned unauthorized fields.")
    try:
        checked = {}
        for key, value in raw.items():
            if key == "phase":
                if type(value) is not int:
                    raise InvalidRuntimeOutputError(
                        "Topology phase must be a strict integer."
                    )
                checked[key] = value
            else:
                schema = GraphMessage if key == "contributions" else GraphDelegation
                checked[key] = tuple(
                    schema.model_validate(
                        item.model_dump() if isinstance(item, schema) else item
                    )
                    for item in value
                )
    except (ValidationError, TypeError) as exc:
        raise InvalidRuntimeOutputError(
            "Topology node update failed validation."
        ) from exc
    if checked != canonical:
        raise InvalidRuntimeOutputError(
            "Topology node changed authorized data/ownership."
        )
    return checked


def topology_step(
    raw: object, expected: WorkflowRequest, actor: GraphRole, phase: int
) -> dict:
    """Execute one role-owned stage; subordinate data cannot issue delegation."""
    state = validate_topology_state(raw, expected, phase)
    plan = topology_plan(expected.topology)
    messages = expected_graph_messages(expected)
    if expected.topology == GraphTopology.SEQUENTIAL:
        if phase >= 3 or actor != plan.roles[phase]:
            raise InvalidRuntimeOutputError("Sequential stage ownership is invalid.")
        size = (
            len(state.request.task.instruction)
            if phase == 0
            else int(state.contributions[-1].content.split()[2])
        )
        content = (
            f"Research counted {size} characters."
            if phase == 0
            else f"Analysis accepted {size} characters."
            if phase == 1
            else f"Sequential synthesis accepted {size} characters."
        )
        message = validate_graph_message(
            messages[phase].model_copy(update={"content": content}), expected, actor
        )
        return {"phase": phase + 1, "contributions": (message,)}
    if expected.topology == GraphTopology.HIERARCHICAL:
        owners = (
            GraphRole.SUPERVISOR,
            GraphRole.LEAD,
            GraphRole.SPECIALIST,
            GraphRole.LEAD,
            GraphRole.SUPERVISOR,
        )
        if phase >= 5 or actor != owners[phase]:
            raise InvalidRuntimeOutputError(
                "Only the assigned supervisor/child may advance."
            )
        if phase < 2:
            return {
                "phase": phase + 1,
                "delegations": expected_delegations(expected)[: phase + 1],
            }
        index = phase - 2
        size = (
            len(state.request.task.instruction)
            if index == 0
            else int(state.contributions[-1].content.split()[2])
        )
        content = (
            f"Specialist counted {size} characters."
            if index == 0
            else f"Lead validated {size} characters."
            if index == 1
            else f"Supervisor synthesis accepted {size} characters."
        )
        message = validate_graph_message(
            messages[index].model_copy(update={"content": content}), expected, actor
        )
        return {"phase": phase + 1, "contributions": (message,)}
    if phase != 0 or actor != GraphRole.AGGREGATOR:
        raise InvalidRuntimeOutputError(
            "Only the coordinator may assign parallel work."
        )
    return {"phase": 1, "delegations": expected_delegations(expected)}


def parallel_branch(raw: object, expected: WorkflowRequest, role: GraphRole) -> dict:
    """Independent branch from the same validated authorized parent snapshot."""
    state = validate_topology_state(raw, expected, 1)
    if expected.topology != GraphTopology.PARALLEL or role not in (
        GraphRole.LEFT,
        GraphRole.RIGHT,
    ):
        raise InvalidRuntimeOutputError("Parallel branch ownership is invalid.")
    size = len(state.request.task.instruction)
    index = topology_plan(expected.topology).roles.index(role)
    content = (
        f"{'Left' if role == GraphRole.LEFT else 'Right'} counted {size} characters."
    )
    message = validate_graph_message(
        expected_graph_messages(expected)[index].model_copy(
            update={"content": content}
        ),
        expected,
        role,
    )
    return {"contributions": (message,)}


def parallel_aggregate(raw: object, expected: WorkflowRequest) -> dict:
    """Fan-in accepts exactly both individually validated branches before synthesis."""
    try:
        state = TopologyState.model_validate(
            raw.model_dump() if isinstance(raw, TopologyState) else raw
        )
        state = TopologyState.model_validate(state.model_dump())
    except ValidationError as exc:
        raise InvalidRuntimeOutputError("Fan-in state failed validation.") from exc
    # The ordinary phase-one boundary requires the branch-start snapshot. Here
    # validate that same context with the two required messages checked separately.
    validate_topology_state(state.model_copy(update={"contributions": ()}), expected, 1)
    if state.contributions != expected_graph_messages(expected)[:2]:
        raise InvalidRuntimeOutputError(
            "Fan-in requires both valid branch contributions."
        )
    sizes = tuple(int(item.content.split()[2]) for item in state.contributions)
    if sizes[0] != sizes[1]:
        raise InvalidRuntimeOutputError("Parallel branch results disagree.")
    message = expected_graph_messages(expected)[2].model_copy(
        update={"content": f"Parallel synthesis accepted {sizes[0]} characters."}
    )
    return {
        "phase": 2,
        "contributions": (
            validate_graph_message(message, expected, GraphRole.AGGREGATOR),
        ),
    }
