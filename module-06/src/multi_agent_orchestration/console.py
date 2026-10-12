"""Bounded application service and curated views for the operations console."""

import asyncio
import threading
import time
from collections import deque
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from .contracts import (
    Contract,
    ExecutionEvidence,
    ExecutionLimits,
    GraphTopology,
    RuntimeId,
    TaskInput,
    ValidatedWorkflowResult,
    WorkflowRequest,
)
from .distributed_contracts import DistributedEvidence, DistributedResult
from .errors import (
    ExecutionTimeoutError,
    InvalidRuntimeOutputError,
    InvalidWorkflowRequestError,
    RuntimeUnavailableError,
    StepBudgetExceededError,
)
from .observability import Observability
from .observability_adapters import LocalLangSmith, LocalOpenTelemetry, checked_trace
from .observability_contracts import Outcome, RunTrace
from .observed_execution import execute_observed_workflow


class Demonstration(StrEnum):
    FIXTURE = "Deterministic fixture"
    COORDINATOR = "LangGraph coordinator-worker"
    SEQUENTIAL = "LangGraph sequential"
    PARALLEL = "LangGraph parallel"
    HIERARCHICAL = "LangGraph hierarchical"
    CREWAI = "CrewAI collaboration"
    ADK = "Google ADK orchestration"
    DISTRIBUTED = "Local multi-process distributed orchestration"


def selection(mode: Demonstration):
    """Closed application selection, never runtime/provider strings from a model."""
    mode = Demonstration(mode)
    runtime = (
        RuntimeId.FIXTURE
        if mode == Demonstration.FIXTURE
        else RuntimeId.CREWAI
        if mode == Demonstration.CREWAI
        else RuntimeId.GOOGLE_ADK
        if mode in (Demonstration.ADK, Demonstration.DISTRIBUTED)
        else RuntimeId.LANGGRAPH
    )
    topology = {
        Demonstration.SEQUENTIAL: GraphTopology.SEQUENTIAL,
        Demonstration.PARALLEL: GraphTopology.PARALLEL,
        Demonstration.HIERARCHICAL: GraphTopology.HIERARCHICAL,
    }.get(mode, GraphTopology.COORDINATOR_WORKER)
    return runtime, topology, mode == Demonstration.DISTRIBUTED


def guidance(mode: Demonstration) -> str:
    """Static reviewer guidance; no caller content is interpolated."""
    return {
        Demonstration.FIXTURE: (
            "One fixed task result proves the offline request/result boundary."
        ),
        Demonstration.COORDINATOR: (
            "A native graph delegates, processes text length and validates the return."
        ),
        Demonstration.SEQUENTIAL: (
            "Researcher, analyst and critic pass validated context in order."
        ),
        Demonstration.PARALLEL: (
            "Two native graph branches join before validated synthesis; "
            "concurrency is capped at two."
        ),
        Demonstration.HIERARCHICAL: (
            "Supervisor, lead and specialist follow fixed delegation and "
            "return ownership."
        ),
        Demonstration.CREWAI: (
            "Real CrewAI tasks exchange context across researcher, analyst and "
            "critic roles."
        ),
        Demonstration.ADK: (
            "Real ADK roles delegate and validate within one execution process."
        ),
        Demonstration.DISTRIBUTED: (
            "Two independent ADK worker processes count disjoint fragments, "
            "meet a barrier and are reaped before return."
        ),
    }[Demonstration(mode)]


class ConsoleRequest(Contract):
    mode: Demonstration
    instruction: Annotated[str, Field(strict=True, min_length=1, max_length=4096)] = (
        Field(repr=False)
    )
    max_steps: Annotated[int, Field(strict=True, ge=1, le=32)] = 8
    timeout_ms: Annotated[int, Field(strict=True, ge=1, le=30000)] = 30000

    @model_validator(mode="after")
    def nonblank(self):
        if not self.instruction.strip():
            raise ValueError("Synthetic task text is required.")
        return self


