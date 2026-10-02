# AI Engineering Program Modules

Source-faithful implementations of the AI Engineering Program, organized as independently demonstrable engineering modules.

## Engineering Roadmap

| Module | Status |
| --- | --- |
| Module 1 - Python, APIs, and LLM SDK Foundations | Complete |
| Modules 2-12 | Planned |

## Module 1 - Python, APIs, and LLM SDK Foundations

Module 1 implements Python-based AI engineering foundations including REST/API interaction, provider SDKs, asynchronous execution, streaming, structured response parsing, retries, timeouts, logging, and safe API handling.

### Implemented Capabilities

- Async REST client using httpx
- OpenAI SDK integration
- Anthropic SDK integration
- Gemini SDK integration
- Provider-independent Pydantic models
- Async generation and streaming service
- Concurrent request execution
- Structured response parsing and validation
- Retry, timeout, and backoff handling
- Operational logging
- Zero-key startup and explicit credential authorization
- Runnable Streamlit UI
- Incremental browser streaming

### Verification

- 62 automated tests
- Ruff validation
- pytest validation
- Python compilation validation
- Streamlit runtime smoke testing
- Credential security tests
- Provider contract tests
- Streaming regression tests
- Live provider testing
- Progressive Gemini browser-streaming verification

### Run Module 1

Synchronize dependencies: uv sync

Launch the UI: uv run streamlit run module-01/app.py

Run tests: uv run pytest

### Security

The application starts with no automatically authorized API credential. Stored credentials remain inert until explicitly authorized by the user. Prompt text and model output have no credential-management authority.

The local .env file is ignored by Git and must never be committed.

### Module 1 Definition of Done

- [x] Python implementation
- [x] REST/API handling
- [x] OpenAI SDK
- [x] Anthropic SDK
- [x] Gemini SDK
- [x] Async and concurrent LLM service
- [x] Streaming
- [x] Structured response parsing
- [x] Retries and timeouts
- [x] Logging
- [x] Safe API handling
- [x] Runnable Streamlit UI
- [x] Automated tests
- [x] Runtime verification
- [x] Live provider verification

Module 1 is complete.
