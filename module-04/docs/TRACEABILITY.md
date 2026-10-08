# Module 4 Source-to-Evidence Traceability

This document maps every Module 4 requirement ID in
[SOURCE_REQUIREMENTS.md](SOURCE_REQUIREMENTS.md) to its source basis,
implementation, tests, runnable demonstration, and dashboard section.

**Authority.** The authoritative Module 4 course source comes first. Next
come the frozen requirements and [ARCHITECTURE.md](ARCHITECTURE.md),
including the Story 5, Rule 44, Story 10 placement, and Story 12 closeout
amendments. Recorded human decisions follow. Modules 1-3 are not a source of
any Module 4 requirement (Rule 44).

## Conventions

- Paths are relative to `module-04/`.
- Package source is `src/advanced_rag_evaluation/`, shortened here to `pkg/`.
- "UI §n" is the numbered section of the dashboard (`app.py`), run with
  `uv run streamlit run module-04/app.py`.
- Test counts are per file. All Module 4 tests run credential-free and
  offline.

## Summary

| Status | Count | IDs |
| --- | --- | --- |
| Complete | 26 | RET-01..05, OPT-01..05, EVAL-01..03, OBS-03, OBS-04, LAB-01..04, TOOL-01..04, DEL-01, DEL-02, PORT-01 |
| Complete — approved limitation | 3 | OBS-01, OBS-02, TOOL-05 |
| Partial | 0 | |
| Missing | 0 | |

All 29 requirement IDs are complete. M4-PORT-01 became `Complete` when the
human recorded the final manual Streamlit verification as PASS on
2026-10-08 (see [VERIFICATION.md](VERIFICATION.md)).

## Authoritative source coverage

| Source item | Requirement IDs |
| --- | --- |
| BM25, semantic retrieval, hybrid search architectures, query reranking, cross-encoder pipelines | M4-RET-01..05 |
| Context filtering, latency & cost optimisation, retrieval caching, dynamic retrieval | M4-OPT-01..05 |
| RAGAS: faithfulness evaluation, context precision, relevance scoring | M4-EVAL-01..03 |
| LangSmith tracing, LangFuse monitoring, latency tracking, failure analysis | M4-OBS-01..04 |
| Hands-on labs (4) | M4-LAB-01..04 |
| Tools: RAGAS, LangSmith, LangFuse, ChromaDB, Pinecone | M4-TOOL-01..05 |
| Deliverables: production-grade RAG architecture, evaluation dashboard | M4-DEL-01, M4-DEL-02 |
| Repository requirement: runnable self-explanatory UI | M4-PORT-01 |

## Retrieval / search

| ID | Implementation | Tests | Demonstration | Status |
| --- | --- | --- | --- | --- |
| M4-RET-01 BM25 | `pkg/bm25.py`: `BM25Index`, `LexicalQuery`, `LexicalResults` | `tests/test_bm25.py` (48) | `examples/bm25_search.py`; UI §3 | Complete |
| M4-RET-02 Semantic leg | `pkg/semantic_retrieval.py`: `ChromaSemanticIndex`, `HashEmbedder`, `SemanticResults`; fused by `hybrid_retrieval.fuse_results` | `tests/test_semantic_retrieval.py` (70), including `test_feeds_hybrid_fusion` | `examples/hybrid_search.py`; UI §3 | Complete |
| M4-RET-03 Hybrid fusion | `pkg/hybrid_retrieval.py`: Reciprocal Rank Fusion that retains both legs' rank and score | `tests/test_hybrid_retrieval.py` (38) | `examples/hybrid_search.py`; UI §3 | Complete |
| M4-RET-04 Query reranking | `pkg/reranking.py`: `rerank`, `RerankedResults`, keeping pre- and post-rerank evidence | `tests/test_reranking.py` (43) | `examples/reranking_demo.py`; UI §4 | Complete |
| M4-RET-05 Cross-encoder | `pkg/reranking.py`: `SentenceTransformersCrossEncoderScorer` (resolution 3) | `tests/test_reranking.py` with an injected scorer; `tests/test_app.py` opt-in with the model loader replaced | `examples/cross_encoder_verification.py` (explicit opt-in; one genuine model run is recorded in [STORY_04.md](STORY_04.md)); UI §4 opt-in | Complete |

## Optimisation