class ConsoleRun(Contract):
    """Temporary payload-free view, not a telemetry database or authority source."""

    workflow_id: UUID
    task_id: UUID
    mode: Demonstration
    outcome: Outcome
    finished_ns: Annotated[int, Field(strict=True, ge=1)]
    output: (
        Annotated[
            str,
            Field(
                strict=True,
                max_length=256,
                pattern=(
                    r"^(Fixture task completed; no model or external calls were made\."
                    r"|(?:Deterministic worker processed|Sequential synthesis accepted"
                    r"|Parallel synthesis accepted|Supervisor synthesis accepted"
                    r"|Collaborative review accepted|ADK validation accepted"
                    r"|Distributed synthesis accepted) [0-9]{1,4} characters\.)$"
                ),
            ),
        ]
        | None
    ) = None
    evidence: ExecutionEvidence | DistributedEvidence | None = None
    trace: RunTrace | None = None
    observation: Literal["local", "degraded", "unavailable"]

    @model_validator(mode="after")
    def correlated(self):
        runtime, topology, distributed = selection(self.mode)
        if self.outcome == Outcome.COMPLETED:
            if self.evidence is None or self.output is None:
                raise ValueError("Completion requires validated result evidence.")
            evidence = self.evidence
            if (
                isinstance(evidence, DistributedEvidence) != distributed
                or evidence.workflow_id != self.workflow_id
                or evidence.task_id != self.task_id
                or (evidence.runtime if distributed else evidence.actual_runtime)
                != runtime
                or (not distributed and evidence.topology != topology)
            ):
                raise ValueError("Console evidence correlation is invalid.")
        elif self.evidence is not None or self.output is not None:
            raise ValueError("Failure cannot carry success output/evidence.")
        if self.trace is not None and (
            self.trace.workflow_id != self.workflow_id
            or self.trace.task_id != self.task_id
            or self.trace.runtime != runtime
            or self.trace.topology != topology
            or self.trace.distributed != distributed
            or self.trace.outcome != self.outcome
        ):
            raise ValueError("Console trace correlation is invalid.")
        return self


def fresh(model, schema):
    """Closed recursive revalidation without rejected-value serialization warnings."""

    def data(value, depth=0):
        if depth > 8:
            raise ValueError("View nesting exceeds the bounded contract.")
        if isinstance(value, Contract):
            if set(value.__dict__) != set(type(value).model_fields):
                raise ValueError("Unowned contract fields.")
            return {key: data(item, depth + 1) for key, item in value.__dict__.items()}
        if isinstance(value, tuple):
            if len(value) > 32:
                raise ValueError("Contract collection exceeds the hard bound.")
            return tuple(data(item, depth + 1) for item in value)
        return value

    return schema.model_validate(data(model))


def failure_message(outcome: Outcome) -> str:
    return {
        Outcome.DENIED: (
            "Request or execution evidence was denied. Check the selected "
            "demonstration and step budget; no fallback ran."
        ),
        Outcome.TIMED_OUT: (
            "The deadline expired. Try the 30,000 ms default; distributed "
            "children are cleaned up before return."
        ),
        Outcome.CANCELLED: "Execution was cancelled. No success evidence is reported.",
        Outcome.FAILED: (
            "Execution failed. Check the synchronized local environment, then "
            "retry manually. No automatic fallback or retry ran."
        ),
        Outcome.COMPLETED: "Application validation completed successfully.",
    }[Outcome(outcome)]


class ConsoleRequestError(ValueError):
    """Submitted controls failed application validation; nothing executed."""


class ConsoleBusyError(ValueError):
    """The session already has an active run; nothing executed or cleared."""


class ConsoleFaultError(RuntimeError):
    """An admitted run ended without a recordable view; no cause is retained."""


