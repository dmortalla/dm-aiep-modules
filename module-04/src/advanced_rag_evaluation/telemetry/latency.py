"""Per-stage latency measurement and budget evaluation (M4-OPT-02, M4-OBS-03).

Timing is always taken from an injected ``Clock``, never inferred from
timestamps embedded in retrieved or model content: a clock's ``now()`` is
the only source of elapsed-time evidence anywhere in this module. The
default production clock (``PerfCounterClock``) wraps
``time.perf_counter()``, a monotonic, high-resolution timer appropriate for
measuring elapsed wall time without being affected by system-clock
adjustments; normal, deterministic tests inject ``FakeClock`` instead, so no
test depends on real wall-clock timing or a ``sleep`` call.

Measuring a stage never converts a failed operation into a successful
timing result: ``measure_stage`` calls the supplied operation directly, with
no surrounding ``try``/``except``, so any exception the operation raises
propagates with its original type, message, and traceback unchanged, and no
``StageTiming`` is produced for that call. This module does not retain
failure-timing evidence; a caller that wants to time a failing stage must
measure around its own exception handling explicitly.

Latency-budget evaluation (M4-OPT-02) is explicit, bounded, application-
owned configuration compared against already-measured evidence; it never
infers, benchmarks, or claims production performance, and no retrieved or
model content can influence a configured budget.
"""

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ..errors import LatencyConfigurationError, LatencyError, LatencyPolicyError


class Clock(Protocol):
    """An injectable source of monotonic elapsed-time measurements."""

    def now(self) -> float:
        """Return a monotonic timestamp in seconds.

        Only the *difference* between two calls is meaningful; the absolute
        value carries no calendar/wall-clock meaning.
        """
        ...


class PerfCounterClock:
    """The default production clock: a thin wrapper over time.perf_counter."""

    def now(self) -> float:
        """Return the current monotonic high-resolution timestamp in seconds."""
        return time.perf_counter()


class FakeClock:
    """A deterministic clock for tests: returns each configured timestamp in order.

    Each call to ``now()`` returns the next value from a fixed, pre-supplied
    sequence; it never reads the real system or monotonic clock.
    """

    __slots__ = ("_timestamps", "_index")

    def __init__(self, timestamps: tuple[float, ...]) -> None:
        """Configure the exact, ordered sequence of timestamps to return.

        Args:
            timestamps: At least two finite numeric timestamps, in the
                order they will be returned; typically one pair (start,
                end) per stage to be measured.

        Raises:
            LatencyConfigurationError: For a malformed or too-short sequence.
        """
        if (
            type(timestamps) is not tuple
            or len(timestamps) < 2
            or any(
                type(value) not in (int, float)
                or type(value) is bool
                or not math.isfinite(value)
                for value in timestamps
            )
        ):
            raise LatencyConfigurationError(
                "Supply at least two finite numeric timestamps, in order."
            )
        self._timestamps = timestamps
        self._index = 0

    def now(self) -> float:
        """Return the next configured timestamp.

        Raises:
            LatencyConfigurationError: If every configured timestamp has
                already been returned.
        """
        if self._index >= len(self._timestamps):
            raise LatencyConfigurationError(
                "FakeClock exhausted; supply more timestamps than stages measured."
            )
        value = self._timestamps[self._index]
        self._index += 1
        return float(value)


@dataclass(frozen=True, slots=True)
class StageTiming:
    """One measured stage's elapsed duration, with explicit sequence evidence.

    Args:
        stage: Nonblank stage name.
        sequence: Zero-based position in measurement order.
        elapsed_seconds: Finite, nonnegative measured duration.

    Raises:
        LatencyError: For a blank stage name, malformed sequence, or
            negative/nonfinite duration (including one implied by a
            malformed clock returning a later start than end timestamp).
    """

    stage: str
    sequence: int
    elapsed_seconds: float

    def __post_init__(self) -> None:
        """Validate measured-stage shape without rendering any stage payload."""
        if type(self.stage) is not str or not self.stage.strip():
            raise LatencyError("Use a nonblank stage name.")
        if (
            type(self.sequence) is not int
            or type(self.sequence) is bool
            or self.sequence < 0
        ):
            raise LatencyError("Use a zero-based nonnegative integer sequence.")
        if (
            type(self.elapsed_seconds) not in (int, float)
            or type(self.elapsed_seconds) is bool
            or not math.isfinite(self.elapsed_seconds)
            or self.elapsed_seconds < 0
        ):
            raise LatencyError("Use a finite nonnegative elapsed_seconds duration.")


