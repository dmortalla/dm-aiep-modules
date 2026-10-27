"""Private native ADK scheduling for exactly one authorized worker assignment."""

from contextlib import aclosing

from .distributed import expected_response, validate_assignment, validate_response
from .errors import ExecutionFailureError, InvalidRuntimeOutputError


async def run_assignment(assignment, pid: int, barrier):
    """The native role enters the IPC barrier before processing its local fragment."""
    from google.adk.agents import BaseAgent
    from google.adk.agents.run_config import RunConfig
    from google.adk.events import Event, EventActions
    from google.adk.runners import InMemoryRunner
    from google.adk.telemetry.context import TelemetryConfig
    from google.adk.workflow import START, Workflow
    from google.genai import types

    expected = validate_assignment(assignment)

    class AssignedWorker(BaseAgent):
        async def _run_async_impl(self, ctx):
            state = validate_assignment(ctx.session.state.get("assignment"))
            if (
                self.name != expected.role.value
                or ctx.agent is not self
                or state != expected
            ):
                raise InvalidRuntimeOutputError("ADK worker scope is invalid.")
            await barrier(state)
            state = validate_assignment(ctx.session.state.get("assignment"))
            if state != expected:
                raise InvalidRuntimeOutputError("ADK worker context was altered.")
            response = expected_response(state, pid)
            data = response.model_dump(mode="json")
            yield Event(
                author=self.name,
                output=data,
                actions=EventActions(state_delta={"response": data}),
            )

    agent = AssignedWorker(name=expected.role.value)
    workflow = Workflow(
        name="distributed_worker", edges=[(START, agent)], max_concurrency=1
    )
    app_name, user_id = "module06_distributed", "local"
    session_id = str(expected.assignment_id)
    async with InMemoryRunner(node=workflow, app_name=app_name) as runner:
        await runner.session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            state={"assignment": expected.model_dump(mode="json")},
        )
        count, response = 0, None
        async with aclosing(
            runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=types.Content(
                    role="user", parts=[types.Part(text="Execute bounded assignment.")]
                ),
                run_config=RunConfig(
                    max_llm_calls=1,
                    telemetry=TelemetryConfig(adk_experimental_telemetry_opt_in=False),
                ),
            )
        ) as events:
            async for event in events:
                if event.error_code or event.error_message:
                    raise ExecutionFailureError("ADK worker execution failed.") from (
                        RuntimeError(event.error_message or event.error_code)
                    )
                count += 1
                if count != 1 or event.author != expected.role.value:
                    raise InvalidRuntimeOutputError(
                        "ADK worker event ownership is invalid."
                    )
                response = validate_response(event.output, expected, pid)
                actions = event.actions.model_dump(
                    exclude_defaults=True, exclude_none=True
                )
                if (
                    actions
                    != {"state_delta": {"response": response.model_dump(mode="json")}}
                    or event.content is not None
                    or event.partial
                    or event.long_running_tool_ids
                    or event.usage_metadata is not None
                ):
                    raise InvalidRuntimeOutputError(
                        "ADK worker proposed unauthorized actions."
                    )
        session = await runner.session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
        if (
            count != 1
            or session is None
            or session.id != session_id
            or session.user_id != user_id
            or session.app_name != app_name
            or set(session.state) != {"assignment", "response"}
            or validate_assignment(session.state["assignment"]) != expected
            or validate_response(session.state["response"], expected, pid) != response
        ):
            raise InvalidRuntimeOutputError("ADK worker final state is invalid.")
    return response
