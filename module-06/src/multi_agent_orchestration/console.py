"""Bounded application service and curated views for the operations console."""

import asyncio
import threading
import time
from collections import deque
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from .benchmark import BenchmarkPlan, BenchmarkReport, run_benchmark
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

if TYPE_CHECKING:  # Additive live definitions load only after run admission.
    from .cockpit_langsmith import StoredLangSmithObservation
    from .cockpit_ops import StoredOperationsObservation
    from .console_live import LiveRun


def failure_text(category) -> str:
    """Fixed sanitized failed-live wording; loaded only on this additive path."""
    from .live_errors import failure_text as fixed

    return fixed(category)


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


class ScalingProfile(StrEnum):
    """Closed reviewer choices; the accepted benchmark still enforces its bounds."""

    QUICK = "Quick check: 2 workflows at caps 1 and 2"
    APPROVED = "Approved plan: 8 workflows at caps 1, 2 and 4"


def scaling_plan(profile: ScalingProfile) -> BenchmarkPlan:
    """Application-owned mapping; no caller number ever reaches the benchmark."""
    if ScalingProfile(profile) == ScalingProfile.QUICK:
        return BenchmarkPlan(mode="local-distributed-scaling", caps=(1, 2), workflows=2)
    return BenchmarkPlan(mode="local-distributed-scaling")


def scaling_guidance() -> tuple[tuple[str, str], ...]:
    """Static reviewer guidance; no caller or measured content is interpolated."""
    return (
        (
            "Purpose",
            "Shows how completed work changes when more identical local "
            "two-process workflows are admitted at once.",
        ),
        (
            "Action",
            "Choose a profile and select Run scaling benchmark. The quick check "
            "takes roughly 20 seconds; the approved plan takes a minute or two.",
        ),
        (
            "Expected result",
            "Every workflow completes at every cap, the observed peak equals the "
            "cap, and the invariants are reported as held. Timings differ on "
            "every run.",
        ),
        (
            "What it proves",
            "Deterministic, local, single-host, bounded-concurrency evidence: the "
            "cap was respected, every result was revalidated and every worker "
            "process was reaped. Agents are deterministic; no model or LLM "
            "inference runs.",
        ),
        (
            "What it does not prove",
            "Production capacity or service levels, cloud, horizontal or "
            "remote-cluster scaling, or a speedup that carries over to another "
            "machine. Speedup is a machine-specific measurement, not a pass "
            "criterion.",
        ),
    )


class ScalingRequest(Contract):
    profile: ScalingProfile


