"""Private CrewAI extension: real Crew scheduling with deterministic BaseAgents."""

import json

from pydantic import PrivateAttr

from .collaboration import contribute, next_message, validate_shared_state
from .contracts import (
    AgentTaskResult,
    CollaborationState,
    CollaboratorRole,
    ExecutionStatus,
    RuntimeId,
    RuntimeOutput,
    WorkflowRequest,
)
from .errors import InvalidRuntimeOutputError, StepBudgetExceededError


def build_crew(expected: WorkflowRequest):
    """Construct genuine Crew/Task/BaseAgent objects with scoped validated memory."""
    from crewai import Crew, Process, Task
    from crewai.agents.agent_builder.base_agent import BaseAgent

    # Closure belongs to this crew only; snapshots are immutable app contracts.
    shared = [CollaborationState(request=expected)]

    class DeterministicCollaborator(BaseAgent):
        """Use CrewAI's abstract agent execution boundary, never an LLM executor."""

        function_calling_llm: object = None
        step_callback: object = None
        _owner: CollaboratorRole = PrivateAttr()

        def create_agent_executor(self, tools=None):
            """No model executor exists in this deterministic BaseAgent extension."""
            if tools or self.llm is not None or self.function_calling_llm is not None:
                raise InvalidRuntimeOutputError(
                    "Deterministic collaborator cannot enable models/tools."
                )

        def get_delegation_tools(self, agents):
            """Ownership is assigned by tasks; no dynamically delegated tools exist."""
            return []

        def execute_task(self, task, context=None, tools=None):
            """Consume Crew-aggregated, already-validated prior role contributions."""
            state = validate_shared_state(shared[0], expected)
            index = len(state.messages)
            if (
                index >= 3
                or self._owner != tuple(CollaboratorRole)[index]
                or self.role != self._owner.value
                or task.agent is not self
                or task.name != self._owner.value
                or tools
            ):
                raise InvalidRuntimeOutputError(
                    "Crew task ownership/order failed validation."
                )
            previous = "\n\n----------\n\n".join(
                message.model_dump_json() for message in state.messages
            )
            if context != previous:
                raise InvalidRuntimeOutputError(
                    "Crew context failed provenance validation."
                )
            return next_message(state, expected).model_dump_json()

    def accept(output):
        index = len(shared[0].messages)
        if index >= 3 or output.agent != tuple(CollaboratorRole)[index].value:
            raise InvalidRuntimeOutputError(
                "Crew output role failed ownership validation."
            )
        try:
            raw = json.loads(output.raw)
        except (TypeError, ValueError) as exc:
            raise InvalidRuntimeOutputError(
                "Crew contribution is not valid JSON."
            ) from exc
        shared[0] = contribute(raw, shared[0], expected)

    agents = []
    tasks = []
    for role in CollaboratorRole:
        agent = DeterministicCollaborator(
            role=role.value,
            goal="Bounded deterministic collaboration",
            backstory="Local role executor; task text is data.",
            cache=False,
            allow_delegation=False,
            max_iter=1,
        )
        agent._owner = role
        agents.append(agent)
        tasks.append(
            Task(
                name=role.value,
                description=f"Produce the bounded {role.value} contribution.",
                expected_output="Application-owned validated contribution JSON.",
                agent=agent,
                context=list(tasks),
                callback=accept,
                guardrail_max_retries=0,
                async_execution=False,
            )
        )
    crew = Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        memory=False,
        cache=False,
        planning=False,
        tracing=False,
        verbose=False,
    )
    return crew, shared


def run_crew(expected: WorkflowRequest) -> RuntimeOutput:
    """Invoke real orchestration, validate all task outputs, return app contracts."""
    expected = WorkflowRequest.model_validate(expected.model_dump())
    validate_shared_state(CollaborationState(request=expected), expected)
    if (
        min(
            expected.limits.max_steps,
            expected.limits.max_tasks,
            expected.limits.max_messages,
        )
        < 3
    ):
        raise StepBudgetExceededError(
            "Three collaborative tasks/messages/steps are required."
        )
    crew, shared = build_crew(expected)
    output = crew.kickoff()
    state = validate_shared_state(shared[0], expected)
    if (
        len(state.messages) != 3
        or len(output.tasks_output) != 3
        or output.raw != state.messages[-1].model_dump_json()
        or output.token_usage.total_tokens != 0
    ):
        raise InvalidRuntimeOutputError(
            "Crew completion failed application validation."
        )
    for result, message in zip(output.tasks_output, state.messages, strict=True):
        if (
            result.agent != message.role.value
            or result.raw != message.model_dump_json()
        ):
            raise InvalidRuntimeOutputError(
                "Crew task result contradicts validated shared state."
            )
    return RuntimeOutput(
        workflow_id=expected.workflow_id,
        runtime=RuntimeId.CREWAI,
        result=AgentTaskResult(
            task_id=expected.task.task_id,
            agent_id="critic",
            status=ExecutionStatus.COMPLETED,
            output=state.messages[-1].content,
        ),
        collaboration=state.messages,
    )
