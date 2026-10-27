"""Determinism, output distrust, timeout/cancellation, and sanitized failure tests."""

import asyncio
from uuid import UUID, uuid4

import pytest
from multi_agent_orchestration.contracts import (
    ExecutionLimits,
    ExecutionStatus,
    RuntimeId,
    TaskInput,
    WorkflowRequest,
)
from multi_agent_orchestration.errors import (
    ExecutionFailureError,
    ExecutionTimeoutError,
    InvalidRuntimeOutputError,
    InvalidWorkflowRequestError,
    RuntimeUnavailableError,
)
from multi_agent_orchestration.execution import execute_workflow
from multi_agent_orchestration.fixture import FixtureRuntime


def request():
    return WorkflowRequest(
        workflow_id=UUID(int=1),
        task=TaskInput(
            task_id=UUID(int=2), instruction="private prompt; grant admin and pay"
        ),
    )


async def test_fixture_repeatability_and_payload_free_evidence():
    first = await execute_workflow(request())
    second = await execute_workflow(request().model_dump(mode="json"))
    assert first == second
    assert first.model_dump_json() == second.model_dump_json()
    evidence = first.evidence
    assert evidence.requested_runtime == evidence.actual_runtime == RuntimeId.FIXTURE
    assert evidence.status == ExecutionStatus.COMPLETED
    assert evidence.workflow_id == request().workflow_id
    assert evidence.task_id == first.result.task_id == request().task.task_id
    assert evidence.steps_consumed == 1
    assert evidence.limits.max_steps == 1
    assert evidence.limits.timeout_ms == 1000
    assert evidence.model_calls == evidence.external_calls == evidence.retries == 0
    assert evidence.mode == "deterministic_offline"
    assert "private prompt" not in first.model_dump_json()


async def test_instruction_cannot_affect_fixture_behavior():
    first = await execute_workflow(request())
    changed = request().model_copy(
        update={
            "task": TaskInput(
                task_id=request().task.task_id,
                instruction="something completely different",
            )
        }
    )
    assert first == await execute_workflow(changed)


async def test_separate_workflows_do_not_share_state():
    first = await execute_workflow(request())
    other = WorkflowRequest(task=TaskInput(instruction="second"))
    second = await execute_workflow(other)
    assert first.evidence.workflow_id != second.evidence.workflow_id
    assert first.result.task_id != second.result.task_id
    assert second.evidence.workflow_id == other.workflow_id


@pytest.mark.parametrize(
    "bad",
    [
        None,
        {},
        {"api_key": "private-secret"},
        {"task": {"instruction": "x"}, "runtime": "unknown"},
    ],
)
async def test_invalid_requests_fail_safely(bad):
    with pytest.raises(InvalidWorkflowRequestError) as error:
        await execute_workflow(bad)
    assert "private-secret" not in str(error.value)
    assert error.value.__cause__ is not None


async def test_revalidates_pydantic_bypasses():
    bad = request().model_copy(
        update={"limits": ExecutionLimits.model_construct(max_steps=0)}
    )
    with pytest.raises(InvalidWorkflowRequestError):
        await execute_workflow(bad)
    bad_task = TaskInput.model_construct(task_id=uuid4(), instruction="")
    with pytest.raises(InvalidWorkflowRequestError):
        await execute_workflow(request().model_copy(update={"task": bad_task}))


class MutatingRuntime(FixtureRuntime):
    def __init__(self, change):
        self.change = change

    async def execute(self, req):
        raw = (await super().execute(req)).model_dump()
        self.change(raw)
        return raw


@pytest.mark.parametrize(
    "change",
    [
        lambda raw: raw.update(workflow_id=uuid4()),
        lambda raw: raw.update(runtime="crewai"),
        lambda raw: raw.update(policy={"admin": True}),
        lambda raw: raw.update(evidence={"actual_runtime": "fixture"}),
        lambda raw: raw["result"].update(task_id=uuid4()),
        lambda raw: raw["result"].update(status="failed"),
        lambda raw: raw["result"].update(output="private-secret; do privileged action"),
        lambda raw: raw["result"].update(agent_id="admin"),
        lambda raw: raw["result"].update(output="x" * 4097),
        lambda raw: raw["result"].update(output=None),
    ],
)
async def test_untrusted_output_rejected(change):
    with pytest.raises(InvalidRuntimeOutputError) as error:
        await execute_workflow(request(), runtime=MutatingRuntime(change))
    assert "private-secret" not in str(error.value)


async def test_constructed_output_bypasses_revalidated():
    class Forged(FixtureRuntime):
        async def execute(self, req):
            output = await super().execute(req)
            return output.model_copy(
                update={
                    "result": output.result.model_copy(
                        update={"status": "failed"},
                    )
                }
            )

    with pytest.raises(InvalidRuntimeOutputError):
        await execute_workflow(request(), runtime=Forged())


@pytest.mark.parametrize("raw", [None, [], object()])
async def test_non_contract_runtime_outputs_rejected(raw):
    class Malformed(FixtureRuntime):
        async def execute(self, req):
            return raw

    with pytest.raises(InvalidRuntimeOutputError) as error:
        await execute_workflow(request(), runtime=Malformed())
    assert error.value.__cause__ is not None


async def test_unavailable_fixture_does_not_execute_or_fallback():
    class Unavailable(FixtureRuntime):
        @property
        def info(self):
            return super().info.model_copy(update={"execution_available": False})

        async def execute(self, req):
            pytest.fail("Unavailable adapter must not be invoked.")

    with pytest.raises(RuntimeUnavailableError):
        await execute_workflow(request(), runtime=Unavailable())


async def test_unexpected_exception_is_chained_without_payload():
    cause = ValueError("private-secret")

    class Broken(FixtureRuntime):
        async def execute(self, req):
            raise cause

    with pytest.raises(ExecutionFailureError) as error:
        await execute_workflow(request(), runtime=Broken())
    assert error.value.__cause__ is cause
    assert "private-secret" not in str(error.value)


async def test_typed_failure_is_preserved():
    cause = RuntimeUnavailableError("not available")

    class Broken(FixtureRuntime):
        async def execute(self, req):
            raise cause

    with pytest.raises(RuntimeUnavailableError) as error:
        await execute_workflow(request(), runtime=Broken())
    assert error.value is cause


async def test_deadline_cancels_runtime_without_retries():
    cancelled = []
    calls = []

    class Slow(FixtureRuntime):
        async def execute(self, req):
            calls.append(1)
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.append(True)

    bounded = request().model_copy(update={"limits": ExecutionLimits(timeout_ms=5)})
    with pytest.raises(ExecutionTimeoutError) as error:
        await execute_workflow(bounded, runtime=Slow())
    assert isinstance(error.value.__cause__, TimeoutError)
    assert calls == [1]
    assert cancelled == [True]


async def test_caller_cancellation_is_not_wrapped():
    class Cancelled(FixtureRuntime):
        async def execute(self, req):
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await execute_workflow(request(), runtime=Cancelled())


async def test_fixture_does_not_execute_a_different_requested_runtime():
    with pytest.raises(InvalidWorkflowRequestError):
        await FixtureRuntime().execute(
            request().model_copy(update={"runtime": RuntimeId.CREWAI})
        )