class ScalingRun(Contract):
    """Temporary curated view of one validated benchmark report; not a store."""

    profile: ScalingProfile
    finished_ns: Annotated[int, Field(strict=True, ge=1)]
    report: BenchmarkReport

    @model_validator(mode="after")
    def correlated(self):
        if self.report.plan != scaling_plan(self.profile):
            raise ValueError("Scaling report contradicts the selected profile.")
        return self


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
    """Per-session synchronous application facade; curated views, no cache.

    Execution uses accepted services only. No keys, requests, SDK objects, raw
    telemetry buffers or exception causes are retained across runs. One run per
    session; SDK providers are created locally and closed before returning.
    The scaling view holds the latest report of the accepted benchmark, which
    owns all measurement and bounds. The live demonstration runs the accepted
    canonical workflow with the module-level synthetic gateway only: no real
    provider connection, credential or delivery is attempted.
    """

    def __init__(self):
        self._runs = deque(maxlen=8)
        self._scaling = None
        self._live = deque(maxlen=8)
        self._operations = None
        self._langsmith = None
        self._lock = threading.Lock()

    @property
    def operations(self) -> "StoredOperationsObservation | None":
        """The last explicit current-host operational check, if any.

        Returns:
            A revalidated presentation-scoped result, or ``None`` when the
            reviewer never requested a check; ``None`` is the honest
            not-activated state, never a fabricated success.

        Raises:
            ConsoleFaultError: The retained view was not revalidatable; the
                stale value is cleared and the error carries no diagnostics.
        """
        from .cockpit_ops import StoredOperationsObservation

        if self._operations is None:
            return None
        try:
            return fresh(self._operations, StoredOperationsObservation)
        except (ValueError, TypeError) as exc:
            self._operations = None
            raise ConsoleFaultError(
                "The stored operational observation was not revalidatable and "
                "was cleared; request a new check."
            ) from exc

    @property
    def runs(self) -> tuple[ConsoleRun, ...]:
        try:
            return tuple(fresh(run, ConsoleRun) for run in self._runs)
        except (ValueError, TypeError):
            self._runs.clear()
            return ()

    @property
    def live_runs(self) -> "tuple[LiveRun, ...]":
        if not self._live:
            return ()
        # The additive live boundary loads only when retained views exist.
        from .console_live import runs

        return runs(self._live)

    def clear(self):
        if not self._lock.acquire(blocking=False):
            raise ConsoleBusyError("A run is already active in this session.")
        try:
            self._runs.clear()
            self._scaling = None
            self._live.clear()
            self._operations = None
        finally:
            self._lock.release()

    def check_operations(self) -> "StoredOperationsObservation":
        """Run one explicit bounded read-only local operational check.

        The querying logic is the accepted ``cockpit_ops`` boundary: fixed
        loopback endpoints of the current running host, single attempt,
        bounded timeouts, untrusted responses validated before any value is
        shown, no retries or background refresh, no credentials. The result
        is presentation state only; it never authorizes anything and is
        never merged with, or substituted by, the recorded historical
        operational evidence.

        Returns:
            The validated fresh observation with its acquisition time; the
            ``unavailable`` state is a truthful outcome, not a failure.

        Raises:
            ConsoleFaultError: Unexpected read-only boundary failure; no
                cause and no diagnostics are retained.
        """
        from .cockpit_ops import LocalStackObservation, StoredOperationsObservation
        from .cockpit_ops import query_local_stack as perform

        try:
            observation = fresh(perform(), LocalStackObservation)
            view = StoredOperationsObservation(
                happened_ns=time.time_ns(), observation=observation
            )
            fresh(view, StoredOperationsObservation)
        except (Exception, asyncio.CancelledError) as exc:
            raise ConsoleFaultError(
                "The operational check could not produce a validated "
                "observation. The deterministic demonstrations remain "
                "available; no historical value is substituted."
            ) from exc
        self._operations = view
        return view

    @property
    def langsmith_read(self) -> "StoredLangSmithObservation | None":
        """The last explicit current LangSmith inspection, if any.

        Returns:
            A revalidated presentation-scoped result, or ``None`` when the
            reviewer never requested one; ``None`` is the honest
            not-activated state.

        Raises:
            ConsoleFaultError: The retained view was not revalidatable; the
                stale value is cleared and the error carries no diagnostics.
        """
        from .cockpit_langsmith import StoredLangSmithObservation as stored_cls

        if self._langsmith is None:
            return None
        try:
            return fresh(self._langsmith, stored_cls)
        except (ValueError, TypeError) as exc:
            self._langsmith = None
            raise ConsoleFaultError(
                "The retained LangSmith inspection was not revalidatable and "
                "was cleared; request a new check."
            ) from exc

    def inspect_langsmith(
        self,
        provider: "object | None" = None,
        trace_id: "object | None" = None,
    ) -> "StoredLangSmithObservation":
        """Run one explicit, bounded, read-only LangSmith inspection.

        The inspecting logic is the accepted ``cockpit_langsmith`` boundary:
        read-only, allowlisted recorded traces only, no credential lookup, no
        network performed by the boundary itself, and no fabricated fact
        when a trusted read capability is absent. The supplied provider is
        a trusted runtime capability, never a visitor artifact; credential
        presence is never asked about and never authorizes anything.

        Args:
            provider: A trusted read capability, or ``None`` (the honest
                result is then an unavailable observation).
            trace_id: Reserved for a single allowlisted target in a later
                story; ``None`` inspects the call's default recorded trace.

        Returns:
            The validated current observation with its acquisition time.

        Raises:
            ConsoleFaultError: Unexpected inspection-boundary failure; no
                cause and no diagnostics are retained.
        """
        from .cockpit_langsmith import (
            LangSmithObservation,
            StoredLangSmithObservation,
            allowlisted_targets,
        )
        from .cockpit_langsmith import inspect_recorded_trace as perform

        allowed = tuple(item[0] for item in allowlisted_targets())
        target = None
        if trace_id is None:
            target = allowed[0]
        elif type(trace_id) is str and trace_id in allowed:
            target = trace_id
        try:
            observation = fresh(
                perform(target, provider), LangSmithObservation
            )
            view = StoredLangSmithObservation(
                happened_ns=time.time_ns(), observation=observation
            )
            fresh(view, StoredLangSmithObservation)
        except (Exception, asyncio.CancelledError) as exc:
            raise ConsoleFaultError(
                "The LangSmith inspection could not produce a validated "
                "observation. The deterministic demonstrations remain "
                "available; no historical value is substituted."
            ) from exc
        self._langsmith = view
        return view

    @property
    def scaling(self) -> ScalingRun | None:
        if self._scaling is None:
            return None
        try:
            return fresh(self._scaling, ScalingRun)
        except (ValueError, TypeError):
            self._scaling = None
            return None

    def run_scaling(self, raw: object) -> ScalingRun:
        """Run the accepted benchmark for a closed profile and keep its report.

        Raises:
            ConsoleRequestError: The profile is not one of the closed choices.
            ConsoleBusyError: This session already has an active execution.
            ConsoleFaultError: No validated report was produced; the earlier
                view, if any, is kept and no cause is retained.
        """
        try:
            checked = fresh(raw, ScalingRequest)
            plan = scaling_plan(checked.profile)
        except (ValueError, TypeError) as exc:
            raise ConsoleRequestError(
                "Choose one of the bounded scaling profiles."
            ) from exc
        if not self._lock.acquire(blocking=False):
            raise ConsoleBusyError("A run is already active in this session.")
        try:
            # The report is untrusted until revalidated and matched to the plan.
            report = fresh(asyncio.run(run_benchmark(plan)), BenchmarkReport)
            view = ScalingRun(
                profile=checked.profile, finished_ns=time.time_ns(), report=report
            )
        except (Exception, asyncio.CancelledError):
            raise ConsoleFaultError(
                "The benchmark ended without a recordable result."
            ) from None
        finally:
            self._lock.release()
        self._scaling = view
        return view

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

    def run_live(self, raw: object) -> "LiveRun":
        """Run the canonical live workflow with the synthetic gateway.

        The authorization, selection and budget are application-owned and
        fixed; the gateway factory is the module-level synthetic demonstration
        factory, so no real provider connection is attempted. The accepted
        service classifies receipts as synthetic offline itself.

        Raises:
            ConsoleRequestError: The submitted text was refused; nothing executed.
            ConsoleBusyError: This session already has an active execution.
            ConsoleFaultError: No recordable view was produced; the earlier
                views are kept and no cause is retained.
        """
        # The additive live boundary and its contracts load only after this
        # admission; deterministic console startup stays free of them.
        from .console_live import execute, validate

        try:
            checked = validate(raw)
        except (ValueError, TypeError) as exc:
            raise ConsoleRequestError(
                "Submit nonblank synthetic text of at most 4096 characters."
            ) from exc
        if not self._lock.acquire(blocking=False):
            raise ConsoleBusyError("A run is already active in this session.")
        try:
            return execute(self, checked)
        except ConsoleRequestError:
            raise
        except (Exception, asyncio.CancelledError):
            # Not a caller input error; never surface it as one or keep its cause.
            raise ConsoleFaultError(
                "The live demonstration ended without a recordable result."
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


def age_seconds(run: "ConsoleRun | ScalingRun | LiveRun") -> int:
    return max(0, int((time.time_ns() - run.finished_ns) / 1_000_000_000))
