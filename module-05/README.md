# Module 5: AI Agent Engineering

Module 5 builds a stateful, bounded, tool-using autonomous agent with three
kinds of memory, reliability controls, and integrations with LangChain Agents,
OpenAI Function Calling, Anthropic Tool Use and Mem0. A Streamlit page
demonstrates every part of it.

The module is standalone. It imports nothing from Modules 1-4.

| Document | Contents |
| --- | --- |
| [`docs/SOURCE_REQUIREMENTS.md`](docs/SOURCE_REQUIREMENTS.md) | The authoritative course source: 30 requirements |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | The approved, frozen design, and (section 28) how the build differs from it |
| [`docs/TRACEABILITY.md`](docs/TRACEABILITY.md) | Each requirement mapped to code, tests and evidence class |
| [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) | Hands-on walkthroughs, sample inputs, expected results, and a 10-minute reviewer demo |
| [`docs/VERIFICATION.md`](docs/VERIFICATION.md) | Story-by-story evidence and the final gate results |

## Status

Stories 1-11 are complete and human-approved. Module 5 is released under the
annotated Git tag `v0.5.0-module-5`. All 30 source requirements are traced to
implementation, tests and verification evidence.

This is a teaching implementation verified locally. It has **not** been
verified against live OpenAI, live Anthropic or Mem0 cloud, and it is not a
production deployment.

## Architecture

```
src/ai_agent_engineering/
    models.py          AgentRunState (typed workflow state), AgentStatus (12 states)
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
tests/                 17 test files, 228 tests
```

## How it works

**Autonomous agent.** `run_agent` takes a goal, moves the run through an
application-owned lifecycle (received, initialized, context ready, reasoning,
tool selected, validated, executing, observed), and repeats reason, act,
observe until a decision provider finishes or the step budget runs out. Every
step leaves an application-visible `DecisionRecord`; no private
chain-of-thought is stored or shown. Runs end in `completed` or
`budget_exhausted`; a denied or failing tool call stops the run with a typed
error and is never reported as success.

**Tool authority boundary.** `ToolRegistry` is the only way a tool runs. A
proposed call must name an allowlisted, authorized tool and its arguments must
pass the tool's JSON Schema before the handler runs. Unknown tools, extra
arguments and invalid values are denied. There is no shell, eval or
filesystem tool. Model, provider, tool and memory output is data and cannot
register tools or change the allowlist.

**Memory.** Short-term memory holds bounded session context. Long-term memory
keeps facts across runs. Episodic memory records past runs (goal, outcome,
tools). `Mem0MemoryAdapter` puts Mem0 behind an application-owned contract
with per-user scoping. Recalled memory is context only and never grants
authority. In the demo, memory is loaded into the run state before a run and
the run is recorded afterwards.

**Provider integrations.** Each integration exposes the registry's tools in
the provider's format and sends every proposed call back through
`ToolRegistry`:

- LangChain Agents: the real `create_agent` runtime with registry tools as
  `StructuredTool`s.
- OpenAI Function Calling: a bounded Responses API loop.
- Anthropic Tool Use: a bounded Messages API loop with `tool_result`
  continuation.

Both provider loops pre-validate the whole batch of tool calls before running
any of them, and cap requests and tool calls.

**Reliability.** `run_with_retry` (bounded, retryable errors only),
`run_with_timeout` (a real cancelling deadline) and `run_with_fallback`
(explicit recoverable errors, fallback use visible) are standalone primitives.
The agent loop itself enforces the step budget and fails closed. Retry,
timeout and fallback are not wired into `run_agent`.

## Streamlit demonstration

### Start here: hands-on user guide

If you are trying the application for the first time, begin with the **[Streamlit User Guide](docs/USER_GUIDE.md)**. It provides four end-to-end walkthroughs with ready-to-use sample inputs, expected results, security and reliability demonstrations, and a 10-minute reviewer path through the application.

The page has four tabs, each with "what to do / what to expect / what it
proves" guidance:

| Tab | What you can do |
| --- | --- |
| Autonomous Agent | Pick or type a goal, set a step budget, run the agent, and inspect the lifecycle trace, decisions, tools, observations and workflow state |
| Memory | Inspect short-term context and episodes, add long-term facts, use the Mem0 adapter (stand-in) and, in the offline Mem0 launch, the genuine Mem0 library |
| Tool Integrations | Run the LangChain, OpenAI and Anthropic paths; switch to a hostile proposal to see an invented `shell` call denied |
| Reliability | Run 10 scenarios: retry, timeout, fallback, budget exhaustion and denials |

A coverage table on the page maps each lab and deliverable to where it runs.

### Run the ordinary zero-key UI

From the repository root (PowerShell):

```powershell
.\.venv\Scripts\python.exe -m streamlit run module-05/app.py
```