def measure_stage[T](
    stage: str, operation: Callable[[], T], clock: Clock, sequence: int
) -> tuple[T, StageTiming]:
    """Time one callable's execution using an injected clock.

    If ``operation`` raises, the exception propagates unchanged -- this
    function adds no exception handling around the call itself -- and no
    StageTiming is returned for that call.

    Args:
        stage: Nonblank stage name for the resulting StageTiming.
        operation: Zero-argument callable to time and run exactly once.
        clock: Injected Clock; production code supplies PerfCounterClock,
            tests supply FakeClock.
        sequence: Zero-based position of this stage in measurement order.

    Returns:
        A tuple of the operation's own return value and the StageTiming
        measured around it.

    Raises:
        LatencyConfigurationError: For a blank stage name or malformed
            sequence, checked before ``operation`` is ever called.
        Exception: Whatever ``operation`` itself raises, unmodified.
    """
    if type(stage) is not str or not stage.strip():
        raise LatencyConfigurationError("Supply a nonblank stage name.")
    if type(sequence) is not int or type(sequence) is bool or sequence < 0:
        raise LatencyConfigurationError(
            "Use a zero-based nonnegative integer sequence."
        )
    start = clock.now()
    result = operation()
    end = clock.now()
    timing = StageTiming(stage, sequence, end - start)
    return result, timing


@dataclass(frozen=True, slots=True)
class LatencyReport:
    """Validated, ordered, complete per-stage timing evidence for one run.

    Args:
        stages: Nonempty tuple of StageTiming, contiguous zero-based
            ``sequence`` from zero, unique ``stage`` names.

    Raises:
        LatencyError: For an empty/malformed tuple, a sequence gap, or a
            duplicate stage name.
    """

    stages: tuple[StageTiming, ...]

    def __post_init__(self) -> None:
        """Re-validate contiguous sequence order and unique stage names."""
        if (
            type(self.stages) is not tuple
            or not self.stages
            or any(type(s) is not StageTiming for s in self.stages)
        ):
            raise LatencyError("Supply a nonempty tuple of validated StageTiming.")
        for index, stage in enumerate(self.stages):
            if stage.sequence != index:
                raise LatencyError("Keep stage sequence contiguous from zero.")
        names = [stage.stage for stage in self.stages]
        if len(set(names)) != len(names):
            raise LatencyError("Deduplicate stage names within one LatencyReport.")

    @property
    def total_seconds(self) -> float:
        """Return the sum of every stage's measured elapsed_seconds."""
        return sum(stage.elapsed_seconds for stage in self.stages)


@dataclass(frozen=True, slots=True)
class LatencyBudget:
    """One application-owned per-stage latency budget.

    Args:
        stage: Nonblank stage name this budget applies to.
        max_seconds: Finite, nonnegative maximum allowed duration.

    Raises:
        LatencyConfigurationError: For invalid settings.
    """

    stage: str
    max_seconds: float

    def __post_init__(self) -> None:
        """Validate one budgeted stage's bound before any report is considered."""
        if type(self.stage) is not str or not self.stage.strip():
            raise LatencyConfigurationError("Use a nonblank budgeted stage name.")
        if (
            type(self.max_seconds) not in (int, float)
            or type(self.max_seconds) is bool
            or not math.isfinite(self.max_seconds)
            or self.max_seconds < 0
        ):
            raise LatencyConfigurationError("Use a finite nonnegative max_seconds.")


