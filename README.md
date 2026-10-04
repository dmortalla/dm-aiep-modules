# AI Engineering Program Modules

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Tests](https://img.shields.io/badge/tests-1054%20passing-brightgreen)
![Ruff](https://img.shields.io/badge/code%20quality-Ruff-brightgreen)
![OpenAI](https://img.shields.io/badge/LLM-OpenAI-412991)
![Anthropic](https://img.shields.io/badge/LLM-Anthropic-D97757)
![Gemini](https://img.shields.io/badge/LLM-Gemini-4285F4)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B)
![Postman](https://img.shields.io/badge/API%20Testing-Postman-FF6C37)

Source-faithful implementations of the AI Engineering Program, organized as independently demonstrable engineering modules.

**Module 1 is a multi-provider LLM client that lets users interact with OpenAI, Anthropic, or Gemini through one unified interface while demonstrating production-oriented API and asynchronous Python engineering patterns.**

Choose a provider and model, supply a session-only API credential, enter a prompt, and interact with the selected LLM through the Streamlit interface. Underneath that simple workflow, the module demonstrates provider abstraction, async execution, streaming, REST/API handling, retries, rate-limit handling, token-cost estimation, queue-based execution, event-driven workflows, structured response parsing, logging, and safe credential handling.

## Engineering Roadmap

| Module | Status |
| --- | --- |
| Module 1 - Python, APIs, and LLM SDK Foundations | ✅ Complete |
| Module 2 - Prompt Engineering & Structured Output Systems | ✅ Complete |
| Module 3 - RAG Engineering Foundations | ✅ Complete |
| Modules 4-12 | Planned |

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
