# Module 4 — Advanced RAG & Evaluation Systems

![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)
![pytest](https://img.shields.io/badge/tests-pytest-brightgreen)
![Ruff](https://img.shields.io/badge/code%20quality-Ruff-brightgreen)
![ChromaDB](https://img.shields.io/badge/vector%20DB-ChromaDB-orange)
![RAGAS](https://img.shields.io/badge/RAG%20evaluation-RAGAS-purple)
![LangSmith](https://img.shields.io/badge/LangSmith-offline%20verified-1C3C3C)
![LangFuse](https://img.shields.io/badge/LangFuse-offline%20verified-0A0A0A)
![Pinecone](https://img.shields.io/badge/Pinecone-offline%20verified-000000)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B)

An advanced, evaluable hybrid RAG pipeline: dynamic retrieval, BM25 and ChromaDB
semantic retrieval fused by Reciprocal Rank Fusion, reranking, context filtering,
retrieval caching, latency and cost telemetry, RAGAS evaluation, LangSmith
tracing, LangFuse monitoring and failure analysis, presented in a 12-section
Streamlit evaluation dashboard.

## Executive overview

Module 4 extends the RAG idea into a measurable system: every stage produces
evidence that the dashboard shows beside the answer and its citations. The
module is standalone and does not import Modules 1–3; an isolation test enforces
this.

## Status and reviewer start-here

Module 4 Stories 1–12 are complete and human-approved, and the module is released
under the annotated Git tag `v0.4.0-module-4`. All 29 source requirements are
complete: 26 complete and 3 complete with approved limitations (LangSmith,
LangFuse and Pinecone). The [29-requirement evidence map](docs/TRACEABILITY.md)
and [verification record](docs/VERIFICATION.md) document the source
reconciliation, deterministic gates and the human Streamlit verification
(PASS, 2026-10-08).

Start with the dashboard, then the end-to-end workflow example (see
[Run](#run-and-reviewer-instructions)). Normal tests and default UI paths are
credential-free.

## Architecture

The pipeline is dynamic retrieval → BM25 and semantic retrieval → Reciprocal
Rank Fusion → reranking → context filtering → generation, with a retrieval
cache, telemetry and observability around it. See the frozen
[architecture](docs/ARCHITECTURE.md), including its human-approved amendments.

```text
src/advanced_rag_evaluation/
    dynamic_retrieval.py, bm25.py,        dynamic decision; BM25; ChromaDB semantic leg
    semantic_retrieval.py, hybrid_retrieval.py   (RRF fusion)
    reranking.py, context_filtering.py    reranking and filtering with evidence
    retrieval_cache.py                    retrieval caching
    advanced_rag_pipeline.py, generation.py   end-to-end pipeline; extractive generation
    telemetry/                            latency and cost
    evaluation/                           RAGAS adapter
    observability/                        LangSmith, LangFuse, failure analysis
app.py                                    Streamlit evaluation dashboard
examples/                                 nine offline demos and one opt-in verification
```

## Key capabilities

The dashboard renders twelve sections: (1) answer and citations, (2) dynamic
retrieval, (3) BM25 versus semantic retrieval fused by RRF, (4) reranking,
(5) context filtering, (6) retrieval cache, (7) latency, (8) cost, (9) RAGAS
evaluation, (10) LangSmith tracing, (11) LangFuse monitoring, and (12) failure
analysis, plus an evidence-provenance panel.

## Production-grade engineering

- Fail-fast quality gates and a Rule 44 module-isolation test.
- Retrieval caching with visible cache hits and a clearable cache.
- Latency budgets and a labelled cost estimate.
- Failure analysis that separates fatal faults (such as reranking) from nonfatal
  observability faults, so the answer is kept when tracing or monitoring fails.

## Security and trust boundaries

Adversarial retrieved text is displayed as untrusted data rather than treated as
instructions. Provenance shows `remote_delivery_verified=False` where delivery
was not performed, and the default dashboard path needs no credentials.

## Verification and evidence

- Release gates (Windows, 2026-10-08): Ruff clean; the full-repository suite
  passed with 1844 tests and three accepted ChromaDB deprecation warnings; the
  isolation test and import grep found no Module 1–3 imports; the Definition of
  Done was 27 of 27.
- Nine offline demos ran and exited 0, including the RAGAS demo and the
  LangSmith and LangFuse demos; the opt-in cross-encoder verification was not run
  in the closeout.
- A human performed the manual Streamlit verification and recorded PASS
  (2026-10-08); see the [verification record](docs/VERIFICATION.md).

## Limitations and evidence boundaries

- LangSmith and LangFuse use genuine SDK integrations verified offline; live
  remote delivery is outside the final Module 4 scope.
- Pinecone uses the genuine SDK boundary with deterministic offline verification;
  live service verification was not performed.
- Dashboard RAGAS uses fixed judgments rather than a live model judge.
- Generation is extractive rather than LLM-generated, and cost is an estimate
  rather than provider billing.
- Semantic embeddings use the accepted local deterministic implementation and do
  not demonstrate learned semantic similarity.

## Run and reviewer instructions

From the repository root:

```powershell
uv sync --locked
uv run streamlit run module-04/app.py --browser.gatherUsageStats false
uv run python module-04/examples/hybrid_rag_workflow.py
```

The other demos in [`examples/`](examples/) cover BM25, hybrid search, reranking,
optimization, telemetry, RAGAS, LangSmith and LangFuse. `cross_encoder_verification.py`
is an explicit opt-in path that downloads a model and is not part of normal runs.

## Documentation

[Architecture](docs/ARCHITECTURE.md) · [Source requirements](docs/SOURCE_REQUIREMENTS.md) ·
[Traceability](docs/TRACEABILITY.md) · [Verification](docs/VERIFICATION.md) ·
[Story 12 closeout](docs/STORY_12.md) · [Portfolio README](../README.md)

---

Developed from Techademy AI Engineering program requirements. Independent
implementation and engineering enhancements.