@dataclass(frozen=True, slots=True)
class LatencyBudgetConfig:
    """Application-owned, explicit set of per-stage latency budgets.

    Args:
        budgets: Nonempty tuple of LatencyBudget, unique stage names.

    Raises:
        LatencyConfigurationError: For an empty tuple or duplicate stage.
    """

    budgets: tuple[LatencyBudget, ...]

    def __post_init__(self) -> None:
        """Validate the budget set before any report is evaluated against it."""
        if (
            type(self.budgets) is not tuple
            or not self.budgets
            or any(type(b) is not LatencyBudget for b in self.budgets)
        ):
            raise LatencyConfigurationError(
                "Supply a nonempty tuple of validated LatencyBudget objects."
            )
        stages = [budget.stage for budget in self.budgets]
        if len(set(stages)) != len(stages):
            raise LatencyConfigurationError("Deduplicate budgeted stage names.")


@dataclass(frozen=True, slots=True)
class LatencyEvaluation:
    """One stage's inspectable budget-comparison outcome.

    Args:
        stage: The evaluated stage name.
        measured_seconds: The stage's measured elapsed_seconds from the report.
        budget_seconds: The configured max_seconds for this stage.
        within_budget: True when measured_seconds <= budget_seconds.
        rationale: Human-readable explanation naming the measured value,
            the budget, and the outcome -- never only a bare boolean.

    Raises:
        LatencyError: For malformed fields or an inconsistent within_budget flag.
    """

    stage: str
    measured_seconds: float
    budget_seconds: float
    within_budget: bool
    rationale: str

    def __post_init__(self) -> None:
        """Re-validate shape and that within_budget matches the compared values."""
        if type(self.stage) is not str or not self.stage.strip():
            raise LatencyError("Use a nonblank stage name.")
        if type(self.within_budget) is not bool:
            raise LatencyError("Use bool for within_budget.")
        if type(self.rationale) is not str or not self.rationale.strip():
            raise LatencyError("Supply a nonblank rationale string.")
        if self.within_budget != (self.measured_seconds <= self.budget_seconds):
            raise LatencyError(
                "within_budget must equal measured_seconds <= budget_seconds."
            )


def evaluate_latency_budget(
    report: LatencyReport, config: LatencyBudgetConfig
) -> tuple[LatencyEvaluation, ...]:
    """Compare each budgeted stage's measured duration against its budget.

    A stage present in ``report`` but not budgeted in ``config`` is simply
    not evaluated -- that is not an error, since a report may measure
    stages this particular policy does not care about. A stage budgeted in
    ``config`` but missing from ``report`` is an error: a budget cannot be
    evaluated against evidence that was never measured.

    Args:
        report: Validated LatencyReport to evaluate.
        config: Validated, explicit, application-owned LatencyBudgetConfig.

    Returns:
        One LatencyEvaluation per budgeted stage, in ``config.budgets`` order.

    Raises:
        LatencyConfigurationError: For wrong-typed report/config.
        LatencyPolicyError: If a budgeted stage has no corresponding
            measured StageTiming in the report.
    """
    if type(report) is not LatencyReport:
        raise LatencyConfigurationError("Supply a validated LatencyReport.")
    if type(config) is not LatencyBudgetConfig:
        raise LatencyConfigurationError("Supply a validated LatencyBudgetConfig.")

    by_stage = {timing.stage: timing for timing in report.stages}
    evaluations = []
    for budget in config.budgets:
        timing = by_stage.get(budget.stage)
        if timing is None:
            raise LatencyPolicyError(
                f"No measured timing for budgeted stage {budget.stage!r}."
            )
        within = timing.elapsed_seconds <= budget.max_seconds
        rationale = (
            f"Stage {budget.stage!r} measured {timing.elapsed_seconds:.6f}s "
            f"against a configured budget of {budget.max_seconds:.6f}s; "
            f"{'within' if within else 'over'} budget."
        )
        evaluations.append(
            LatencyEvaluation(
                budget.stage,
                timing.elapsed_seconds,
                budget.max_seconds,
                within,
                rationale,
            )
        )
    return tuple(evaluations)
