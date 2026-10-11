"""Private real LangGraph compilation/execution for the three bounded topologies."""

import asyncio
from importlib import import_module
from typing import Annotated

from pydantic import Field

from .contracts import (
    AgentTaskResult,
    ExecutionStatus,
    GraphMessage,
    GraphRole,
    GraphTopology,
    RuntimeId,
    RuntimeOutput,
    TopologyState,
    WorkflowRequest,
)
from .topologies import (
    check_topology_budget,
    merge_contributions,
    parallel_aggregate,
    parallel_branch,
    topology_plan,
    topology_step,
    validate_node_update,
    validate_topology_state,
)


class _GraphState(TopologyState):
    """Reducer annotation stays private; domain state contains no SDK types."""

    contributions: Annotated[
        tuple[GraphMessage, ...], Field(max_length=3), merge_contributions
    ] = ()


async def run_stage(state, expected, actor, phase):
    """Native async node with bounded deterministic application behavior."""
    return topology_step(state, expected, actor, phase)


async def run_branch(state, expected, role):
    """Cooperative independent native async branch; no threads/background jobs."""
    await asyncio.sleep(0)
    return parallel_branch(state, expected, role)


def compile_topology(expected: WorkflowRequest, graph_type):
    """Build fixed edges, real fan-out/fan-in barrier, or supervisor hierarchy."""
    check_topology_budget(expected)
    graph = graph_type(state_schema=_GraphState)

    def add_stage(name, actor, phase):
        async def stage(state):
            raw = await run_stage(state, expected, actor, phase)
            return validate_node_update(
                raw, topology_step(state, expected, actor, phase)
            )

        graph.add_node(name, stage)

    if expected.topology == GraphTopology.SEQUENTIAL:
        nodes = ("researcher", "analyst", "critic")
        for index, (name, role) in enumerate(
            zip(nodes, topology_plan(expected.topology).roles, strict=True)
        ):
            add_stage(name, role, index)
        for parent, child in zip(
            ("__start__", *nodes), (*nodes, "__end__"), strict=True
        ):
            graph.add_edge(parent, child)
    elif expected.topology == GraphTopology.HIERARCHICAL:
        nodes = (
            "supervisor_delegate",
            "lead_delegate",
            "specialist",
            "lead_validate",
            "supervisor_synthesize",
        )
        roles = (
            GraphRole.SUPERVISOR,
            GraphRole.LEAD,
            GraphRole.SPECIALIST,
            GraphRole.LEAD,
            GraphRole.SUPERVISOR,
        )
        for phase, (name, role) in enumerate(zip(nodes, roles, strict=True)):
            add_stage(name, role, phase)
        for parent, child in zip(
            ("__start__", *nodes), (*nodes, "__end__"), strict=True
        ):
            graph.add_edge(parent, child)
    else:
        add_stage("fanout", GraphRole.AGGREGATOR, 0)
        for name, role in (("left", GraphRole.LEFT), ("right", GraphRole.RIGHT)):

            async def branch(state, owner=role):
                raw = await run_branch(state, expected, owner)
                return validate_node_update(
                    raw, parallel_branch(state, expected, owner)
                )

            graph.add_node(name, branch)

        async def aggregate(state):
            return parallel_aggregate(state, expected)

        graph.add_node("aggregate", aggregate)
        graph.add_edge("__start__", "fanout")
        graph.add_edge("fanout", "left")
        graph.add_edge("fanout", "right")
        graph.add_edge(["left", "right"], "aggregate")
        graph.add_edge("aggregate", "__end__")
    return graph.compile()


async def execute_topology(expected: WorkflowRequest, graph_type) -> RuntimeOutput:
    """Use compiled.ainvoke and native scheduler cleanup under caller timeout."""
    check_topology_budget(expected)
    plan = topology_plan(expected.topology)
    compiled = compile_topology(expected, graph_type)
    with import_module("langsmith").tracing_context(enabled=False):
        raw = await compiled.ainvoke(
            TopologyState(request=expected).model_dump(),
            config={
                "recursion_limit": plan.steps + 1,
                "max_concurrency": plan.concurrency,
            },
        )
    phase = {
        GraphTopology.SEQUENTIAL: 3,
        GraphTopology.PARALLEL: 2,
        GraphTopology.HIERARCHICAL: 5,
    }[expected.topology]
    state = validate_topology_state(raw, expected, phase)
    return RuntimeOutput(
        workflow_id=expected.workflow_id,
        runtime=RuntimeId.LANGGRAPH,
        topology=expected.topology,
        result=AgentTaskResult(
            task_id=expected.task.task_id,
            agent_id=plan.roles[-1].value,
            status=ExecutionStatus.COMPLETED,
            output=state.contributions[-1].content,
        ),
        contributions=state.contributions,
    )
