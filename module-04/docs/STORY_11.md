# Story 11 — RAG Operations & Evaluation Dashboard

Status: implemented for independent human review. Stories 1–10, the Story 10
placement amendment, and the Rule 44 isolation remediation are accepted. The
Story 11 architecture (presentation-only `module-04/app.py`) and five human
decisions were approved on 2026-10-08. Story 12 work is not included.

Run: `uv run streamlit run module-04/app.py` (repository root). Tests:
`uv run pytest module-04/tests/test_app.py`.

## Requirement evidence

| Requirement | Implementation and evidence |
| --- | --- |
| M4-DEL-02 Evaluation dashboard | `app.py` runs the real Story 10 pipeline, genuine RAGAS metric computation, and genuine LangSmith/LangFuse SDK serialization on every **Run workflow** click, and renders the returned contracts. Nothing is static. `tests/test_app.py` drives it with Streamlit `AppTest`. |
| M4-PORT-01 self-explanatory UI | Sidebar guidance: what it demonstrates, how to run/test, what to do, what to expect, and what each evidence label means. Every section states Expected / Actual / Why it matters. |
| M4-LAB-01..04 (UI demonstration) | Hybrid workflow (sections 1–8), RAGAS (9), reranking incl. opt-in cross-encoder (4–5), LangSmith tracing (10). |
| M4-RET, M4-OPT, M4-EVAL, M4-OBS | BM25/semantic/RRF (3), reranking (4), context filtering (5), dynamic retrieval (2), cache (6), latency (7), cost (8), RAGAS metrics (9), LangSmith/LangFuse (10–11), failure analysis (12). |
| M4-TOOL-05 Pinecone | Not exercised: it needs credentials and a live index. The provenance table labels it *Unavailable*. |

Traceability and status updates in `ARCHITECTURE.md` / `SOURCE_REQUIREMENTS.md`
belong to Story 12 and were not changed.

## Architecture

`app.py` is a presentation/orchestration consumer. It calls only public
Module 4 functions: `run_hybrid_rag`, `evaluate_latency_budget`,
`evaluate_cost_budget`, `to_evaluation_case`, `build_replay_judge`,
`RagasEvaluator.evaluate`, `LangSmithTracer.trace`, `LangFuseMonitor.monitor`,
and `analyze_failure`. No backend logic was moved or duplicated and nothing
under `src/` changed. The `*_rows` helpers are display projections that read
accepted contract fields into `list[dict]` for `st.dataframe`.
`CuratedScenario` and `RunSettings` are in-app fixture/widget records, not
runtime contracts. `MalformedScorerDemo` is the bounded fault double.

Resources: the demo corpus, its `BM25Index`, and its ephemeral
`ChromaSemanticIndex` are built once per process with `st.cache_resource`; the
Chroma collection is deleted when the resource is released. Each session owns
one `InMemoryRetrievalCache` and a run log in `st.session_state`. Nothing is
persisted, and no dependency, configuration, or service was added.

## Sections and evidence sources

| Section | Accepted evidence rendered |
| --- | --- |
| Evidence provenance | Generator id/evidence kind, embedder id, Chroma runtime, scorer type, RAGAS evidence kind/judge/embeddings/version, LangSmith/LangFuse SDK version and `remote_delivery_verified`, cost classification and pricing version, Pinecone *Unavailable*. |
| 1 Answer and citations | `GeneratedAnswer.text` (verbatim in `st.code`), citations with filter order, rerank rank/score, hybrid rank, RRF score, leg ranks, document/source id, passage. |
| 2 Dynamic retrieval | `DynamicRetrievalDecision` branch, term count, top_k, rationale, policy bounds. |
| 3 Retrieved evidence | `HybridCandidate` RRF score and both legs' rank/score; counts by leg membership. |
| 4 Reranking | `RerankedCandidate` rank/score with the fused rank, so movement is visible. |
| 5 Context filtering | Retained items and `FilterExclusion` reasons; active `ContextFilterConfig`. |
| 6 Retrieval cache | `CachedRetrieval.from_cache`, cache size, per-session run log; **Clear retrieval cache**. |
| 7 Latency | `LatencyReport` stages and total; `evaluate_latency_budget` against illustrative 1 s budgets. |
| 8 Cost | `CostEvaluation` usage (classification, convention), pricing version, cost; `evaluate_cost_budget`. |
| 9 RAGAS | `EvaluationResult` scores beside the fixture's expected values, evidence kind, judge, embeddings, version, judge-call count, strictness, plus the labelled fixture judgments. |
| 10 LangSmith | `TraceEvidence` success, SDK version, evidence kind, `remote_delivery_verified`, child runs, captured request count, serialized output field names, and a content-leak check over the captured payloads. |
| 11 LangFuse | `MonitoringEvidence` with the same fields and leak check. |
| 12 Failure analysis | `FailureAnalysis` stage, category, result_available, fatal, result_usable — from `HybridRagStageFailure.analysis`, `MonitoringEvidence.monitoring_failure`, or `analyze_failure` over `TraceEvidence.failure`. |

