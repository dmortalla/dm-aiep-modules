# Module 1 — Python, APIs, and LLM SDK Foundations

![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)
![pytest](https://img.shields.io/badge/tests-pytest-brightgreen)
![Ruff](https://img.shields.io/badge/code%20quality-Ruff-brightgreen)
![Pydantic](https://img.shields.io/badge/validation-Pydantic-blueviolet)
![httpx](https://img.shields.io/badge/HTTP-httpx-informational)
![OpenAI SDK](https://img.shields.io/badge/SDK-OpenAI-412991)
![Anthropic SDK](https://img.shields.io/badge/SDK-Anthropic-D97757)
![Gemini SDK](https://img.shields.io/badge/SDK-Gemini-4285F4)
![Postman](https://img.shields.io/badge/API%20testing-Postman-FF6C37)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B)

A provider-independent LLM client foundation: asynchronous REST and SDK access
to OpenAI, Anthropic and Gemini behind one Pydantic-validated service, with
streaming, structured-response parsing, retries and rate-limit handling, token
cost management, queue-based execution and safe credential handling, presented
through a runnable Streamlit application.

## Executive Summary

**What:** Module 1 is a provider-independent LLM engineering foundation that unifies OpenAI, Anthropic, and Gemini behind one validated application service.

**How:** Python 3.12, httpx, provider SDKs, Pydantic models, asynchronous execution, streaming, structured-response validation, retries, rate-limit handling, queue-based workflows, and explicit credential controls are composed behind application-owned interfaces.

**Why:** The module establishes the reliable API, provider, concurrency, validation, resilience, and cost-management primitives that later portfolio systems build upon.

**Proof:** Reviewers can launch the Streamlit application, exercise the provider-independent workflows, inspect the implementation and tests, and verify the recorded 84-test completion evidence together with provider, credential, streaming, queue, and rate-limit checks.

## Start Here / Reviewer Path

**Hands-on reviewer path:** follow the [Module 1 User Guide](docs/USER_GUIDE.md) for launch instructions, exact UI controls, safe credential handling, sample prompts, expected results, troubleshooting, and a five-minute review sequence.

Module 1 is complete and released under the annotated Git tags
`v0.1.0-module-1` and `v0.1.1-module-1`. Every source requirement is mapped to
implementation and verification evidence in the table below.

Start by launching the Streamlit application (see [Run Locally](#run-locally)).
It starts with **no authorized API credential**, so a visitor must explicitly
authorize a provider for the current session before any provider request can be
made.

## Key Capabilities

- Async REST client using httpx
- OpenAI, Anthropic and Gemini SDK integrations
- Provider-independent Pydantic models
- Async generation and streaming service, with incremental browser streaming
- Concurrent request execution and queue-based asynchronous execution
- Event-driven workflows
- Structured response parsing and validation
- Token usage normalization and cost estimation
- Retry, timeout, exponential-backoff and HTTP 429 `Retry-After` handling
- Operational logging
- Postman REST/API exercises
- Zero-key startup and session-only credential authorization

## Architecture

```text
module-01/
    src/ai_engineering_foundations/
        api_client.py        async httpx REST client: retries, timeouts, 429 Retry-After
        base.py, models.py   provider contract and provider-independent Pydantic models
        providers/           openai_provider.py, anthropic_provider.py, gemini_provider.py
        service.py           LLMService: async generation, streaming, concurrency, queues
        structured.py        structured response parsing and validation
        costs.py             token-usage normalization and cost estimation
        credentials.py       credential handling utilities
        events.py            AsyncEventDispatcher and WorkflowEvent
    app.py                   Streamlit application (presentation layer)
    postman/                 REST/API exercise collection
    tests/                   15 test files
```

Provider SDK differences are isolated inside the provider implementations, so
`LLMService` and the application work against one normalized request/response and
token-usage model.

## Technology Stack

| Role | Technologies |
| --- | --- |
| Language and validation | Python 3.12, Pydantic |
| HTTP and API integration | httpx, REST APIs, Postman |
| LLM providers | OpenAI SDK, Anthropic SDK, Gemini SDK |
| Application layer | Provider-independent asynchronous LLM service |
| Presentation | Streamlit |
| Testing and quality | pytest, Ruff, Python compilation validation |

## Production-Grade Engineering

- **Resilience:** bounded retries with exponential backoff, request timeouts and
  explicit rate-limit handling in the API client and providers.
- **Cost management:** normalized `TokenUsage` and cost estimation across
  providers.
- **Concurrency:** `generate_many()` for concurrent execution and
  `generate_queued()` for queue-based execution.
- **Observability:** operational logging in the API client and service.
- **Typed boundaries:** provider-independent Pydantic models and a structured
  parser at the response boundary.

## Security and Trust Boundaries

The Streamlit application starts with no automatically authorized API
credential. Credentials entered through the Streamlit UI are session-only and are
not persisted by the UI. The underlying credential utilities demonstrate local
credential-management patterns for the module, while the
interface intentionally does not expose local or OS-level credential persistence
controls. The local `.env` file is ignored by Git and must never be committed.

## Testing and Verification

Recorded at module completion:

- 84 automated tests passing
- Ruff, pytest and Python compilation validation
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

The automated suite is under `tests/`. The live provider and browser-streaming
items above are completion checks recorded in the accepted Module 1 completion
checklist; this README does not repeat them and makes no claim beyond that
record.

## Run Locally

From the repository root:

```powershell
uv sync
uv run streamlit run module-01/app.py
uv run pytest
```

`uv run pytest` runs the repository's configured suite, which includes this
module's tests under `module-01/tests/`.

## Documentation / Deep Dives

Use these references when you want implementation-level evidence beyond the recruiter-facing overview.

### Documentation Index

- [User Guide](docs/USER_GUIDE.md) — hands-on launch, walkthroughs, expected results, security cleanup, and troubleshooting

- [Portfolio README](../README.md)
- Source: [`src/ai_engineering_foundations/`](src/ai_engineering_foundations/),
  [`app.py`](app.py), [`tests/`](tests/),
  [Postman collection](postman/module-01-rest-api-foundations.postman_collection.json)


<details>
<summary><strong>Source Requirements Traceability</strong></summary>

Every source requirement is mapped to implementation and verification evidence.


| Source requirement | Primary implementation evidence | Verification evidence |
| --- | --- | --- |
| Functions, OOP, error handling, type hints | `src/ai_engineering_foundations/` | Module 1 test suite |
| REST APIs and HTTP methods | `api_client.py` | `test_api_client.py` |
| Authentication patterns | `credentials.py`, Postman collection | `test_credentials.py`, `test_postman_collection.py` |
| Rate limiting | `api_client.py` — HTTP 429 / `Retry-After` handling | `test_api_client.py` |
| OpenAI SDK | `providers/openai_provider.py` | `test_openai_provider.py` |
| Anthropic SDK | `providers/anthropic_provider.py` | `test_anthropic_provider.py` |
| Gemini SDK | `providers/gemini_provider.py` | `test_gemini_provider.py` |
| Streaming | provider implementations, `service.py`, `app.py` | provider and Streamlit contract tests |
| Token cost management | `costs.py`, normalized `TokenUsage` models | `test_costs.py`, provider tests |
| Retry logic and timeout handling | `api_client.py`, provider implementations | `test_api_client.py`, provider tests |
| Logging strategies | `api_client.py`, `service.py` | API-client and service tests |
| Safe API handling | `credentials.py`, `app.py` | `test_credentials.py`, `test_public_credential_ui.py` |
| Async concurrency | `service.py` — `generate_many()` | `test_service.py` |
| Queue-based execution | `service.py` — `generate_queued()` | `test_queue_execution.py` |
| Event-driven workflows | `events.py` — `AsyncEventDispatcher` and `WorkflowEvent` | `test_events.py` |
| Build LLM API client | provider implementations and `service.py` | provider and service tests |
| Implement async API calls | `api_client.py`, providers, `service.py` | API-client/provider/service tests |
| Create streaming response workflows | providers, `service.py`, `app.py` | streaming/provider/UI tests |
| Build structured response parser | `structured.py` | `test_structured.py` |
| Postman | `postman/module-01-rest-api-foundations.postman_collection.json` | `test_postman_collection.py` |
| httpx | `api_client.py` | `test_api_client.py` |
| Production-ready API client | `api_client.py` | `test_api_client.py` |
| Async LLM interaction service | `service.py` | `test_service.py`, `test_queue_execution.py` |


</details>

<details>
<summary><strong>Definition of Done</strong></summary>


- [x] Python implementation
- [x] REST/API handling
- [x] OpenAI, Anthropic and Gemini SDKs
- [x] Postman and httpx
- [x] Async and concurrent LLM service
- [x] Queue-based execution and event-driven workflow
- [x] Streaming and structured response parsing
- [x] Token cost management
- [x] Rate-limit handling, retries and timeouts
- [x] Logging and safe API handling
- [x] Runnable Streamlit UI
- [x] Automated tests and runtime verification
- [x] Live provider verification


</details>

## Evidence and Limitations

- The credential utilities demonstrate local credential-management patterns for
  the module; the Streamlit UI deliberately exposes only session-only
  authorization.
- This is a foundations module: it is not a deployed service, and no hosted
  Streamlit deployment is claimed here.


For the six-system engineering progression and links to the other modules, see the [portfolio README](../README.md).

---

Developed from Techademy AI Engineering program requirements. Independent
implementation and engineering enhancements.
