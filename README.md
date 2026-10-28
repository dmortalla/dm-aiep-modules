# Production-Grade AI Engineering Systems Portfolio

![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)
![uv](https://img.shields.io/badge/packaging-uv-6C47FF)
![pytest](https://img.shields.io/badge/tests-pytest-brightgreen)
![Ruff](https://img.shields.io/badge/code%20quality-Ruff-brightgreen)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B)
![Standalone modules](https://img.shields.io/badge/architecture-standalone%20modules-informational)
![Techademy](https://img.shields.io/badge/Techademy-AI%20Engineering%20Program-informational)

*A portfolio of six independently demonstrable AI engineering systems developed from Techademy AI Engineering Program requirements, with independent architecture, implementation, production-grade engineering enhancements, testing and reviewer-facing Streamlit demonstrations.*

The portfolio progresses from LLM API and asynchronous Python foundations through prompt engineering and structured outputs, retrieval-augmented generation, advanced RAG evaluation, AI agent engineering, and multi-agent orchestration. Each system preserves the functional requirements of its source module and extends them with explicit architecture, automated verification, and security and reliability controls.

## Engineering approach

- **Architecture first.** Each module has a frozen architecture, source requirements and a traceability record before and after implementation.
- **Standalone modules.** Every module has its own package, tests, documentation and application, and imports nothing from the others.
- **Security and trust boundaries.** Model, provider, tool and retrieved output is treated as untrusted data; authority stays in application code.
- **Safe by default.** Applications start without credentials and run deterministically or against mocked boundaries; live integrations are explicit, bounded and opt-in.
- **Evidence discipline.** Claims are tied to tests and records, and different evidence classes are never merged.
- **Reviewer-visible.** Each system has a runnable Streamlit application.

### Evidence vocabulary

Module READMEs use these terms precisely: *deterministic/offline* verification, *mocked or offline provider-boundary* verification, *real local* execution, *external delivery* verification, *deployed* reviewer UI, and *limitations* where something is not verified. A badge or an adapter existing never means a live integration was verified.

## Engineering roadmap

| Module | System | Status |
| --- | --- | --- |
| 1 | [Python, APIs, and LLM SDK Foundations](module-01/README.md) | ✅ Complete (`v0.1.1-module-1`) |
| 2 | [Prompt Engineering & Structured Output Systems](module-02/README.md) | ✅ Complete (`v0.2.0-module-2`) |
| 3 | [RAG Engineering Foundations](module-03/README.md) | ✅ Complete (`v0.3.0-module-3`) |
| 4 | [Advanced RAG & Evaluation Systems](module-04/README.md) | ✅ Complete (`v0.4.0-module-4`) |
| 5 | [AI Agent Engineering](module-05/README.md) | ✅ Complete (`v0.5.0-module-5`), with a published production-grade upgrade |
| 6 | [Multi-Agent Systems & Orchestration](module-06/README.md) | 🔶 Engineering accepted; public reviewer deployment verified; release and LinkedIn closeout pending |

## Systems

### Module 1 — Python, APIs, and LLM SDK Foundations
An async, provider-independent LLM client over OpenAI, Anthropic and Gemini with streaming, structured parsing, retries and rate-limit handling, token cost management and session-only credential authorization.
**[README](module-01/README.md)** · [Streamlit app](module-01/app.py)

### Module 2 — Prompt Engineering & Structured Output Systems
Application-owned prompt construction, strict JSON/schema and typed-output validation, bounded advanced prompting techniques, independent tool authorization and deterministic evaluation, in an offline four-area Streamlit interface.
**[README](module-02/README.md)** · [Streamlit app](module-02/app.py)

### Module 3 — RAG Engineering Foundations
Ingestion with provenance, fixed/recursive/semantic chunking, embeddings and vector stores (FAISS, ChromaDB, Pinecone boundary), query transformation, bounded context and core versus LangChain RAG, in a nine-area Streamlit application.
**[README](module-03/README.md)** · [Streamlit app](module-03/app.py)

### Module 4 — Advanced RAG & Evaluation Systems
A hybrid RAG pipeline (BM25 plus semantic retrieval fused by RRF, reranking, filtering, caching) with latency and cost telemetry, RAGAS evaluation, LangSmith and LangFuse integrations and failure analysis, in a 12-section evaluation dashboard.
**[README](module-04/README.md)** · [Streamlit app](module-04/app.py)

### Module 5 — AI Agent Engineering
A bounded, stateful, tool-using agent with allowlisted tool authority, three kinds of memory, reliability controls and LangChain, OpenAI, Anthropic and Mem0 integrations, demonstrated in a four-tab Streamlit application.
**[README](module-05/README.md)** · **[Live demo](https://dm-aiep-module-05.streamlit.app/)** · [User guide](module-05/docs/USER_GUIDE.md)

### Module 6 — Multi-Agent Systems & Orchestration
Sequential, parallel, hierarchical, coordinator-worker and distributed orchestration on LangGraph, CrewAI and Google ADK, with cost governance, scaling evidence, and layered observability (LangSmith for AI tracing; OpenTelemetry → Collector → Prometheus → Grafana verified locally) in a six-tab reviewer cockpit. The public Streamlit reviewer deployment is verified (deterministic, no-key; Live/BYOK is unavailable by design). Hosted Grafana/Prometheus, production deployment and the final release closeout are not claimed.
**[README](module-06/README.md)** · [Streamlit app](module-06/app.py)

## Quick start

From the repository root, with Python 3.12 and [uv](https://docs.astral.sh/uv/):

```powershell
uv sync --locked
uv run streamlit run module-0N/app.py --browser.gatherUsageStats false   # N = 1 to 4
uv run pytest
```

Modules 5 and 6 have their own launch instructions in their READMEs ([Module 5](module-05/README.md), [Module 6](module-06/README.md)). Each module README lists the exact commands, evidence and limitations for that system.

---

Developed from Techademy AI Engineering program requirements. Independent implementation and engineering enhancements.