## Human decisions applied

1. **RAGAS: curated scenarios only.** Three curated scenarios carry
   human-authored replay judgments. RAGAS runs only when the actual answer and
   retained chunk ids equal the scenario fixture; otherwise the page shows a
   fixed *not evaluated* reason (custom query, abstention, or changed result).
   Expected scores: supported answer 1/1/1; useful passage ranked second
   1/0.5/1; short keyword query 1/1/0.408248 (hash embeddings compare token
   overlap). No provider/model judge exists.
2. **LangSmith/LangFuse: offline evidence only.** The accepted sealed offline
   transports are used; `remote_delivery_verified=False` is displayed as
   returned. No live transport was added.
3. **Cross-encoder: opt-in, off by default.** The normal path uses
   `DeterministicOverlapScorer`. A checkbox enables the accepted
   `SentenceTransformersCrossEncoderScorer`; a caption visible before
   activation states that it may download/load a model and increase latency.
   While it is on, the 0–1 score threshold is disabled because cross-encoder
   logits are unbounded (the `ContextFilterConfig` guidance).
4. **Fault injection: bounded demo controls.** A fixed select box offers
   none, reranking stage failure (the malformed scorer double, rejected by
   `rerank` as `RerankScorerError`), LangSmith transport failure, and LangFuse
   transport failure (the accepted `failure=` fixtures with fixed
   app-constructed exceptions). There is no free-form fault input.
5. **Rule 44 guard.** `tests/test_module_isolation.py` now scans `app.py` and
   imports it in a clean interpreter.

## Evidence labels

*Deterministic / offline*, *Measured*, *Estimate*, *Fixture data*, *Genuine
local model (opt-in)*, *Not evaluated*, *Unavailable*, and *Demo fault*. Labels
come from contract fields (`evidence_kind`, `remote_delivery_verified`,
`TokenUsage.classification`, `embedding_id`, scorer type), never from text.

## Security

- Untrusted text (query, passages, answer, fixture judgments) is rendered
  only through `st.text`, `st.code`, `st.dataframe`, and `st.metric` values.
  Markdown-capable elements receive only app-owned literals; an AST test
  enforces this, and there is no `unsafe_allow_html`, `st.html`, `st.write`,
  or `st.exception`. The built-in corpus includes an adversarial passage
  (instruction text, a Markdown image link, a script tag) that renders inertly.
- No credentials: the app reads no environment variable, `.env`, or
  `st.secrets`, and does not reference the Pinecone connection functions.
- No raw exception content: stage failures show only `FailureAnalysis`
  facts; unexpected errors show one fixed message and log only the exception
  type name. Transport fault text never reaches the page.
- Controls are fixed widgets with bounded values; no content selects
  configuration. The custom query is limited to 500 characters and
  re-validated by the contracts.
- The default path opens no network connection (tested with outbound
  sockets blocked).

## Tests

`tests/test_app.py` (23): `AppTest` start-up guidance; default offline run
(answer, citations, five stages, estimated cost, RAGAS matching fixture,
provenance labels, offline observability, no payload content); cache hit then
clear; custom query and changed filter settings not evaluated; reranking
fault; LangSmith and LangFuse transport faults; cross-encoder opt-in with the
model loader replaced (no download); inert rendering of hostile text; generic
unexpected-error message. Helper tests: every curated scenario matches its
fixture, short-query branch, row builders including single-leg candidates,
hostile text unchanged, truthful cache marker, threshold policy. Static checks:
formatted elements receive literals only, no HTML escape hatches, no
credential or live-provider access, bounded fault controls.

`tests/test_module_isolation.py` (13, previously 11): adds `app.py` to the
static scan and a clean-interpreter import check.

## What the dashboard cannot truthfully show

Live LangSmith/LangFuse delivery or consoles; provider/model-judged RAGAS;
RAGAS for custom queries or changed results; LLM-written answers; actual token
usage or monetary cost; learned semantic similarity; live Pinecone or remote
Chroma; per-leg RRF contribution values and full per-leg result lists (not
retained by `HybridResults`); cache statistics beyond `from_cache`, size, and
the run log; latency of the RAGAS/observability steps; real LangFuse
timestamps (synthetic anchor).

## Carried forward to Story 12

- The source requirements describe LangSmith/LangFuse as "live opt-in"; no
  live path is implemented. Record this gap in final traceability.
- Pinecone has offline boundary verification only.
- `examples/langfuse_monitoring_demo.py` still prints that the Story 11
  dashboard is future work; it was outside the approved Story 11 file list.
- Requirement status/traceability updates for M4-DEL-02 and M4-PORT-01, and a
  manual verification record of the running dashboard.
