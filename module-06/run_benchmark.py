"""Operator command: bounded local scaling benchmark of the distributed service.

Nothing runs unless ``--run`` is given. Identical deterministic workflows are
admitted at caps 1, 2 and 4 and the observed behaviour is printed. No model,
provider, paid or network call is made, no credential is read and no file is
written. Timings describe this host only; speedup is not an acceptance criterion.
"""

import argparse
import asyncio


def bounded(low: int, high: int):
    def parse(text: str) -> int:
        value = int(text)
        if not low <= value <= high:
            raise argparse.ArgumentTypeError(f"value must be {low} to {high}")
        return value

    return parse


def shown(value: float | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def render(report) -> str:
    """Plain-text view of a validated report; unavailable values are not zero."""
    host = report.host
    cpus = "unknown" if host.logical_cpus is None else host.logical_cpus
    lines = [
        f"Deterministic local scaling benchmark ({report.classification})",
        f"Host: {host.system}, Python {host.python}, logical CPUs: {cpus}",
        f"Workload: {report.plan.workflows} identical two-process distributed "
        f"workflows per level; warm-up completed: {report.warmup_completed}",
        "repeat cap done/asked wall_s per_s min_s median_s max_s peak overlap "
        "speedup result",
    ]
    for level in report.levels:
        lines.append(
            f"{level.repeat:>6} {level.cap:>3} "
            f"{level.completed:>4}/{level.requested:<5} "
            f"{shown(level.wall_seconds):>6} "
            f"{shown(level.throughput_per_second, 3):>5} "
            f"{shown(level.duration_min_seconds):>5} "
            f"{shown(level.duration_median_seconds):>8} "
            f"{shown(level.duration_max_seconds):>5} "
            f"{level.peak_in_flight:>4} "
            f"{shown(level.overlap_factor):>7} "
            f"{shown(level.speedup_vs_cap_1):>7} "
            f"{'passed' if level.passed else 'FAILED'}"
        )
        if not level.passed:
            lines.append(
                f"       failed: {level.failed}; timed out: {level.timed_out}; "
                f"denied: {level.denied}; cancelled: {level.cancelled}; "
                f"level deadline exceeded: {level.deadline_exceeded}; "
                f"integrity: {level.integrity}"
            )
    calls = "0" if report.passed else "not established"
    lines += [
        f"Workers reaped: {sum(level.workers_reaped for level in report.levels)}; "
        f"model, provider and external calls and retries: {calls}",
        "Speedup is an observation on this host only. It is not an acceptance "
        "criterion and is not evidence of hosted, multi-host or production "
        "capacity.",
        f"Benchmark invariants: {'passed' if report.passed else 'FAILED'}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", action="store_true", help="required to execute")
    parser.add_argument("--workflows", type=bounded(2, 16), default=8)
    parser.add_argument("--repeats", type=bounded(1, 3), default=1)
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)
    if not args.run:
        print("Nothing ran. The benchmark is opt-in: pass --run to execute it.")
        return 2

    from multi_agent_orchestration.benchmark import BenchmarkPlan, run_benchmark

    report = asyncio.run(
        run_benchmark(
            BenchmarkPlan(
                mode="local-distributed-scaling",
                workflows=args.workflows,
                repeats=args.repeats,
            )
        )
    )
    print(report.model_dump_json(indent=2) if args.json else render(report))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
