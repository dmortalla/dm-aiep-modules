# Module 5 — AI Agent Engineering

![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)
![pytest](https://img.shields.io/badge/tests-pytest-brightgreen)
![Ruff](https://img.shields.io/badge/code%20quality-Ruff-brightgreen)
![Pydantic](https://img.shields.io/badge/validation-Pydantic-blueviolet)
![LangChain Agents](https://img.shields.io/badge/agents-LangChain-1C3C3C)
![OpenAI Function Calling](https://img.shields.io/badge/OpenAI-function%20calling-412991)
![Anthropic Tool Use](https://img.shields.io/badge/Anthropic-tool%20use-D97757)
![Mem0](https://img.shields.io/badge/memory-Mem0-6C5CE7)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B)

A stateful, bounded, tool-using autonomous agent with three kinds of memory,
reliability controls, and integrations with LangChain Agents, OpenAI Function
Calling, Anthropic Tool Use and Mem0, demonstrated by a four-tab Streamlit
application.

## Executive overview

Module 5 builds an application-owned ReAct lifecycle in which a model proposes
and the application decides. Every tool call passes an allowlisted
`ToolRegistry`, memory is context and never authority, and provider output is
untrusted data. The module is standalone and imports nothing from Modules 1–4.

## Status and reviewer start-here

Stories 1–11 are complete and human-approved. Module 5 is released under the
annotated Git tag `v0.5.0-module-5`, and all 30 source requirements are traced to
implementation, tests and verification evidence. That tag is immutable and
identifies the original source-complete release.

A later production-grade upgrade, published to `main` without moving the tag, is
recorded in [`docs/PRODUCTION_READINESS.md`](docs/PRODUCTION_READINESS.md). It
added a session-only credential UI, bounded live OpenAI and Anthropic execution
paths, integrated retry and fallback, and runtime state reconciliation. Its
recorded verdict is production-ready **for the documented Streamlit deployment
scope**, with genuine live OpenAI and Anthropic verification under explicit human
authorization, and a published Streamlit application whose health endpoint and
production controls were verified.

**Start here:** [launch the live Streamlit application](https://dm-aiep-module-05.streamlit.app/),
then follow the [Streamlit User Guide](docs/USER_GUIDE.md): four end-to-end
walkthroughs with ready-to-use sample inputs, expected results, security and
reliability demonstrations, and a 10-minute reviewer path.

| Document | Contents |
| --- | --- |
| [`docs/SOURCE_REQUIREMENTS.md`](docs/SOURCE_REQUIREMENTS.md) | The authoritative course source: 30 requirements |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | The approved, frozen design, and (section 28) how the build differs from it |
| [`docs/TRACEABILITY.md`](docs/TRACEABILITY.md) | Each requirement mapped to code, tests and evidence class |
| [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) | Hands-on walkthroughs, sample inputs, expected results, and a 10-minute reviewer demo |
| [`docs/VERIFICATION.md`](docs/VERIFICATION.md) | Story-by-story evidence and the final gate results |
| [`docs/PRODUCTION_READINESS.md`](docs/PRODUCTION_READINESS.md) | The production-grade upgrade, live-provider evidence, deployment verification and claim boundary |

## Architecture

```
src/ai_agent_engineering/
    models.py          AgentRunState (typed workflow state), AgentStatus
    errors.py          domain errors
    agent/             lifecycle.py (validated transitions), react.py (decisions),
                       runner.py (bounded ReAct loop)
    tools/             schemas.py (ToolDefinition + JSON Schema), registry.py
                       (allowlist), builtins.py (calculator, knowledge_lookup,
                       note_lookup)
    memory/            short_term.py, long_term.py, episodic.py, mem0_adapter.py
    providers/         openai_tools.py, anthropic_tools.py
    integrations/      langchain_agent.py
    resilience/        retry.py, timeout.py, fallback.py
app.py                 Streamlit demonstration (presentation layer)
tests/                 test suite (see docs/VERIFICATION.md for gate results)
```

## Key capabilities

**Autonomous agent.** `run_agent` takes a goal, moves the run through an
application-owned lifecycle (received, initialized, context ready, reasoning,
tool selected, validated, executing, observed), and repeats reason, act, observe
until a decision provider finishes or the step budget runs out. Every step leaves
an application-visible `DecisionRecord`; no private chain-of-thought is stored or
shown. Runs end in `completed` or `budget_exhausted`; a denied or failing tool
call stops the run with a typed error and is never reported as success.

**Tool authority boundary.** `ToolRegistry` is the only way a tool runs. A
proposed call must name an allowlisted, authorized tool and its arguments must
pass the tool's JSON Schema before the handler runs. Unknown tools, extra
arguments and invalid values are denied. There is no shell, eval or filesystem
tool. Model, provider, tool and memory output is data and cannot register tools
or change the allowlist.

**Memory.** Short-term memory holds bounded session context. Long-term memory
keeps facts across runs. Episodic memory records past runs (goal, outcome, tools).
`Mem0MemoryAdapter` puts Mem0 behind an application-owned contract with per-user
scoping. Recalled memory is context only and never grants authority.

**Provider integrations.** Each integration exposes the registry's tools in the
provider's format and sends every proposed call back through `ToolRegistry`:

- LangChain Agents: the real `create_agent` runtime with registry tools as
  `StructuredTool`s.
- OpenAI Function Calling: a bounded Responses API loop.
- Anthropic Tool Use: a bounded Messages API loop with `tool_result`
  continuation.

Both provider loops pre-validate the whole batch of tool calls before running any
of them, and cap requests and tool calls.

## Production-grade engineering

- **Reliability.** `run_with_retry` (bounded, retryable errors only),
  `run_with_timeout` (a real cancelling deadline for awaitable operations) and
  `run_with_fallback` (explicit recoverable errors, fallback use visible) are
  standalone primitives. After the production-grade upgrade, `run_agent` composes
  bounded retry and explicit fallback at the synchronous decision-provider
  boundary and records `retry_count` and `fallback_history`; the safe default
  retries only `ConnectionError`. Ambiguous synchronous timeouts are not replayed
  automatically, and `timed_out` stays reserved for a future genuinely
  cancellable boundary. Escaped failures reconcile the run to a terminal `failed`
  state with normalized, application-owned descriptions.
- **Cost control.** Normal operation is zero-cost. Live execution is explicit,
  finite (request, tool-call and step caps, finite request timeout, SDK retries
  disabled) and potentially billable.
- **Evidence discipline.** Deterministic, mocked-transport, local, and genuine
  live evidence are collected and labelled separately.

## Security and trust boundaries

- Zero-key startup. Credentials entered in the deployed application are masked
  and session-only, and are never committed, persisted, printed, logged, traced
  or returned in tool output.
- Entering a credential makes no provider request; a separate explicit action,
  labelled as potentially billable, is required.
- Provider selection is application-allowlisted, and possession of a credential
  grants access only to the selected provider path.
- Automated live tests require both `RUN_LIVE_LLM_TESTS=1` and the provider
  credential; normal tests make no remote provider calls.
- `ToolRegistry` is the sole execution authority for the runner and all three
  integrations. Hostile proposals (invented tools, injected arguments) are denied
  before any handler runs, and hostile memory stays data.
- User, tool, memory and provider text is rendered as plain text, never Markdown.
  `app.py` uses no `eval`, `exec`, `subprocess` or environment access
  (source test).
- Genuine Mem0 refuses to start unless telemetry is off and the hub is offline.

## Streamlit demonstration

The page has four tabs, each with "what to do / what to expect / what it proves"
guidance:

| Tab | What you can do |
| --- | --- |
| Autonomous Agent | Pick or type a goal, set a step budget, run the agent, and inspect the lifecycle trace, decisions, tools, observations and workflow state |
| Memory | Inspect short-term context and episodes, add long-term facts, use the Mem0 adapter (stand-in) and, in the offline Mem0 launch, the genuine Mem0 library |
| Tool Integrations | Run the LangChain, OpenAI and Anthropic paths; switch to a hostile proposal to see an invented `shell` call denied |
| Reliability | Run 10 scenarios: retry, timeout, fallback, budget exhaustion and denials |

A coverage table on the page maps each lab and deliverable to where it runs. The
deterministic mocked-transport provider demonstrations remain separate from the
explicitly user-initiated OpenAI and Anthropic live paths.

## Evidence classifications

| Integration | What is genuine | What is not |
| --- | --- | --- |
| LangChain Agents | The real LangChain `create_agent` runtime and tool loop | In the default demonstration the model is a local scripted chat model; no LLM is called |
| OpenAI Function Calling | Real OpenAI SDK request serialization and response parsing in the default demonstration; a separate explicit live path was verified live under human authorization (see `docs/PRODUCTION_READINESS.md`) | In the default demonstration HTTP transport is mocked and **is not live OpenAI evidence** |
| Anthropic Tool Use | Real Anthropic SDK request serialization and response parsing in the default demonstration; a separate explicit live path was verified live under human authorization (see `docs/PRODUCTION_READINESS.md`) | In the default demonstration HTTP transport is mocked and **is not live Anthropic evidence** |
| Mem0 | Real `mem0` 2.2.1 locally: local Qdrant, cached Hugging Face embedder, local fake LangChain LLM; telemetry off and network offline in the Story 10 and Story 11 runs | **Not Mem0 cloud or remote evidence.** The stand-in on the Memory tab is adapter evidence only |
| Agent, tools, memory, reliability | Deterministic local execution of Module 5 code | Decision providers are deterministic in the default demonstration, not a model |

**Story 5 telemetry note.** The first genuine Mem0 run (Story 5) left Mem0
telemetry at its default (on). Anonymous PostHog telemetry was likely attempted;
delivery was not verified. That run made 0 remote LLM calls and 0 paid calls.
Later runs disable telemetry.

## Verification and evidence

From the repository root:

```powershell
.\.venv\Scripts\ruff.exe check module-05
$env:PYTHONPATH='module-05/src'; .\.venv\Scripts\python.exe -m pytest module-05/tests -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m compileall -q module-05/app.py module-05/src module-05/tests
```

At the Story 11 release the recorded results were Ruff PASS; pytest 224 passed,
4 skipped in `.venv`; compileall PASS; offline Mem0 overlay 227 passed, 1 skipped;
0 non-loopback network attempts. The production-grade upgrade then added its own
gates and live-provider verification, with the live-test gate left off
afterwards. Details and current gate results are in
[`docs/VERIFICATION.md`](docs/VERIFICATION.md) and
[`docs/PRODUCTION_READINESS.md`](docs/PRODUCTION_READINESS.md).

## Limitations and evidence boundaries

1. **Mem0 portability.** `mem0ai` is not a declared project dependency and is not
   in `.venv`. Genuine Mem0 runs only from Story 5's cached
   `uv run --with mem0ai==2.2.1` overlay. If that cache is removed, the offline
   launch fails cleanly rather than downloading.
2. **Temporary directories.** Each genuine Mem0 **Start** creates a
   `module5-mem0-*` directory under `%TEMP%` that is not deleted when the session
   ends.
3. **Claim boundary.** The production-ready verdict is scoped to the documented
   architecture and Streamlit deployment. It does not claim enterprise-scale high
   availability, multi-tenant operations, formal compliance certification,
   unlimited provider/model compatibility, or guarantees beyond the tested and
   documented boundary.
4. **Timeouts.** Retry and fallback are integrated into `run_agent`; a cancelling
   timeout is not, because the decision-provider contract is synchronous.
   `run_with_timeout` remains a standalone primitive and live requests keep
   finite SDK timeouts.
5. `Mem0MemoryAdapter.from_default_mem0()` would build Mem0 with its remote
   defaults. Nothing in Module 5 calls it; do not call it without configuring Mem0
   explicitly.

## Run and reviewer instructions

### Run the ordinary zero-key UI

From the repository root (PowerShell):

```powershell
.\.venv\Scripts\python.exe -m streamlit run module-05/app.py
```

No API key is needed to start. In the default demonstrations the page makes no
network calls: provider demos use in-process mock transports, and in this launch
the genuine Mem0 section explains that Mem0 is unavailable. Live provider paths
run only after an explicit, separately labelled user action.

### Run genuine local Mem0 (offline)

```powershell
$env:MEM0_TELEMETRY='False'; $env:HF_HUB_OFFLINE='1'; uv run --offline --no-sync --with mem0ai==2.2.1 streamlit run module-05/app.py --server.fileWatcherType none
```

Then open Memory and press **Start genuine local Mem0**.

- `MEM0_TELEMETRY=False` is required. Mem0 sends PostHog telemetry by default; the
  app refuses to start Mem0 while it is on.
- `HF_HUB_OFFLINE=1` is required so the embedder cannot contact the Hugging Face
  Hub; the app refuses to start Mem0 otherwise.
- `--offline --no-sync` reuses the already-cached uv overlay, downloads nothing
  and leaves `.venv` untouched.
- `--server.fileWatcherType none` avoids harmless watcher tracebacks from
  `transformers`.

Mem0 then uses local Qdrant in a temporary directory, the cached
`sentence-transformers/all-MiniLM-L6-v2` embedder and a local fake LangChain
model, and stores memories verbatim (`infer=False`).

## Documentation

[Source requirements](docs/SOURCE_REQUIREMENTS.md) · [Architecture](docs/ARCHITECTURE.md) ·
[Traceability](docs/TRACEABILITY.md) · [User Guide](docs/USER_GUIDE.md) ·
[Verification](docs/VERIFICATION.md) · [Production readiness](docs/PRODUCTION_READINESS.md) ·
[Portfolio README](../README.md)

---

Developed from Techademy AI Engineering program requirements. Independent
implementation and engineering enhancements.
