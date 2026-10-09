# AI Engineering Program Modules

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Tests](https://img.shields.io/badge/tests-2069%20passing-brightgreen)
![Ruff](https://img.shields.io/badge/code%20quality-Ruff-brightgreen)
![OpenAI](https://img.shields.io/badge/LLM-OpenAI-412991)
![Anthropic](https://img.shields.io/badge/LLM-Anthropic-D97757)
![Gemini](https://img.shields.io/badge/LLM-Gemini-4285F4)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B)
![Postman](https://img.shields.io/badge/API%20Testing-Postman-FF6C37)

Source-faithful implementations of Modules 1-6 of the AI Engineering Program, organized as independently demonstrable engineering modules.

This repository progresses from LLM API and asynchronous Python foundations through prompt engineering, structured outputs, retrieval-augmented generation, advanced RAG evaluation, AI agent engineering, and the final Module 6 scope. Each module remains standalone while applying production-oriented engineering practices, automated verification, source traceability, and an appropriate runnable demonstration interface.

The Engineering Roadmap below records the verified completion state of each module. Detailed module documentation preserves implementation, testing, limitations, release evidence, and source-requirement traceability for each completed system.

## Engineering Roadmap

| Module | Status |
| --- | --- |
| Module 1 - Python, APIs, and LLM SDK Foundations | ✅ Complete |
| Module 2 - Prompt Engineering & Structured Output Systems | ✅ Complete |
| Module 3 - RAG Engineering Foundations | ✅ Complete |
| Module 4 - Advanced RAG & Evaluation Systems | ✅ Complete |
| Module 5 - AI Agent Engineering | ✅ Complete |
| Module 6 | Planned |

## Module 5 - AI Agent Engineering

### Start here: hands-on application guide

New to the module? **[Launch the live Streamlit application](https://dm-aiep-module-05.streamlit.app/)**, then use the **[Module 5 Streamlit User Guide](module-05/docs/USER_GUIDE.md)** for four end-to-end walkthroughs with ready-to-use sample inputs, expected results, security and reliability demonstrations, and a 10-minute reviewer path through the application.

Module 5 is complete, human-approved, and released under the annotated Git tag
`v0.5.0-module-5`. All 30 source requirements are traced to implementation,
tests, and verification evidence.

The standalone module builds a bounded, stateful autonomous AI agent with a
ReAct-style execution loop, allowlisted tool orchestration, short-term,
long-term, and episodic memory, plus retry, timeout, fallback, validation, and
safe-execution controls. Required integrations include LangChain Agents,
OpenAI Function Calling, Anthropic Tool Use, and Mem0.

A four-tab Streamlit presentation layer demonstrates the Autonomous Agent,
Memory, Tool Integrations, and Reliability workflows. The ordinary UI is
credential-free and uses local/deterministic execution with mocked provider
transports; genuine local Mem0 has a separate offline launch path.

**Module:** [`module-05/`](module-05/)
**Documentation:** [`module-05/README.md`](module-05/README.md)
**User Guide:** [`module-05/docs/USER_GUIDE.md`](module-05/docs/USER_GUIDE.md)
**Live Demo:** [Launch Streamlit app](https://dm-aiep-module-05.streamlit.app/)
**Streamlit source:** [`module-05/app.py`](module-05/app.py)
## Module 4 - Advanced RAG & Evaluation Systems

Module 4 Stories 1-12 are complete and human-approved, and Module 4 is
released under the annotated Git tag `v0.4.0-module-4`. All 29 source
requirements are complete: 26 complete and 3 complete with approved
limitations (LangSmith, LangFuse and Pinecone). The
[29-requirement evidence map](module-04/docs/TRACEABILITY.md) and
[verification record](module-04/docs/VERIFICATION.md) document the source
reconciliation, deterministic gates, and the human Streamlit verification.

The 12-section Streamlit evaluation dashboard runs the real hybrid pipeline:
dynamic retrieval, BM25 and ChromaDB semantic retrieval fused by Reciprocal
Rank Fusion, reranking, context filtering, retrieval caching, latency and cost
telemetry, RAGAS faithfulness/context precision/relevancy, LangSmith tracing,
LangFuse monitoring, and failure analysis. Module 4 is standalone and does not
import Modules 1-3.

Approved limitations: LangSmith and LangFuse use genuine SDK integrations
verified offline; live remote delivery is outside the final Module 4 scope.
Pinecone uses the genuine SDK boundary with deterministic offline
verification; live service verification was not performed. Generation is
extractive rather than LLM-generated, cost is an estimate rather than provider
billing, semantic embeddings use the accepted local deterministic
implementation, and dashboard RAGAS uses fixed judgments rather than a live
model judge. Normal tests and default UI paths are credential-free.

```powershell
uv sync --locked
uv run streamlit run module-04/app.py --browser.gatherUsageStats false
uv run python module-04/examples/hybrid_rag_workflow.py
```

See the [frozen architecture](module-04/docs/ARCHITECTURE.md),
[source requirements](module-04/docs/SOURCE_REQUIREMENTS.md), and
[Story 12 closeout](module-04/docs/STORY_12.md).

## Module 3 - RAG Engineering Foundations

Module 3 implementation and Stories 1-10 are complete, human-approved, released,
and published as the annotated Git tag `v0.3.0-module-3`. The
[28-requirement evidence map](module-03/docs/TRACEABILITY.md) and
[verification record](module-03/docs/VERIFICATION.md) document the source
reconciliation, deterministic gates, and human acceptance evidence.

The nine-area Streamlit UI demonstrates ingestion and provenance, fixed/recursive/
semantic chunking, embedding metrics, vector retrieval/stores, query transformation,
bounded context, core/LangChain RAG, and corpus-refresh knowledge freshness.
FAISS, ChromaDB and LangChain have genuine local runtime verification. Pinecone
has a genuine SDK/integration boundary with deterministic offline verification;
OpenAI Embeddings has a genuine provider adapter with offline request-response
verification. Live remote OpenAI/Pinecone verification is not established.

LocalHashEmbedder, the tiny semantic topic signal, and LocalExtractiveGenerator
are explicitly limited teaching implementations. They do not establish trained
semantic quality or source truth. Normal tests and default UI paths are
credential-free; the optional OpenAI panel requires an explicitly supplied key.

```powershell
uv sync --locked
uv run streamlit run module-03/app.py --browser.gatherUsageStats false
uv run python module-03/examples/rag_freshness.py
```

See the [frozen architecture](module-03/docs/ARCHITECTURE.md),
[source requirements](module-03/docs/SOURCE_REQUIREMENTS.md), and
[Story 10 closeout](module-03/docs/STORY_10.md).

## Module 2 - Prompt Engineering & Structured Output Systems

Module 2 demonstrates application-owned prompt construction, strict JSON/schema
and typed-output validation, bounded advanced prompting techniques, independent
tool authorization, repeatable red-team simulation, and deterministic evaluation
with separate PromptLayer observability. Its four Streamlit areas run locally
using synthetic responses without accounts, credentials, or external services.

Stories 1–10 are accepted. Module 2 implementation, documentation, source
traceability, automated verification, and human review are complete.
OpenAI JSON Mode and PromptLayer have genuine adapters with mocked verification;
offline receipts are not evidence of live output or remote storage.

```powershell
uv sync --locked
uv run streamlit run module-02/app.py --browser.gatherUsageStats false
```

See the [Module 2 guide](module-02/README.md),
[28-requirement evidence map](module-02/docs/TRACEABILITY.md), and
[verification record](module-02/docs/VERIFICATION.md).

## Module 1 - Python, APIs, and LLM SDK Foundations

Module 1 implements Python-based AI engineering foundations including REST/API interaction, provider SDKs, asynchronous execution, streaming, structured response parsing, retries, timeouts, rate-limit handling, token cost management, logging, queue-based execution, and safe API handling.

### Implemented Capabilities

- Async REST client using httpx
- OpenAI SDK integration
- Anthropic SDK integration
- Gemini SDK integration
- Provider-independent Pydantic models
- Async generation and streaming service
- Concurrent request execution
- Queue-based asynchronous execution
- Structured response parsing and validation
- Token usage normalization and cost estimation
- Retry, timeout, exponential-backoff, and HTTP 429 Retry-After handling
- Operational logging
- Postman REST/API exercises
- Zero-key startup and session-only public credential authorization
- Runnable Streamlit UI
- Incremental browser streaming

### Source Requirements Traceability

| Source requirement | Primary implementation evidence | Verification evidence |
| --- | --- | --- |
| Functions, OOP, error handling, type hints | `module-01/src/ai_engineering_foundations/` | Module 1 test suite |
| REST APIs and HTTP methods | `api_client.py` | `test_api_client.py` |
| Authentication patterns | `credentials.py`, Postman collection | `test_credentials.py`, `test_postman_collection.py` |
| Rate limiting | `api_client.py` - HTTP 429 / `Retry-After` handling | `test_api_client.py` |
| OpenAI SDK | `providers/openai_provider.py` | `test_openai_provider.py` |
| Anthropic SDK | `providers/anthropic_provider.py` | `test_anthropic_provider.py` |
| Gemini SDK | `providers/gemini_provider.py` | `test_gemini_provider.py` |
| Streaming | provider implementations, `service.py`, `app.py` | provider and Streamlit contract tests |
| Token cost management | `costs.py`, normalized `TokenUsage` models | `test_costs.py`, provider tests |
| Retry logic and timeout handling | `api_client.py`, provider implementations | `test_api_client.py`, provider tests |
| Logging strategies | `api_client.py`, `service.py` | API-client and service tests |
| Safe API handling | `credentials.py`, `app.py` | `test_credentials.py`, `test_public_credential_ui.py` |
| Async concurrency | `service.py` - `generate_many()` | `test_service.py` |
| Queue-based execution | `service.py` - `generate_queued()` | `test_queue_execution.py` |
| Event-driven workflows | `events.py` - `AsyncEventDispatcher` and `WorkflowEvent` | `test_events.py` |
| Build LLM API client | provider implementations and `service.py` | provider and service tests |
| Implement async API calls | `api_client.py`, providers, `service.py` | API-client/provider/service tests |
| Create streaming response workflows | providers, `service.py`, `app.py` | streaming/provider/UI tests |
| Build structured response parser | `structured.py` | `test_structured.py` |
| Postman | `module-01/postman/module-01-rest-api-foundations.postman_collection.json` | `test_postman_collection.py` |
| httpx | `api_client.py` | `test_api_client.py` |
| Production-ready API client | `api_client.py` | `test_api_client.py` |
| Async LLM interaction service | `service.py` | `test_service.py`, `test_queue_execution.py` |

### Verification

- 84 automated tests passing
- Ruff validation
- pytest validation
- Python compilation validation
- Streamlit runtime smoke testing
- Credential security tests
- Provider contract tests
- Rate-limit handling tests
- Token-cost management tests
- Queue-execution tests
- Postman collection contract tests
- Streaming regression tests
- Live provider testing
- Progressive Gemini browser-streaming verification

### Run Module 1

Synchronize dependencies: `uv sync`

Launch the UI: `uv run streamlit run module-01/app.py`

Run tests: `uv run pytest`

### Security

The public Streamlit application starts with no automatically authorized API credential. Credentials entered through the public UI are session-only and are not persisted by the UI.

The underlying credential utilities demonstrate local credential-management patterns for the academic module, while the public interface intentionally does not expose local or OS-level credential persistence controls.

The local `.env` file is ignored by Git and must never be committed.

### Module 1 Definition of Done

- [x] Python implementation
- [x] REST/API handling
- [x] OpenAI SDK
- [x] Anthropic SDK
- [x] Gemini SDK
- [x] Postman
- [x] httpx
- [x] Async and concurrent LLM service
- [x] Queue-based execution
- [x] Event-driven workflow
- [x] Streaming
- [x] Structured response parsing
- [x] Token cost management
- [x] Rate-limit handling
- [x] Retries and timeouts
- [x] Logging
- [x] Safe API handling
- [x] Runnable Streamlit UI
- [x] Automated tests
- [x] Runtime verification
- [x] Live provider verification

Module 1 is complete.
