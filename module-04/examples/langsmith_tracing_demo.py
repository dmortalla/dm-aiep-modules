"""Story 8 lab: genuine LangSmith SDK, offline only; no remote delivery claim."""

from advanced_rag_evaluation.observability.langsmith_adapter import (
    LangSmithTracer,
    OfflineTransport,
)
from advanced_rag_evaluation.telemetry.latency import LatencyReport, StageTiming


def main() -> None:
    """Show actual serialized SDK run relationships and timing summaries."""
    transport = OfflineTransport()
    report = LatencyReport(
        (StageTiming("retrieval", 0, 0.08), StageTiming("evaluation", 1, 0.12))
    )
    evidence = LangSmithTracer(transport).trace(report)
    print("Trace workflows with LangSmith: genuine SDK, deterministic_offline")
    print("How: injected offline HTTP transport; expected root + two children.")
    print(
        f"Actual: sdk={evidence.sdk_version} success={evidence.success} "
        f"requests={len(transport.records)} children={len(evidence.child_ids)}"
    )
    print("Remote delivery verified: False; no live verification performed.")
    for method, _, payload in transport.records:
        print(
            f"  {method} name={payload.get('name', 'completion')} "
            f"parent={bool(payload.get('parent_run_id'))} "
            f"outputs={payload.get('outputs', {})}"
        )
    print("Why: real SDK serialization proves integration; raw content is excluded.")


if __name__ == "__main__":
    main()
