"""Opt-in bounded local scaling benchmark over the accepted distributed service.

Nothing here runs on import. Trusted operator code builds a ``BenchmarkPlan`` and
calls ``run_benchmark``; workflow requests, runtime output, credentials and
environment variables cannot select caps, counts or deadlines. Admission control
is scoped to one benchmark level. It is not a platform worker pool, queue or
global limiter. Timings are observations on one host, never acceptance criteria
and never evidence of hosted, multi-host or production capacity.
"""

import asyncio
import math
import os
import statistics
import sys
import time
from collections.abc import Callable
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .contracts import Contract, ExecutionLimits, RuntimeId, TaskInput, WorkflowRequest
from .distributed_contracts import DistributedResult
from .errors import (
    ExecutionTimeoutError,
    InvalidRuntimeOutputError,
    InvalidWorkflowRequestError,
    RuntimeFoundationError,
    StepBudgetExceededError,
)
from .observability import Observability, ObservationAdapter
from .observability_contracts import Count, Outcome
from .observed_execution import execute_observed_workflow

CAPS = (1, 2, 4)
INSTRUCTION = "Deterministic local scaling benchmark workload."
EXPECTED_OUTPUT = f"Distributed synthesis accepted {len(INSTRUCTION)} characters."
MARGIN_MS = 30_000

Seconds = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
Ratio = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]


class BenchmarkError(RuntimeFoundationError):
    """Benchmark selection failed validation; nothing was executed."""


class BenchmarkPlan(Contract):
    """Operator-owned bounded workload; never part of workflow or runtime data.

    Attributes:
        mode: Required explicit selection. There is no default.
        caps: Admission caps in strictly ascending order, each one of 1, 2 or 4.
        workflows: Identical workflows submitted at every cap.
        repeats: Complete passes over the caps; each is reported separately.
        timeout_ms: Deadline of each workflow, enforced by the accepted service.
        warmup: Run and discard one workflow before the measured levels.
    """

    mode: Literal["local-distributed-scaling"]
    caps: Annotated[
        tuple[Annotated[int, Field(strict=True)], ...],
        Field(min_length=1, max_length=3),
    ] = CAPS
    workflows: Annotated[int, Field(strict=True, ge=2, le=16)] = 8
    repeats: Annotated[int, Field(strict=True, ge=1, le=3)] = 1
    timeout_ms: Annotated[int, Field(strict=True, ge=1, le=30_000)] = 30_000
    warmup: Annotated[bool, Field(strict=True)] = True

    @model_validator(mode="after")
    def bounded_caps(self) -> "BenchmarkPlan":
        """Reject caps outside the approved set or not strictly increasing."""
        if any(cap not in CAPS for cap in self.caps) or any(
            low >= high for low, high in zip(self.caps, self.caps[1:], strict=False)
        ):
            raise ValueError("Caps must be ascending values from 1, 2 and 4.")
        return self