| ID | Implementation | Tests | Demonstration | Status |
| --- | --- | --- | --- | --- |
| M4-OPT-01 Context filtering | `pkg/context_filtering.py`: `filter_context`, `FilteredContext`, `FilterExclusion` (Story 5 amendment) | `tests/test_context_filtering.py` (33) | `examples/optimization_demo.py`; UI §5 | Complete |
| M4-OPT-02 Latency optimisation / measurement | `pkg/telemetry/latency.py`: `measure_stage`, `LatencyReport`, `evaluate_latency_budget`. Optimisation comes from the cache (OPT-04) and dynamic breadth (OPT-05). | `tests/test_latency.py` (58) | `examples/telemetry_demo.py`; UI §7 | Complete |
| M4-OPT-03 Cost optimisation / measurement | `pkg/telemetry/cost.py`: versioned `PricingConfig`, `actual` vs `estimated` `TokenUsage`, `evaluate_cost_budget` (resolution 8) | `tests/test_cost.py` (58) | `examples/telemetry_demo.py`; UI §8, labelled *Estimate* | Complete |
| M4-OPT-04 Retrieval caching | `pkg/retrieval_cache.py`: `InMemoryRetrievalCache`, `get_or_retrieve`, `from_cache` marker (resolution 6) | `tests/test_retrieval_cache.py` (42); pipeline cache hit/miss tests | `examples/optimization_demo.py`; UI §6 | Complete |
| M4-OPT-05 Dynamic retrieval | `pkg/dynamic_retrieval.py`: `decide_retrieval`, a documented deterministic policy (resolution 5) | `tests/test_dynamic_retrieval.py` (40) | `examples/optimization_demo.py`; UI §2 | Complete |

## Evaluation (RAGAS)

| ID | Implementation | Tests | Demonstration | Status |
| --- | --- | --- | --- | --- |
| M4-EVAL-01 Faithfulness | `pkg/evaluation/ragas_adapter.py` and `_ragas_runtime.py` make a genuine `ragas==0.3.1` call with an injected `ReplayJudge` (resolution 2). The provider-backed opt-in boundary (`allow_provider_backed=True`) is tested with offline doubles. | `tests/test_ragas_evaluation.py` (140) | `examples/ragas_evaluation_demo.py`; UI §9 | Complete |
| M4-EVAL-02 Context precision | Same as EVAL-01 | Same | Same | Complete |
| M4-EVAL-03 Relevance scoring | Same as EVAL-01, using RAGAS response relevancy over `HashEmbedder` vectors | Same | Same | Complete |

## Observability

| ID | Implementation | Tests | Demonstration | Status |
| --- | --- | --- | --- | --- |
| M4-OBS-01 LangSmith tracing | `pkg/observability/langsmith_adapter.py`: genuine `Client.create_run` and `update_run` calls over `OfflineTransport`, with content excluded | `tests/test_langsmith_tracing.py` (24) | `examples/langsmith_tracing_demo.py`; UI §10 | Complete — approved limitation (HITL-1) |
| M4-OBS-02 LangFuse monitoring | `pkg/observability/langfuse_adapter.py`: genuine `LangfuseAPI.opentelemetry.export_traces` call over `OfflineMonitoringTransport` | `tests/test_langfuse_monitoring.py` (74) | `examples/langfuse_monitoring_demo.py`; UI §11 | Complete — approved limitation (HITL-1) |
| M4-OBS-03 Latency tracking | Per-stage `LatencyReport` from `run_hybrid_rag`, carried into both SDK payloads | `tests/test_latency.py`; `tests/test_advanced_rag_pipeline.py` | `examples/telemetry_demo.py`; UI §7 | Complete |
| M4-OBS-04 Failure analysis | `pkg/observability/failure_analysis.py`: `Stage`, `Category`, `analyze_failure`; `HybridRagStageFailure.analysis` | `tests/test_langfuse_monitoring.py`; `tests/test_advanced_rag_pipeline.py`; `tests/test_app.py` | `examples/langfuse_monitoring_demo.py`; UI §12 with bounded fault injection | Complete |

## Hands-on labs

