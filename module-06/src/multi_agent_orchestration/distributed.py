"""Pure finite delegation, strict JSON protocol, and untrusted worker validation."""

import json
from uuid import uuid4

from pydantic import ValidationError

from .contracts import GraphTopology, RuntimeId, WorkflowRequest
from .distributed_contracts import (
    MAX_PACKET_BYTES,
    WorkerAssignment,
    WorkerId,
    WorkerResponse,
    WorkerRole,
)
from .errors import (
    InvalidRuntimeOutputError,
    InvalidWorkflowRequestError,
    StepBudgetExceededError,
)


def validate_request(raw: object) -> WorkflowRequest:
    try:
        request = WorkflowRequest.model_validate(
            raw.model_dump() if isinstance(raw, WorkflowRequest) else raw
        )
        request = WorkflowRequest.model_validate(request.model_dump())
    except ValidationError as exc:
        raise InvalidWorkflowRequestError(
            "Distributed request failed contract validation."
        ) from exc
    if (
        request.runtime != RuntimeId.GOOGLE_ADK
        or request.topology != GraphTopology.COORDINATOR_WORKER
    ):
        raise InvalidWorkflowRequestError(
            "Local distribution requires explicit Google ADK selection."
        )
    if (
        request.limits.max_steps < 4
        or request.limits.max_tasks < 3
        or request.limits.max_messages < 3
        or request.limits.max_concurrency < 2
    ):
        raise StepBudgetExceededError(
            "Distribution requires four steps, three tasks/messages "
            "and concurrency two."
        )
    return request


def make_assignments(request: WorkflowRequest, coordinator_pid: int) -> tuple:
    request = validate_request(request)
    text = request.task.instruction
    split = (len(text) + 1) // 2
    return tuple(
        WorkerAssignment(
            workflow_id=request.workflow_id,
            task_id=request.task.task_id,
            assignment_id=uuid4(),
            worker=worker,
            role=tuple(WorkerRole)[index],
            sequence=index + 1,
            coordinator_pid=coordinator_pid,
            limits=request.limits,
            fragment=(text[:split], text[split:])[index],
        )
        for index, worker in enumerate(WorkerId)
    )


def encode_packet(packet) -> bytes:
    data = (
        json.dumps(
            packet.model_dump(mode="json"),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )
    if len(data) > MAX_PACKET_BYTES:
        raise InvalidRuntimeOutputError("Protocol packet exceeds the hard byte limit.")
    return data


def decode_packet(data: bytes, schema):
    """Reject duplicate keys, non-finite values, malformed UTF-8 and extra fields."""

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate protocol key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("Non-finite protocol value")

    try:
        if len(data) > MAX_PACKET_BYTES or not data.endswith(b"\n"):
            raise ValueError("Invalid protocol framing")
        raw = json.loads(
            data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant
        )
        parsed = schema.model_validate(raw)
        return schema.model_validate(parsed.model_dump())
    except (ValidationError, ValueError, TypeError) as exc:
        raise InvalidRuntimeOutputError(
            "Serialized worker packet failed validation."
        ) from exc


def validate_assignment(raw: object) -> WorkerAssignment:
    try:
        assignment = WorkerAssignment.model_validate(
            raw.model_dump() if isinstance(raw, WorkerAssignment) else raw
        )
        return WorkerAssignment.model_validate(assignment.model_dump())
    except ValidationError as exc:
        raise InvalidWorkflowRequestError(
            "Worker assignment failed contract validation."
        ) from exc


def expected_response(assignment: WorkerAssignment, pid: int) -> WorkerResponse:
    assignment = validate_assignment(assignment)
    return WorkerResponse(
        **assignment.model_dump(exclude={"kind", "fragment"}),
        pid=pid,
        characters=len(assignment.fragment),
    )


def validate_response(raw: object, assignment: WorkerAssignment, pid: int):
    try:
        response = WorkerResponse.model_validate(
            raw.model_dump() if isinstance(raw, WorkerResponse) else raw
        )
        response = WorkerResponse.model_validate(response.model_dump())
    except ValidationError as exc:
        raise InvalidRuntimeOutputError(
            "Worker result failed schema validation."
        ) from exc
    if response != expected_response(assignment, pid):
        raise InvalidRuntimeOutputError(
            "Worker result contradicts authorized ownership/context/provenance."
        )
    return response


def validate_responses(raw: tuple, assignments: tuple, pids: tuple) -> tuple:
    """Require each assignment exactly once, independent of completion order."""
    if len(raw) != 2 or len(assignments) != 2 or len(pids) != 2 or len(set(pids)) != 2:
        raise InvalidRuntimeOutputError(
            "Distribution requires two independent workers."
        )
    validated = []
    for assignment, pid in zip(assignments, pids, strict=True):
        matches = [
            item
            for item in raw
            if getattr(item, "assignment_id", None) == assignment.assignment_id
        ]
        if len(matches) != 1:
            raise InvalidRuntimeOutputError(
                "Missing, duplicate or replayed worker result."
            )
        validated.append(validate_response(matches[0], assignment, pid))
    return tuple(validated)
