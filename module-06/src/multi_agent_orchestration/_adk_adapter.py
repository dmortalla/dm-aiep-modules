"""Private SDK boundary: real Workflow scheduling, Runner events, and sessions."""

from contextlib import aclosing

from pydantic import PrivateAttr

from .contracts import (
    AgentTaskResult,
    ExecutionStatus,
    OrchestrationRole,
    OrchestrationState,
    RuntimeId,
    RuntimeOutput,
    WorkflowRequest,
)
from .errors import (
    ExecutionFailureError,
    InvalidRuntimeOutputError,
    InvalidWorkflowRequestError,
    StepBudgetExceededError,
)
from .orchestration import advance_orchestration, validate_orchestration_state


def build_workflow(expected: WorkflowRequest):
    """Build three custom BaseAgents linked by the installed native Workflow API."""
    from google.adk.agents import BaseAgent
    from google.adk.events import Event, EventActions
    from google.adk.workflow import START, Workflow

    class DeterministicAgent(BaseAgent):
        _owner: OrchestrationRole = PrivateAttr()

        async def _run_async_impl(self, ctx):
            if self.name != self._owner.value or ctx.agent is not self:
                raise InvalidRuntimeOutputError("ADK role ownership is invalid.")
            state = advance_orchestration(
                ctx.session.state.get("workflow"), expected, self._owner
            )
            data = state.model_dump(mode="json")
            yield Event(
                author=self.name,
                output=data,
                actions=EventActions(state_delta={"workflow": data}),
            )

    agents = []
    for role in OrchestrationRole:
        agent = DeterministicAgent(name=role.value)
        agent._owner = role
        agents.append(agent)
    return Workflow(name="bounded_adk", edges=[(START, *agents)], max_concurrency=1)


async def run_adk(request: WorkflowRequest) -> RuntimeOutput:
    """Execute one local in-memory workflow; validate every event and final state.

    No LlmAgent, provider, tool, model, plugin, external service, or retry is used.
    The caller supplies the deadline. Closing the event generator cancels and
    gathers native Workflow tasks; production additionally kills/reaps its child.
    """
    from google.adk.agents.run_config import RunConfig
    from google.adk.runners import InMemoryRunner
    from google.adk.telemetry.context import TelemetryConfig
    from google.genai import types

    expected = WorkflowRequest.model_validate(request.model_dump())
    if expected.runtime != RuntimeId.GOOGLE_ADK:
        raise InvalidWorkflowRequestError("ADK requires explicit matching selection.")
    if (
        min(
            expected.limits.max_steps,
            expected.limits.max_tasks,
            expected.limits.max_messages,
        )
        < 3
    ):
        raise StepBudgetExceededError(
            "ADK requires three authorized steps/tasks/messages."
        )
    workflow = build_workflow(expected)
    roles = tuple(OrchestrationRole)
    app_name, user_id, session_id = "module06_adk", "local", str(expected.workflow_id)
    async with InMemoryRunner(node=workflow, app_name=app_name) as runner:
        await runner.session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            state={
                "workflow": OrchestrationState(request=expected).model_dump(mode="json")
            },
        )
        count = 0
        async with aclosing(
            runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part(text="Execute bounded local workflow.")],
                ),
                run_config=RunConfig(
                    # ADK interprets zero as unlimited. No model path exists; one is
                    # a defensive SDK ceiling, never permission to call a model.
                    max_llm_calls=1,
                    telemetry=TelemetryConfig(adk_experimental_telemetry_opt_in=False),
                ),
            )
        ) as events:
            async for event in events:
                if event.error_code or event.error_message:
                    raise ExecutionFailureError(
                        "ADK native execution failed."
                    ) from RuntimeError(event.error_message or event.error_code)
                count += 1
                if count > 3 or event.author != roles[count - 1].value:
                    raise InvalidRuntimeOutputError(
                        "ADK event ownership/order is invalid."
                    )
                state = validate_orchestration_state(event.output, expected, count)
                data = state.model_dump(mode="json")
                # Reject transfers, routes, tool/auth/artifact actions, or other
                # control-plane output, even if the native SDK would accept it.
                actions = event.actions.model_dump(
                    exclude_defaults=True, exclude_none=True
                )
                if (
                    actions != {"state_delta": {"workflow": data}}
                    or event.content is not None
                    or event.partial
                    or event.long_running_tool_ids
                    or event.usage_metadata is not None
                ):
                    raise InvalidRuntimeOutputError(
                        "ADK event contains unauthorized actions."
                    )
        if count != 3:
            raise InvalidRuntimeOutputError("ADK workflow did not complete all roles.")
        session = await runner.session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
        if (
            session is None
            or session.id != session_id
            or session.user_id != user_id
            or session.app_name != app_name
            or set(session.state) != {"workflow"}
        ):
            raise InvalidRuntimeOutputError("ADK session state is invalid.")
        final = validate_orchestration_state(session.state["workflow"], expected, 3)
        return RuntimeOutput(
            workflow_id=expected.workflow_id,
            runtime=RuntimeId.GOOGLE_ADK,
            result=AgentTaskResult(
                task_id=expected.task.task_id,
                agent_id="adk_validator",
                status=ExecutionStatus.COMPLETED,
                output=final.messages[-1].content,
            ),
            orchestration=final.messages,
        )