| ID | Implementation | Tests | Demonstration | Status |
| --- | --- | --- | --- | --- |
| M4-LAB-01 Build hybrid RAG workflow | `pkg/advanced_rag_pipeline.py`: `run_hybrid_rag`, `HybridRagResult`; `pkg/generation.py` (Story 10 placement amendment) | `tests/test_advanced_rag_pipeline.py` (30), `tests/test_generation.py` (54) | `examples/hybrid_rag_workflow.py` (subprocess-tested with sockets blocked); UI §1–8 | Complete |
| M4-LAB-02 Evaluate RAG with RAGAS | As EVAL-01..03 | `tests/test_ragas_evaluation.py` (demo subprocess-tested) | `examples/ragas_evaluation_demo.py`; UI §9 on curated scenarios (Story 11 decision 1) | Complete |
| M4-LAB-03 Implement reranking systems | As RET-04 and RET-05 | `tests/test_reranking.py` | `examples/reranking_demo.py`, `examples/cross_encoder_verification.py` (opt-in); UI §4 | Complete |
| M4-LAB-04 Trace workflows with LangSmith | As OBS-01 | `tests/test_langsmith_tracing.py` (demo subprocess-tested) | `examples/langsmith_tracing_demo.py`; UI §10 | Complete (offline evidence; see OBS-01) |

## Tools

| ID | Implementation | Tests | Status |
| --- | --- | --- | --- |
| M4-TOOL-01 RAGAS | Genuine RAGAS metric computation (EVAL-01..03) | `tests/test_ragas_evaluation.py` | Complete |
| M4-TOOL-02 LangSmith | Genuine LangSmith SDK tracing call (OBS-01) | `tests/test_langsmith_tracing.py` | Complete (offline-verified; see HITL-1) |
| M4-TOOL-03 LangFuse | Genuine LangFuse SDK monitoring call (OBS-02) | `tests/test_langfuse_monitoring.py` | Complete (offline-verified; see HITL-1) |
| M4-TOOL-04 ChromaDB | `ChromaSemanticIndex` over a genuine `chromadb.EphemeralClient` collection; the default semantic leg in the pipeline and dashboard | `tests/test_semantic_retrieval.py` | Complete |
| M4-TOOL-05 Pinecone | `PineconeSemanticIndex` using the installed SDK `Vector`, `QueryResponse` and `ScoredVector` types; `connect_pinecone_index` builds a real SDK handle | `tests/test_semantic_retrieval.py::TestPineconeBoundary` (10, offline injected client) | Complete — approved limitation (HITL-3). The dashboard labels Pinecone *Unavailable*. |

## Deliverables and repository UI

| ID | Evidence | Status |
| --- | --- | --- |
| M4-DEL-01 Production-grade RAG architecture | Runnable end-to-end `run_hybrid_rag`; 789 Module 4 tests; [ARCHITECTURE.md](ARCHITECTURE.md), this document, [VERIFICATION.md](VERIFICATION.md), and the story records `STORY_01.md`..`STORY_12.md` | Complete |
| M4-DEL-02 Evaluation dashboard | `app.py` runs the real pipeline, genuine RAGAS, and genuine SDK serialization on every run; nothing is static. `tests/test_app.py` (23) uses AppTest, helper and AST tests. | Complete |
| M4-PORT-01 Runnable self-explanatory UI | Sidebar guidance, and Expected / Actual / Why it matters in each section; `tests/test_app.py`; human manual Streamlit verification PASS on 2026-10-08, recorded in [VERIFICATION.md](VERIFICATION.md) | Complete |

## Approved limitations (final)

1. **LangSmith / LangFuse (HITL-1, 2026-10-08).** The SDK integrations are
   genuine and verified offline (`evidence_kind="deterministic_offline"`,
   `remote_delivery_verified=False`). The separate live opt-in path
   anticipated by resolution 4 was not built. Live remote delivery has not
   been verified and is outside the final Module 4 scope.
2. **Pinecone (HITL-3, 2026-10-08).** "Live service verification not yet
   performed" is the final Module 4 limitation. The genuine SDK boundary is
   verified offline only. No live index or credential is used.
3. **Other evidence boundaries, as accepted in earlier stories:**
   - Generation is extractive, not an LLM (Story 10).
   - Cost is a labelled estimate at fixture pricing unless a provider
     reports usage (resolution 8).
   - `HashEmbedder` measures token overlap, not learned meaning (Rule 44
     amendment).
   - Dashboard RAGAS runs only on curated scenarios with replay judgments
     (Story 11 decision 1).
   - The provider-backed RAGAS judge path is implemented but not
     live-verified (Story 7).
   - The real cross-encoder ran once, in Story 4, and is opt-in only
     (resolution 3).

## Rule 44 isolation

`tests/test_module_isolation.py` (13 tests) parses every Python file under
`src/`, `tests/`, `examples/`, and `app.py`. It fails on any import of
`ai_engineering_foundations`, `prompt_engineering_systems`, or
`rag_engineering_foundations`. It also imports every runtime module and the
dashboard in clean interpreters. Results are in
[VERIFICATION.md](VERIFICATION.md).