class HostFacts(Contract):
    """Coarse description of the measuring host; no host or user identity."""

    system: Annotated[str, Field(strict=True, min_length=1, max_length=32)]
    python: Annotated[str, Field(strict=True, pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")]
    logical_cpus: Annotated[int, Field(strict=True, ge=1, le=4096)] | None


class LevelResult(Contract):
    """Observed behaviour of one batch at one cap. ``None`` means not derived.

    ``peak_in_flight`` counts workflows the benchmark admitted, not live
    operating-system processes. ``workers_reaped`` is two per validated
    completion, because the accepted service returns only after reaping both
    workers. Derived timing values exist only for a level that passed.
    """

    repeat: Annotated[int, Field(strict=True, ge=1, le=3)]
    cap: Annotated[int, Field(strict=True, ge=1, le=4)]
    requested: Annotated[int, Field(strict=True, ge=2, le=16)]
    completed: Count
    failed: Count
    timed_out: Count
    denied: Count
    cancelled: Count
    deadline_ms: Annotated[int, Field(strict=True, ge=1)]
    deadline_exceeded: Annotated[bool, Field(strict=True)]
    wall_seconds: Seconds
    peak_in_flight: Annotated[int, Field(strict=True, ge=0, le=4)]
    integrity: Annotated[bool, Field(strict=True)]
    workers_reaped: Count
    observed_started: Count
    observed_completed: Count
    observation_drops: Count
    observation_adapter_failures: Count
    passed: Annotated[bool, Field(strict=True)]
    throughput_per_second: Ratio | None = None
    duration_min_seconds: Seconds | None = None
    duration_median_seconds: Seconds | None = None
    duration_max_seconds: Seconds | None = None
    overlap_factor: Ratio | None = None
    speedup_vs_cap_1: Ratio | None = None

    @model_validator(mode="after")
    def consistency(self) -> "LevelResult":
        """Reject counts, timings or ratios inconsistent with the level."""
        finished = (
            self.completed + self.failed + self.timed_out + self.denied + self.cancelled
        )
        derived = (
            self.throughput_per_second,
            self.duration_min_seconds,
            self.duration_median_seconds,
            self.duration_max_seconds,
            self.overlap_factor,
            self.speedup_vs_cap_1,
        )
        if (
            finished != self.requested
            or self.peak_in_flight > self.cap
            or self.workers_reaped != 2 * self.completed
        ):
            raise ValueError("Level counts contradict the bounded workload.")
        if self.passed and (
            self.completed != self.requested
            or self.deadline_exceeded
            or not self.integrity
            or self.observed_started != self.requested
            or self.observed_completed != self.requested
            or self.observation_drops
            or self.duration_max_seconds is None
            or self.duration_max_seconds > self.wall_seconds
        ):
            raise ValueError("A passed level must satisfy every invariant.")
        if not self.passed and any(value is not None for value in derived):
            raise ValueError("A failed level cannot carry derived measurements.")
        return self


class BenchmarkReport(Contract):
    """Payload-free local evidence: no instructions, identifiers or PIDs."""

    classification: Literal["local_single_host"] = "local_single_host"
    evidence_class: Literal["deterministic_local_multi_process"] = (
        "deterministic_local_multi_process"
    )
    workload: Literal["distributed_two_process_character_count"] = (
        "distributed_two_process_character_count"
    )
    host: HostFacts
    plan: BenchmarkPlan
    warmup_completed: Annotated[bool, Field(strict=True)] | None
    levels: Annotated[tuple[LevelResult, ...], Field(max_length=9)]
    model_calls: Literal[0] | None
    provider_calls: Literal[0] | None
    external_calls: Literal[0] | None
    retries: Literal[0] | None
    passed: Annotated[bool, Field(strict=True)]

    @model_validator(mode="after")
    def consistency(self) -> "BenchmarkReport":
        """Reject a report whose levels or verdict contradict its plan."""
        expected = tuple(
            (repeat, cap)
            for repeat in range(1, self.plan.repeats + 1)
            for cap in self.plan.caps
        )
        ran = tuple((level.repeat, level.cap) for level in self.levels)
        complete = (
            self.warmup_completed is not False
            and ran == expected
            and all(level.passed for level in self.levels)
        )
        accounting = (
            self.model_calls,
            self.provider_calls,
            self.external_calls,
            self.retries,
        )
        if (
            ran != expected[: len(ran)]
            or (self.warmup_completed is None) == self.plan.warmup
            or any(level.requested != self.plan.workflows for level in self.levels)
            or self.passed != complete
            or accounting != ((0, 0, 0, 0) if complete else (None,) * 4)
        ):
            raise ValueError("Report contradicts its plan or level evidence.")
        return self


def level_deadline_ms(plan: BenchmarkPlan, cap: int) -> int:
    """Worst case implied by the plan: full waves of deadline-bound workflows."""
    return math.ceil(plan.workflows / cap) * plan.timeout_ms + MARGIN_MS


def _checked(plan: object) -> BenchmarkPlan:
    if type(plan) is not BenchmarkPlan or set(plan.__dict__) != set(
        BenchmarkPlan.model_fields
    ):
        raise BenchmarkError("Benchmark requires an operator plan.")
    try:
        return BenchmarkPlan.model_validate(dict(plan.__dict__))
    except ValueError as exc:
        raise BenchmarkError("Benchmark plan is invalid.") from exc


def _request(plan: BenchmarkPlan) -> WorkflowRequest:
    """Identical work with fresh identities, so no state is shared between runs."""
    return WorkflowRequest(
        runtime=RuntimeId.GOOGLE_ADK,
        task=TaskInput(instruction=INSTRUCTION),
        limits=ExecutionLimits(max_steps=4, timeout_ms=plan.timeout_ms),
    )


def _intact(raw: object, request: WorkflowRequest) -> bool:
    """Service output stays untrusted until it matches the benchmark's own request."""
    if not isinstance(raw, DistributedResult):
        return False
    try:
        checked = DistributedResult.model_validate(raw.model_dump(warnings="error"))
        checked = DistributedResult.model_validate(checked.model_dump())
    except (ValueError, TypeError):
        return False
    return (
        checked.workflow_id == request.workflow_id
        and checked.task_id == request.task.task_id
        and checked.characters == len(INSTRUCTION)
        and checked.output == EXPECTED_OUTPUT
        and checked.evidence.limits == request.limits
        and checked.evidence.coordinator_pid == os.getpid()
    )


async def _workflow(plan: BenchmarkPlan, observer: Observability, clock):
    """One workflow as (outcome, seconds, mismatch); cancellation propagates."""
    request = _request(plan)
    mismatch = False
    started = clock()
    try:
        raw = await execute_observed_workflow(
            request, observer=observer, distributed=True
        )
        mismatch = not _intact(raw, request)
        outcome = Outcome.FAILED if mismatch else Outcome.COMPLETED
    except ExecutionTimeoutError:
        outcome = Outcome.TIMED_OUT
    except (
        InvalidWorkflowRequestError,
        InvalidRuntimeOutputError,
        StepBudgetExceededError,
    ):
        outcome = Outcome.DENIED
    except Exception:
        outcome = Outcome.FAILED  # Counted; one failure cannot abort its siblings.
    return outcome, clock() - started, mismatch


async def _bounded(tasks: list, deadline_ms: int) -> bool:
    """Await tasks under a deadline, then cancel and settle every one of them.

    Returns whether the deadline expired. The wait is shielded throughout, so
    each workflow receives exactly one cancellation request however often the
    caller cancels, and the accepted service can finish killing and reaping its
    workers before this returns or re-raises the caller's cancellation.
    """
    settled = asyncio.gather(*tasks, return_exceptions=True)
    exceeded = interrupted = False
    try:
        async with asyncio.timeout(deadline_ms / 1000):
            await asyncio.shield(settled)
    except TimeoutError:
        exceeded = True
    except asyncio.CancelledError:
        interrupted = True
    for task in tasks:
        if not task.done():
            task.cancel()
    while not settled.done():
        try:
            await asyncio.shield(settled)
        except asyncio.CancelledError:
            interrupted = True
    if interrupted:
        raise asyncio.CancelledError
    return exceeded


async def _warm_up(plan: BenchmarkPlan) -> bool:
    """Run and discard one workflow so first-use effects stay out of level one."""
    task = asyncio.create_task(_workflow(plan, Observability(), time.perf_counter))
    exceeded = await _bounded([task], plan.timeout_ms + MARGIN_MS)
    return (
        not exceeded and not task.cancelled() and task.result()[0] == Outcome.COMPLETED
    )


async def _level(
    plan: BenchmarkPlan,
    cap: int,
    repeat: int,
    baseline: float | None,
    adapters: tuple[ObservationAdapter, ...],
    clock: Callable[[], float],
) -> LevelResult:
    gate = asyncio.Semaphore(cap)
    observer = Observability(adapters=adapters)
    in_flight = peak = 0

    async def admitted():
        nonlocal in_flight, peak
        async with gate:
            in_flight += 1
            peak = max(peak, in_flight)
            try:
                return await _workflow(plan, observer, clock)
            finally:
                in_flight -= 1

    deadline_ms = level_deadline_ms(plan, cap)
    tasks = [asyncio.create_task(admitted()) for _ in range(plan.workflows)]
    started = clock()
    exceeded = await _bounded(tasks, deadline_ms)
    wall = clock() - started

    finished = [task.result() for task in tasks if not task.cancelled()]
    counts = dict.fromkeys(Outcome, 0)
    counts[Outcome.CANCELLED] = len(tasks) - len(finished)
    for outcome, _, _ in finished:
        counts[outcome] += 1
    durations = sorted(
        seconds for outcome, seconds, _ in finished if outcome == Outcome.COMPLETED
    )
    integrity = not any(mismatch for _, _, mismatch in finished)
    completed = counts[Outcome.COMPLETED]
    metrics = observer.metrics
    passed = (
        completed == plan.workflows
        and not exceeded
        and integrity
        and in_flight == 0
        and peak <= cap
        and metrics.started == metrics.completed == plan.workflows
        and metrics.observation_drops == 0
        # Exact on any machine: every duration lies inside the level's window
        # and at most ``cap`` of them overlap. The epsilon covers float summing.
        and durations[-1] <= wall
        and sum(durations) <= cap * wall * (1 + 1e-9) + 1e-9
    )
    measurable = passed and wall > 0
    reference = wall if cap == 1 else baseline
    return LevelResult(
        repeat=repeat,
        cap=cap,
        requested=plan.workflows,
        completed=completed,
        failed=counts[Outcome.FAILED],
        timed_out=counts[Outcome.TIMED_OUT],
        denied=counts[Outcome.DENIED],
        cancelled=counts[Outcome.CANCELLED],
        deadline_ms=deadline_ms,
        deadline_exceeded=exceeded,
        wall_seconds=max(0.0, wall),
        peak_in_flight=peak,
        integrity=integrity,
        workers_reaped=2 * completed,
        observed_started=metrics.started,
        observed_completed=metrics.completed,
        observation_drops=metrics.observation_drops,
        observation_adapter_failures=metrics.adapter_failures,
        passed=passed,
        throughput_per_second=completed / wall if measurable else None,
        duration_min_seconds=durations[0] if passed else None,
        duration_median_seconds=statistics.median(durations) if passed else None,
        duration_max_seconds=durations[-1] if passed else None,
        overlap_factor=(sum(durations) / wall) or None if measurable else None,
        speedup_vs_cap_1=reference / wall if measurable and reference else None,
    )


async def run_benchmark(
    plan: BenchmarkPlan,
    *,
    adapters: tuple[ObservationAdapter, ...] = (),
    clock: Callable[[], float] = time.perf_counter,
) -> BenchmarkReport:
    """Run the planned batches at each cap and report only what was observed.

    Every workflow goes through the accepted observed distributed service with a
    fresh request. Each level has its own admission gate and observer. The run
    stops at the first level that breaks an invariant, and no throughput or
    speedup is derived from such a level. Speedup is descriptive only.

    Args:
        plan: An owned ``BenchmarkPlan`` built by trusted operator code.
        adapters: Trusted local observation adapters; their failures are counted
            and never change benchmark results.
        clock: Trusted monotonic clock in seconds.

    Returns:
        A payload-free report classified as local single-host evidence.

    Raises:
        BenchmarkError: The plan is forged or invalid; nothing was executed.
    """
    plan = _checked(plan)
    warmed = await _warm_up(plan) if plan.warmup else None
    levels: list[LevelResult] = []
    stopped = warmed is False
    for repeat in range(1, plan.repeats + 1):
        baseline = None
        for cap in plan.caps:
            if stopped:
                break
            level = await _level(plan, cap, repeat, baseline, adapters, clock)
            levels.append(level)
            stopped = not level.passed
            if cap == 1 and level.passed and level.wall_seconds > 0:
                baseline = level.wall_seconds
    passed = not stopped and len(levels) == plan.repeats * len(plan.caps)
    accounting = 0 if passed else None  # Validated evidence fixes these at zero.
    return BenchmarkReport(
        host=HostFacts(
            system=sys.platform,
            python=".".join(str(part) for part in sys.version_info[:3]),
            logical_cpus=os.cpu_count(),
        ),
        plan=plan,
        warmup_completed=warmed,
        levels=tuple(levels),
        model_calls=accounting,
        provider_calls=accounting,
        external_calls=accounting,
        retries=accounting,
        passed=passed,
    )