class ConsoleSession:
    """Per-session synchronous application facade; eight curated views, no cache.

    Execution uses accepted services only. No keys, requests, SDK objects, raw
    telemetry buffers or exception causes are retained across runs. One run per
    session; SDK providers are created locally and closed before returning.
    """

    def __init__(self):
        self._runs = deque(maxlen=8)
        self._lock = threading.Lock()

    @property
    def runs(self) -> tuple[ConsoleRun, ...]:
        try:
            return tuple(fresh(run, ConsoleRun) for run in self._runs)
        except (ValueError, TypeError):
            self._runs.clear()
            return ()

    def clear(self):
        if not self._lock.acquire(blocking=False):
            raise ConsoleBusyError("A run is already active in this session.")
        try:
            self._runs.clear()
        finally:
            self._lock.release()

    def run(self, raw: object) -> ConsoleRun:
        try:
            checked = fresh(raw, ConsoleRequest)
        except (ValueError, TypeError) as exc:
            raise ConsoleRequestError(
                "Choose a demonstration and valid bounded synthetic text."
            ) from exc
        if not self._lock.acquire(blocking=False):
            raise ConsoleBusyError("A run is already active in this session.")
        try:
            return self._execute(checked)
        except Exception:
            # Not a caller input error; never surface it as one or keep its cause.
            raise ConsoleFaultError(
                "The run ended without a recordable result."
            ) from None
        finally:
            self._lock.release()

    def _execute(self, command: ConsoleRequest):
        runtime, topology, distributed = selection(command.mode)
        request = WorkflowRequest(
            runtime=runtime,
            topology=topology,
            task=TaskInput(instruction=command.instruction),
            limits=ExecutionLimits(
                max_steps=command.max_steps, timeout_ms=command.timeout_ms
            ),
        )
        observer, otel = Observability(), None
        observation = "local"
        try:
            otel = LocalOpenTelemetry()
            observer = Observability(adapters=(otel, LocalLangSmith()))
        except (Exception, asyncio.CancelledError):
            observation = "unavailable"
        outcome, output, evidence = Outcome.COMPLETED, None, None
        try:
            result = asyncio.run(
                execute_observed_workflow(
                    request, observer=observer, distributed=distributed
                )
            )
            result = fresh(
                result, DistributedResult if distributed else ValidatedWorkflowResult
            )
            evidence = result.evidence
            if evidence.limits != request.limits:
                raise InvalidRuntimeOutputError(
                    "Console result budget correlation failed."
                )
            output = result.output if distributed else result.result.output
        except ExecutionTimeoutError:
            outcome = Outcome.TIMED_OUT
        except (
            InvalidWorkflowRequestError,
            InvalidRuntimeOutputError,
            StepBudgetExceededError,
        ):
            outcome = Outcome.DENIED
        except asyncio.CancelledError:
            outcome = Outcome.CANCELLED
        except RuntimeUnavailableError:
            outcome = Outcome.FAILED
        except Exception:
            outcome = Outcome.FAILED
        finally:
            if otel is not None:
                try:
                    if otel.collect_metrics() is None and observation == "local":
                        observation = "degraded"
                except (Exception, asyncio.CancelledError):
                    observation = "degraded"
                try:
                    otel.close()
                except (Exception, asyncio.CancelledError):
                    observation = "degraded"
        if outcome != Outcome.COMPLETED:
            output = evidence = None
        trace = None
        try:
            candidate = checked_trace(observer.records[-1])
            if (
                candidate.workflow_id != request.workflow_id
                or candidate.task_id != request.task.task_id
                or candidate.outcome != outcome
                or candidate.runtime != runtime
                or candidate.topology != topology
                or candidate.distributed != distributed
            ):
                raise ValueError("Uncorrelated observation.")
            trace = candidate
            if observer.metrics.adapter_failures or observer.metrics.observation_drops:
                observation = "degraded"
        except (Exception, asyncio.CancelledError):
            observation = "unavailable"
        try:
            view = ConsoleRun(
                workflow_id=request.workflow_id,
                task_id=request.task.task_id,
                mode=command.mode,
                outcome=outcome,
                finished_ns=time.time_ns(),
                output=output,
                evidence=evidence,
                trace=trace,
                observation=observation,
            )
        except ValueError:
            view = ConsoleRun(
                workflow_id=request.workflow_id,
                task_id=request.task.task_id,
                mode=command.mode,
                outcome=Outcome.DENIED,
                finished_ns=time.time_ns(),
                observation="unavailable",
            )
        self._runs.append(view)
        return view


def age_seconds(run: ConsoleRun) -> int:
    return max(0, int((time.time_ns() - run.finished_ns) / 1_000_000_000))
