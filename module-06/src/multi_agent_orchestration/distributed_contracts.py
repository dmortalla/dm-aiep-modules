"""Application-owned immutable contracts for the explicit local process slice."""

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from .contracts import Contract, ExecutionLimits, RuntimeId

MAX_PACKET_BYTES = 16_384


class WorkerId(StrEnum):
    LEFT = "worker_left"
    RIGHT = "worker_right"


class WorkerRole(StrEnum):
    LEFT = "left_counter"
    RIGHT = "right_counter"


class AssignmentIdentity(Contract):
    protocol: Annotated[int, Field(strict=True, ge=1, le=1)] = 1
    workflow_id: UUID
    task_id: UUID
    assignment_id: UUID
    worker: WorkerId
    role: WorkerRole
    sequence: Annotated[int, Field(strict=True, ge=1, le=2)]
    coordinator_pid: Annotated[int, Field(strict=True, ge=1)]
    parent: Literal["distributed_coordinator"] = "distributed_coordinator"
    capability: Literal["count_characters"] = "count_characters"
    runtime: Literal[RuntimeId.GOOGLE_ADK] = RuntimeId.GOOGLE_ADK
    limits: ExecutionLimits

    @model_validator(mode="after")
    def ownership(self):
        index = tuple(WorkerId).index(self.worker)
        if self.role != tuple(WorkerRole)[index] or self.sequence != index + 1:
            raise ValueError("Worker role/sequence contradicts assignment ownership.")
        if (
            self.limits.max_steps < 4
            or self.limits.max_tasks < 3
            or self.limits.max_messages < 3
            or self.limits.max_concurrency < 2
        ):
            raise ValueError("Distribution requires bounded authorized work.")
        return self


class WorkerAssignment(AssignmentIdentity):
    kind: Literal["assignment"] = "assignment"
    fragment: Annotated[str, Field(strict=True, max_length=2048)] = Field(repr=False)


class WorkerResponse(AssignmentIdentity):
    kind: Literal["result"] = "result"
    pid: Annotated[int, Field(strict=True, ge=1)]
    characters: Annotated[int, Field(strict=True, ge=0, le=2048)]


class WorkerReady(Contract):
    protocol: Annotated[int, Field(strict=True, ge=1, le=1)] = 1
    kind: Literal["ready"] = "ready"
    worker: WorkerId
    pid: Annotated[int, Field(strict=True, ge=1)]
    coordinator_pid: Annotated[int, Field(strict=True, ge=1)]


class WorkerStarted(Contract):
    protocol: Annotated[int, Field(strict=True, ge=1, le=1)] = 1
    kind: Literal["started"] = "started"
    workflow_id: UUID
    task_id: UUID
    assignment_id: UUID
    worker: WorkerId
    role: WorkerRole
    pid: Annotated[int, Field(strict=True, ge=1)]


class WorkerRelease(Contract):
    protocol: Annotated[int, Field(strict=True, ge=1, le=1)] = 1
    kind: Literal["release"] = "release"
    assignment_id: UUID
    worker: WorkerId
    coordinator_pid: Annotated[int, Field(strict=True, ge=1)]


class WorkerFailure(Contract):
    protocol: Annotated[int, Field(strict=True, ge=1, le=1)] = 1
    kind: Literal["failure"] = "failure"
    category: Literal["invalid_assignment", "invalid_output", "execution", "offline"]
    cause_type: Annotated[
        str,
        Field(
            strict=True,
            min_length=1,
            max_length=64,
            pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
        ),
    ] = "RuntimeError"


class WorkerRecord(Contract):
    """Coordinator-created payload-free provenance, never worker-created evidence."""

    assignment_id: UUID
    worker: WorkerId
    role: WorkerRole
    sequence: Annotated[int, Field(strict=True, ge=1, le=2)]
    pid: Annotated[int, Field(strict=True, ge=1)]
    parent: Literal["distributed_coordinator"] = "distributed_coordinator"
    capability: Literal["count_characters"] = "count_characters"


class DistributedEvidence(Contract):
    workflow_id: UUID
    task_id: UUID
    runtime: Literal[RuntimeId.GOOGLE_ADK] = RuntimeId.GOOGLE_ADK
    mode: Literal["deterministic_local_multi_process"] = (
        "deterministic_local_multi_process"
    )
    coordinator_pid: Annotated[int, Field(strict=True, ge=1)]
    limits: ExecutionLimits
    steps_consumed: Literal[4] = 4
    workers_at_barrier: Literal[2] = 2
    protocol_packets: Literal[10] = 10
    model_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    external_calls: Literal[0] = 0
    retries: Literal[0] = 0
    workers: Annotated[tuple[WorkerRecord, ...], Field(min_length=2, max_length=2)]

    @model_validator(mode="after")
    def consistency(self):
        if (
            tuple(record.worker for record in self.workers) != tuple(WorkerId)
            or tuple(record.role for record in self.workers) != tuple(WorkerRole)
            or tuple(record.sequence for record in self.workers) != (1, 2)
            or len({record.pid for record in self.workers}) != 2
            or len({record.assignment_id for record in self.workers}) != 2
            or self.coordinator_pid in {record.pid for record in self.workers}
            or self.limits.max_steps < 4
            or self.limits.max_tasks < 3
            or self.limits.max_messages < 3
            or self.limits.max_concurrency < 2
        ):
            raise ValueError("Distributed evidence contradicts process/work bounds.")
        return self


class DistributedResult(Contract):
    workflow_id: UUID
    task_id: UUID
    status: Literal["completed"] = "completed"
    characters: Annotated[int, Field(strict=True, ge=1, le=4096)]
    output: Annotated[str, Field(strict=True, max_length=256)]
    evidence: DistributedEvidence

    @model_validator(mode="after")
    def consistency(self):
        if (
            self.workflow_id != self.evidence.workflow_id
            or self.task_id != self.evidence.task_id
            or self.output
            != f"Distributed synthesis accepted {self.characters} characters."
        ):
            raise ValueError("Distributed result contradicts application evidence.")
        return self
