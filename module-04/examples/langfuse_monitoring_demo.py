"""Story 9: genuine LangFuse monitoring API, offline and credential-free."""

from advanced_rag_evaluation.errors import RerankScorerError
from advanced_rag_evaluation.observability.failure_analysis import (
    Stage,
    analyze_failure,
)
from advanced_rag_evaluation.observability.langfuse_adapter import (
    LangFuseMonitor,
    OfflineMonitoringTransport,
)
from advanced_rag_evaluation.telemetry.latency import LatencyReport, StageTiming


def main() -> None:
    """Explain the serialized monitoring structure and safe failure facts."""
    latency = LatencyReport((StageTiming("retrieval", 0, 0.08),))
    failure = analyze_failure(Stage.RERANKING, RerankScorerError("excluded detail"))
    transport = OfflineMonitoringTransport()
    evidence = LangFuseMonitor(transport).monitor(latency, failure=failure)
    spans = transport.records[0]["resourceSpans"][0]["scopeSpans"][0]["spans"]
    print("What: LangFuse monitoring and deterministic failure analysis.")
    print("How: real LangFuse SDK OTLP API through an offline HTTP transport.")
    print("Expected: one POST containing a workflow span and one measured stage.")
    print(
        f"Actual: sdk={evidence.sdk_version} success={evidence.success} "
        f"requests={len(transport.records)} spans={len(spans)} seconds=0.08"
    )
    print(
        f"Failure: stage={failure.stage.value} category={failure.category.value} "
        f"fatal={failure.fatal} result_usable={failure.result_usable}"
    )
    print("Evidence: deterministic_offline; remote delivery verified: False.")
    print("Why: real SDK serialization proves integration, not remote ingestion.")
    print("Synthetic timestamp anchor; no production timing or live verification.")
    print("Dashboard: run module-04/app.py; section 11 shows this LangFuse evidence.")


if __name__ == "__main__":
    main()
