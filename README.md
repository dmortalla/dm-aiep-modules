# Production-Grade AI Engineering Systems Portfolio

![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)
![uv](https://img.shields.io/badge/packaging-uv-6C47FF)
![pytest](https://img.shields.io/badge/tests-pytest-brightgreen)
![Ruff](https://img.shields.io/badge/code%20quality-Ruff-brightgreen)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B)
![Standalone modules](https://img.shields.io/badge/architecture-standalone%20modules-informational)
![Techademy](https://img.shields.io/badge/Techademy-AI%20Engineering%20Program-informational)

*A six-system AI engineering portfolio progressing from provider integration and structured outputs through RAG, agent engineering, and multi-agent orchestration—each system independently runnable, tested, documented, and reviewer-visible.*

This repository contains six standalone systems developed from Techademy AI Engineering Program requirements and extended with production-grade engineering practices: explicit architecture, source-to-implementation traceability, bounded trust and authority, automated verification, reviewer-facing Streamlit applications, and evidence-aware documentation.

## Engineering Approach

- **Architecture first.** Each module is built against explicit requirements, architecture decisions, and traceability.
- **Standalone systems.** Every module has its own package, tests, documentation, and runnable application; modules do not depend on one another at runtime.
- **Application-owned authority.** Model, provider, retrieval, tool, and workflow output is treated as data rather than authority.
- **Safe defaults.** Deterministic, local, offline, or mocked paths are used where appropriate; live integrations are explicit and bounded.
- **Evidence discipline.** Deterministic, synthetic, mocked, real-local, externally delivered, recorded, and current evidence are kept distinct.
- **Reviewer-visible results.** Every module has a runnable Streamlit interface and a practical User Guide.
- **Production-grade without overclaiming.** Engineering quality, deployment evidence, external-service evidence, and limitations are stated separately.

### Evidence Vocabulary

Module documentation uses evidence terms deliberately. A configured adapter or technology badge does not by itself establish live service use. Likewise, a reviewer-facing deployment does not automatically mean production deployment.

Across the portfolio, documentation distinguishes among evidence such as:

- deterministic or offline execution;
- mocked or offline provider-boundary verification;
- synthetic execution;
- real-local execution;
- current versus recorded evidence;
- external delivery or service-read verification;
- deployed reviewer interfaces;
- explicit limitations and unverified boundaries.

## Engineering Roadmap

| Module | System | Status |
| --- | --- | --- |
| 1 | [Python, APIs, and LLM SDK Foundations](module-01/README.md) | ✅ Complete (`v0.1.1-module-1`) |
| 2 | [Prompt Engineering & Structured Output Systems](module-02/README.md) | ✅ Complete (`v0.2.0-module-2`) |
| 3 | [RAG Engineering Foundations](module-03/README.md) | ✅ Complete (`v0.3.0-module-3`) |
| 4 | [Advanced RAG & Evaluation Systems](module-04/README.md) | ✅ Complete (`v0.4.0-module-4`) |
| 5 | [AI Agent Engineering](module-05/README.md) | ✅ Complete (`v0.5.0-module-5`) |
| 6 | [Multi-Agent Systems & Orchestration](module-06/README.md) | ✅ Complete (`v0.6.0-module-6`) |

## Engineering Progression

[**1. API & Provider Foundations**](module-01/README.md) → [**2. Prompting, Structured Outputs & Trust Boundaries**](module-02/README.md) → [**3. RAG Foundations**](module-03/README.md) → [**4. Advanced Retrieval, Evaluation & Observability**](module-04/README.md) → [**5. Stateful Tool-Using Agents**](module-05/README.md) → [**6. Multi-Agent Orchestration & Distributed Coordination**](module-06/README.md)

The progression is deliberate:

1. **Module 1 — provider foundations:** Python, APIs, asynchronous execution, normalized LLM SDK boundaries, streaming, rate limits, cost handling, and credential controls.
2. **Module 2 — trusted structured interaction:** prompt engineering, structured outputs, validation, evaluation, prompt-injection testing, and explicit trust/authorization boundaries.
3. **Module 3 — RAG foundations:** ingestion, chunking, embeddings, vector stores, query transformation, bounded context assembly, provenance, and retrieval-augmented generation.
4. **Module 4 — advanced retrieval and evaluation:** hybrid retrieval, reranking, caching, RAG evaluation, failure analysis, telemetry, and observability.
5. **Module 5 — agent engineering:** bounded stateful tool use, memory, application-owned tool authority, reliability controls, and real provider integrations.
6. **Module 6 — multi-agent systems:** LangGraph, CrewAI, and Google ADK orchestration, distributed local coordination, bounded scaling evidence, and layered AI/operational observability.

Each module stands on its own for review; the sequence shows increasing system complexity rather than runtime coupling between modules.

## Systems

### Module 1 — Python, APIs, and LLM SDK Foundations

An asynchronous, provider-independent LLM client over OpenAI, Anthropic, and Gemini with normalized request/response contracts, streaming, structured parsing, retries, rate-limit handling, token-cost management, and session-scoped credential authorization.

**Review path:** [README](module-01/README.md) · [User Guide](module-01/docs/USER_GUIDE.md) · [Streamlit app](module-01/app.py)

### Module 2 — Prompt Engineering & Structured Output Systems

Application-owned prompt construction with strict JSON/schema and typed-output validation, bounded prompting techniques, prompt-injection testing, independent tool authorization, deterministic evaluation, and explicit provider-boundary evidence.

**Review path:** [README](module-02/README.md) · [User Guide](module-02/docs/USER_GUIDE.md) · [Streamlit app](module-02/app.py)

### Module 3 — RAG Engineering Foundations

A complete RAG foundation covering provenance-aware ingestion, fixed/recursive/semantic chunking, embeddings, FAISS and ChromaDB, a Pinecone boundary, query transformation, bounded context construction, and both core and LangChain RAG paths.

**Review path:** [README](module-03/README.md) · [User Guide](module-03/docs/USER_GUIDE.md) · [Streamlit app](module-03/app.py)

### Module 4 — Advanced RAG & Evaluation Systems

A hybrid retrieval and evaluation system combining BM25 and semantic retrieval with reciprocal-rank fusion, reranking, filtering, caching, latency/cost telemetry, RAGAS evaluation, LangSmith/LangFuse boundaries, and structured failure analysis.

**Review path:** [README](module-04/README.md) · [User Guide](module-04/docs/USER_GUIDE.md) · [Streamlit app](module-04/app.py)

### Module 5 — AI Agent Engineering

A bounded, stateful, tool-using agent with application-owned tool authority, three memory categories, reliability controls, and LangChain, OpenAI, Anthropic, and Mem0 integrations demonstrated through a four-tab reviewer application.

**Review path:** [README](module-05/README.md) · [User Guide](module-05/docs/USER_GUIDE.md) · **[Live demo](https://dm-aiep-module-05.streamlit.app/)**

### Module 6 — Multi-Agent Systems & Orchestration

A production-grade multi-agent orchestration system spanning sequential, parallel, hierarchical, coordinator-worker, collaborative, and distributed-local execution across LangGraph, CrewAI, and Google ADK, with bounded cost/reliability controls, local scaling evidence, LangSmith AI tracing, and OpenTelemetry → Collector → Prometheus → Grafana operational observability.

The public reviewer deployment is deterministic and no-key. Live/BYOK remains unavailable publicly by design; hosted Grafana/Prometheus, cloud scale, SLA, production capacity, and production deployment are not claimed.

**Review path:** [README](module-06/README.md) · [User Guide](module-06/docs/USER_GUIDE.md) · **[Live demo](https://dm-aiep-modules-module-06.streamlit.app/)**

## Portfolio Reviewer Path

For any module, follow the same sequence:

1. **README** — understand purpose, architecture, capabilities, evidence, and limitations.
2. **User Guide** — follow the practical reviewer walkthrough.
3. **Runnable UI** — execute the reviewer-facing Streamlit application.
4. **Deeper engineering evidence** — inspect architecture, source requirements, traceability, security, tests, and specialist evidence linked from the module README.

This keeps recruiter/reviewer navigation consistent while leaving authoritative business logic outside the presentation layer.

## Quick Start

From the repository root, install the locked environment:

```powershell
uv sync --locked
```

Modules 1–4 can be launched directly with Streamlit:

```powershell
uv run streamlit run module-0N/app.py --browser.gatherUsageStats false
```

Replace `N` with `1`, `2`, `3`, or `4`.

Modules 5 and 6 use their own accepted launch paths and reviewer instructions:

- [Module 5 README](module-05/README.md)
- [Module 6 README](module-06/README.md)

Run the repository test suite with:

```powershell
uv run pytest
```

For focused verification, use the exact commands documented by each module.

## Repository Scope and Evidence Boundaries

- The six systems are standalone modules, not one coupled production service.
- Reviewer-facing Streamlit deployments are presentation and demonstration surfaces.
- A deployed reviewer application is not automatically a production deployment.
- External-provider, telemetry, and delivery claims are made only where accepted evidence exists.
- Module-specific limitations supersede any broad portfolio-level shorthand.
- Release tags remain module-specific historical checkpoints.

---

Developed from Techademy AI Engineering Program requirements. Independent implementation and production-grade engineering enhancements.