No API key is needed and none is read. The page makes no network calls: provider demos use in-process
mock transports. In this launch the genuine Mem0 section explains that Mem0 is
unavailable.

### Run genuine local Mem0 (offline)

From the repository root (PowerShell):

```powershell
$env:MEM0_TELEMETRY='False'; $env:HF_HUB_OFFLINE='1'; uv run --offline --no-sync --with mem0ai==2.2.1 streamlit run module-05/app.py --server.fileWatcherType none
```

Then open Memory and press **Start genuine local Mem0**.

- `MEM0_TELEMETRY=False` is required. Mem0 sends PostHog telemetry by
  default; the app refuses to start Mem0 while it is on.
- `HF_HUB_OFFLINE=1` is required so the embedder cannot contact the Hugging
  Face Hub; the app refuses to start Mem0 otherwise.
- `--offline --no-sync` reuses the already-cached uv overlay, downloads
  nothing and leaves `.venv` untouched.
- `--server.fileWatcherType none` avoids harmless watcher tracebacks from
  `transformers`.

Mem0 then uses local Qdrant in a temporary directory, the cached
`sentence-transformers/all-MiniLM-L6-v2` embedder and a local fake LangChain
model, and stores memories verbatim (`infer=False`).

## Evidence classifications

| Integration | What is genuine | What is not |
| --- | --- | --- |
| LangChain Agents | The real LangChain `create_agent` runtime and tool loop | The model is a local scripted chat model; no LLM is called |
| OpenAI Function Calling | Real OpenAI SDK request serialization and response parsing | HTTP transport is mocked. **Not live OpenAI evidence** |
| Anthropic Tool Use | Real Anthropic SDK request serialization and response parsing | HTTP transport is mocked. **Not live Anthropic evidence** |
| Mem0 | Real `mem0` 2.2.1 locally: local Qdrant, cached Hugging Face embedder, local fake LangChain LLM; telemetry off and network offline in the Story 10 and Story 11 runs | **Not Mem0 cloud or remote evidence.** The stand-in on the Memory tab is adapter evidence only |
| Agent, tools, memory, reliability | Deterministic local execution of Module 5 code | Decision providers are deterministic, not a model |

**Story 5 telemetry note.** The first genuine Mem0 run (Story 5) left Mem0
telemetry at its default (on). Anonymous PostHog telemetry was likely
attempted; delivery was not verified. That run made 0 remote LLM calls and 0
paid calls. Later runs disable telemetry.

## Security properties

- Zero-key startup; credentials are never read, stored or printed by the app.
- No automatic or paid provider calls in the app or the tests; the mock SDK
  clients use `*.invalid` URLs and a placeholder key.
- `ToolRegistry` is the sole execution authority for the runner and all three
  integrations.
- Hostile proposals (invented tools, injected arguments) are denied before
  any handler runs; hostile memory stays data.
- User, tool, memory and provider text is rendered as plain text, never
  Markdown.
- `app.py` uses no `eval`, `exec`, `subprocess` or environment access
  (source test).
- Genuine Mem0 refuses to start unless telemetry is off and the hub is
  offline.

## Verification

From the repository root:

```powershell
.\.venv\Scripts\ruff.exe check module-05
$env:PYTHONPATH='module-05/src'; .\.venv\Scripts\python.exe -m pytest module-05/tests -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m compileall -q module-05/app.py module-05/src module-05/tests
```

Story 11 results: Ruff PASS; pytest **224 passed, 4 skipped** in `.venv`;
compileall PASS; offline Mem0 overlay **227 passed, 1 skipped**; 0
non-loopback network attempts. Details are in `docs/VERIFICATION.md`.

## Known limitations

1. **Mem0 portability.** `mem0ai` is not a declared project dependency and is
   not in `.venv`. Genuine Mem0 runs only from Story 5's cached
   `uv run --with mem0ai==2.2.1` overlay. If that cache is removed, the
   offline launch fails cleanly rather than downloading.
2. **Temporary directories.** Each genuine Mem0 **Start** creates a
   `module5-mem0-*` directory under `%TEMP%` that is not deleted when the
   session ends.
3. **No live provider verification.** Live OpenAI and Anthropic calls, the
   session-only credential UI and the `RUN_LIVE_LLM_TESTS` gate described in
   the architecture were not built. Whether the live services accept these
   schemas (for example `minLength` in OpenAI strict mode) is unverified.
4. **Reliability is not wired into the agent loop.** Retry, timeout and
   fallback are demonstrated as standalone primitives; `run_agent` never
   enters `timed_out` and does not populate `retry_count` or
   `fallback_history`.
5. `Mem0MemoryAdapter.from_default_mem0()` would build Mem0 with its remote
   defaults. Nothing in Module 5 calls it; do not call it without configuring
   Mem0 explicitly.
