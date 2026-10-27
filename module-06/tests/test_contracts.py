"""Schema, immutability, serialization, and authority-injection boundary tests."""

from uuid import UUID, uuid4

import pytest
from multi_agent_orchestration.contracts import (
    AgentTaskResult,
    ExecutionEvidence,
    ExecutionLimits,
    ExecutionStatus,
    RuntimeId,
    RuntimeOutput,
    TaskInput,
    ValidatedWorkflowResult,
    WorkflowRequest,
)
from pydantic import ValidationError


@pytest.mark.parametrize("instruction", ["", "   ", "x" * 4097, 5, None])
def test_invalid_task_instructions(instruction):
    with pytest.raises(ValidationError):
        TaskInput(instruction=instruction)


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_steps", 0),
        ("max_steps", 33),
        ("max_steps", True),
        ("max_steps", "1"),
        ("timeout_ms", 0),
        ("timeout_ms", 30_001),
        ("timeout_ms", 1.5),
        ("timeout_ms", False),
    ],
)
def test_limits_are_strict_and_bounded(field, value):
    with pytest.raises(ValidationError):
        ExecutionLimits(**{field: value})


@pytest.mark.parametrize("field", ["api_key", "provider", "allow_paid", "policy"])
def test_request_cannot_grant_authority(field):
    with pytest.raises(ValidationError):
        WorkflowRequest(task=TaskInput(instruction="test"), **{field: "forged"})


@pytest.mark.parametrize("runtime", ["unknown", "", None, 1])
def test_request_requires_known_runtime(runtime):
    with pytest.raises(ValidationError):
        WorkflowRequest(task=TaskInput(instruction="test"), runtime=runtime)


def test_request_roundtrip_and_immutable_nested_values():
    request = WorkflowRequest(task=TaskInput(instruction="test"))
    assert request.runtime == RuntimeId.FIXTURE
    assert isinstance(request.workflow_id, UUID)
    assert WorkflowRequest.model_validate_json(request.model_dump_json()) == request
    with pytest.raises(ValidationError):
        request.runtime = RuntimeId.CREWAI
    with pytest.raises(ValidationError):
        request.limits.max_steps = 32
    with pytest.raises(ValidationError):
        request.task.instruction = "changed"


@pytest.mark.parametrize("field", ["workflow_id", "task_id"])
def test_ids_cannot_carry_arbitrary_sensitive_text(field):
    with pytest.raises(ValidationError):
        if field == "workflow_id":
            WorkflowRequest(
                workflow_id="secret-payload", task=TaskInput(instruction="x")
            )
        else:
            TaskInput(task_id="secret-payload", instruction="x")


def test_sensitive_instruction_is_not_in_repr():
    task = TaskInput(instruction="private-instruction")
    assert "private-instruction" not in repr(task)


@pytest.mark.parametrize("status", [ExecutionStatus.FAILED, "running", "forged"])
def test_success_candidate_rejects_other_status(status):
    with pytest.raises(ValidationError):
        AgentTaskResult(
            task_id=uuid4(), agent_id="fixture_agent", status=status, output="x"
        )


def test_result_and_evidence_cannot_disagree():
    result = AgentTaskResult(
        task_id=uuid4(),
        agent_id="fixture_agent",
        status=ExecutionStatus.COMPLETED,
        output="x",
    )
    evidence = ExecutionEvidence(
        workflow_id=uuid4(),
        task_id=uuid4(),
        requested_runtime=RuntimeId.FIXTURE,
        actual_runtime=RuntimeId.FIXTURE,
        status=ExecutionStatus.COMPLETED,
        limits=ExecutionLimits(),
    )
    with pytest.raises(ValidationError):
        ValidatedWorkflowResult(result=result, evidence=evidence)
    with pytest.raises(ValidationError):
        ValidatedWorkflowResult(
            result=result,
            evidence=evidence.model_copy(
                update={
                    "task_id": result.task_id,
                    "actual_runtime": RuntimeId.CREWAI,
                }
            ),
        )


def test_runtime_candidate_cannot_supply_trusted_evidence():
    with pytest.raises(ValidationError):
        RuntimeOutput(workflow_id=uuid4(), runtime="fixture", result={}, evidence={})
