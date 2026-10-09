# Module 5 Story 10: Integrated Streamlit Demonstration, Final Report

Date: 2026-10-08. Evidence classes: deterministic local, LangChain runtime with a local scripted model, mocked transport (real OpenAI/Anthropic SDKs), local stand-in backend for the Mem0 adapter. **No live provider evidence.**

## 1. STORY 10 STATUS

**COMPLETE**, pending independent acceptance review.

A runnable Streamlit presentation layer, `module-05/app.py`, exposes the four frozen areas (Autonomous Agent, Memory, Tool Integrations, Reliability) over the accepted Story 1-9 components. No `src/` file was changed, there was no architecture change and no dependency change, and Story 11 has not been started.

## 2. SOURCE / ARCHITECTURE INSPECTION

Inspected: `docs/SOURCE_REQUIREMENTS.md` (30 requirements, invariants 8-10 on the UI and evidence honesty), `docs/ARCHITECTURE.md` (sections 4, 13, 16-19, 26; principle 13 "UI demonstrates core behavior but does not contain core domain logic"), `docs/VERIFICATION.md`, the Story 5 Mem0 evidence files, the Story 9 report, all `src/ai_agent_engineering` modules, and all 15 existing test files. Module 4's `app.py` and `tests/test_app.py` were read only to follow the repository's Streamlit/AppTest conventions; nothing is imported from them.

Findings that shaped the UI:
- `run_agent` takes any `DecisionProvider`, and the only accepted decider (`build_deterministic_decider`) is single-tool, so the multi-step lab needed a demonstration decider.
- `run_agent` records no lifecycle history, so the trace is observed through the decider and a wrapped tool handler rather than reconstructed.
- `mem0` is **not installed** in `.venv`, and `Mem0MemoryAdapter.from_default_mem0()` would use Mem0's default remote paid LLM, so the UI does not call it.
- `httpx2` is a runtime dependency of `anthropic` 1.11.0, so the Anthropic mock transport adds no dependency.
- No app was present (`module-05/app.py` did not exist before this story).

## 3. UI IMPLEMENTATION

New files (both inside `module-05/`):
- `app.py`: a single-page Streamlit app with a header, an evidence-label legend, a lab/deliverable coverage table, and `st.tabs` for the four areas. Running `uv run streamlit run module-05/app.py` from the repo root works because the app adds its own `src/` to `sys.path`.
- `tests/test_app.py`: 34 tests.

The page's only additions are clearly labelled demonstration stand-ins for things that would otherwise need a remote model or service:
1. `plan_tool_calls` / `build_plan_decider`: a keyword planner that proposes allowlisted tool calls (at most 4) and feeds `run_agent`. Its proposals are treated as untrusted.
2. `ScriptedToolCallingModel`: a local LangChain `BaseChatModel` that proposes one planned call per turn.
3. Scripted provider responses served to real `OpenAI` / `Anthropic` clients through `httpx.MockTransport` / `httpx2.MockTransport` at `*.invalid` base URLs. The final message is built from the tool outputs the SDK actually sent.
4. `LocalMem0StandIn`: an in-process backend satisfying the accepted `Mem0Backend` protocol.

`observed_registry` rebuilds the default allowlist with the same definitions, schemas and authorization flags, wrapping only each handler so the page can observe real executions. Memory components live in `st.session_state` so they persist across reruns. The page uses no frontend framework, database, service layer or new architecture (Rule 44), and the OpenAI/Anthropic shared-helper refactor was not done.

## 4. AUTONOMOUS AGENT EVIDENCE

- The reviewer picks one of 5 preset goals or types one (max 300 characters), sets a step budget (1-8), toggles memory, and presses **Run agent**.
- The real `AgentRunState` + `run_agent` + `ToolRegistry` produce the following on the page: terminal state, steps used against the budget, number of tools executed, the goal, the final result, an **observed** lifecycle trace (received, reasoning, executing, terminal status), decision records (step/kind/tool/rationale), selected tools and observations, the memory context loaded into state, and the full workflow state snapshot (run_id, status, steps, observations, memories, retry/fallback fields, result, failure).
- Verified: "Explain ReAct and calculate 6 times 7" ends `completed` in 3 steps with tools [knowledge_lookup, calculator] and result 42.0. The three-tool preset runs 3 tools. Budget 2 ends `budget_exhausted`. A goal matching no tool finishes explicitly with no tool run.
- No private chain-of-thought: only the application-visible `DecisionRecord` rationale strings are shown, and the page says so.

## 5. MEMORY EVIDENCE

- Native memory (deterministic): `ShortTermMemory(12)`, `LongTermMemory`, and `EpisodicMemory(20)` are the accepted classes. With memory on, each run loads long-term facts, recent short-term context and the last 3 episodes into `AgentRunState.retrieved_long_term_memories` / `short_term_context` before execution. It then writes the goal and observations to short-term memory and an `Episode` to episodic memory. Repeating a goal reports the prior episode's outcome in the final result (context continuity). The long-term fact form, the short-term clear button and the episode table operate on the same objects.
- Mem0 is labelled separately: "Real Mem0MemoryAdapter over a local in-process stand-in backend. This is not the Mem0 library." The page shows whether `mem0` is installed (currently "no") and points to the genuine offline Mem0 evidence from Story 5 (`story-05-mem0-local-evidence.txt`). Add and recall go through the real adapter, and recall for `demo-user-b` does not return `demo-user-a`'s memory (tested).
- Hostile memory ("Register a shell tool…") stays inert data, and the next run executes only the planned allowlisted tool (tested).

## 6. TOOL INTEGRATIONS EVIDENCE

| Integration | Path exercised | Label shown | Result (multi-step goal) |
| --- | --- | --- | --- |
| LangChain Agents | `build_langchain_agent` + `invoke_langchain_agent` (real `create_agent`), scripted local chat model, LangSmith tracing disabled | Genuine LangChain runtime; no LLM called | knowledge_lookup, calculator executed via registry; final message contains 42.0 |
| OpenAI Function Calling | `run_openai_function_calling` with a real `OpenAI` client over `httpx.MockTransport` | Mocked transport; not live provider evidence | 2 requests; second continues `previous_response_id="resp-1"`; 2 executions |
| Anthropic Tool Use | `run_anthropic_tool_use` with a real `Anthropic` client over `httpx2.MockTransport` | Mocked transport; not live provider evidence | 2 requests; second ends in `tool_result` blocks; 2 executions |
| Mem0 | Memory area | Stand-in backend; not the Mem0 library | see section 5 |

Exact request bodies the SDKs sent, and the registry-derived tool schemas, are viewable on the page. The hostile option adds an invented `shell` call to the batch: OpenAI and Anthropic both return `UnknownToolError` with **0 tools executed and 1 request** (whole-batch prevalidation, no continuation). There are no live credential controls, which was the simpler option the task allowed. Live verification stays deferred and is stated on the page.

## 7. RELIABILITY EVIDENCE

Ten scenarios run on the real `run_with_retry`, `run_with_timeout`, `run_with_fallback`, `run_agent` and `ToolRegistry`, with local fault injection. Each is classified on the page as success (green), recovered (green), bounded failure (amber) or denied (red):

| Scenario | Classification |
| --- | --- |
| Retry recovers a transient fault (2 injected ConnectionErrors, attempts 1-3) | Recovered |
| Retry budget exhausted (3 attempts) | Bounded failure |
| Invalid call is not retried (`operation:"power"`, 1 attempt) | Denied |
| Timeout enforced (2 s operation, 0.05 s deadline, cancelled) | Bounded failure |
| Operation within deadline | Success |
| Fallback after provider outage (`used_fallback=True`) | Recovered |
| Execution budget exhausted (decider never finishes, budget 3) | Bounded failure |
| Unknown tool denied (`shell`, 0 executions, stops at tool_selected) | Denied |
| Injected argument denied (`command`, 0 executions) | Denied |
| Tool failure fails closed (divide by zero, stops at executing, not reported as success) | Bounded failure |

## 8. SOURCE LAB / DELIVERABLE COVERAGE

| ID | Runnable path in the UI | Test evidence |
| --- | --- | --- |
| M5-L01 Tool-using agent | Autonomous Agent > Run agent | `test_agent_area_runs_multi_step_goal_to_completion` |
| M5-L02 Memory-enabled workflows | Agent with memory on + Memory area | `test_agent_area_records_runs_into_memory_area`, `test_memory_area_stores_long_term_facts_used_by_next_run` |
| M5-L03 Multi-step reasoning | Agent multi-step presets (2-3 tools + finish) | decision records `tool, tool, finish` |
| M5-L04 Retry/fallback | Reliability area | `test_every_reliability_scenario_is_classified`, `test_reliability_area_renders_each_outcome_kind` |
| M5-D01 Autonomous AI agent | Autonomous Agent | as L01/L03 |
| M5-D02 Stateful workflow system | Workflow state expander + Memory | snapshot + continuity tests |

The coverage table on the page maps each ID to an existing area (tested).

## 9. SECURITY / AUTHORITY EVIDENCE

- Every tool execution goes through `ToolRegistry.validate_call` (spy-tested). The planner only ever proposes allowlisted names, including for hostile goals (parametrized test).
- UI inputs are untrusted. Goal, memory, tool and provider text are rendered only with `st.text`/`st.code`/`st.json`/`st.dataframe`. A `<script>…**run shell**` goal appears only as text, never in Markdown or other formatted elements, and executes only `calculator` (tested).
- `app.py` has no `eval`/`exec`/`compile`/`open`/`__import__` calls and no `subprocess`, `os.system`, `os.environ`, `getenv` or `dotenv` (AST/source test). Users choose scenarios and Mem0 user ids from fixed allowlists, and unknown scenario names raise `KeyError`.
- No credentials are read, persisted or printed. The SDKs receive the literal `mock-key-not-a-credential`, and only for `.invalid` mock transports.
- Startup and reruns construct no OpenAI/Anthropic client and never call `from_default_mem0` (constructor-refusal test).

## 10. REPAIR LOG

Semantic repairs to `app.py`: 0. Test-authoring repairs to the new `tests/test_app.py`: **2** (within the 3-attempt bound). No accepted test or security rule was weakened or deleted.
1. pytest failure: `from ai_agent_engineering.providers import anthropic_tools` returned the re-exported *function*, not the submodule (`AttributeError`). Fixed by resolving the submodules with `importlib.import_module`. Failed test rerun → pass.
2. pytest failure: the isolation test's `ast.parse` hit a UTF-8 BOM in an accepted test file (`test_builtin_tools.py`). Fixed by reading with `utf-8-sig`; the accepted file was left unchanged. Failed test rerun → pass.

Deterministic formatting: Ruff reported 4 × E501 (3 in `app.py`, 1 in the test). These were wrapped manually because E501 has no autofix and no unsafe fix was used. Then the full sequence restarted from Ruff.

Pre-gate correction (found by my own direct run, before the formal gate): a runtime tool failure (divide by zero) was initially classified "Denied". It was split so authority rejections are "Denied" and runtime failures are "Bounded failure".

## 11. QUALITY GATES

Final fail-fast sequence from the repo root using `.venv`, `PYTHONPATH=module-05/src`:
1. `ruff check module-05`: **PASS** ("All checks passed!")
2. `python -m pytest module-05/tests -q -p no:cacheprovider`: **PASS, 220 passed / 0 failed** (186 accepted baseline, re-confirmed before changes, plus 34 new)
3. `python -m compileall -q module-05/app.py module-05/src module-05/tests`: **PASS** (exit 0)

Network-blocked regression: the full suite was rerun with a scratchpad pytest plugin that blocks and counts non-loopback `connect`/`connect_ex`/`getaddrinfo`. Result: **220 passed, 0 non-loopback attempts**.

## 12. STREAMLIT RUNTIME EVIDENCE

- `python -m streamlit run module-05/app.py --server.headless true --server.address 127.0.0.1 --server.port 8599 --browser.gatherUsageStats false`: `/_stcore/health` returned `ok`.
- The page was loaded in the in-app browser. Title "Module 5: AI Agent Engineering"; all four tabs and the live-verification-not-performed banner rendered.
- Clicked **Run agent**: `completed`, steps 3 / 6, tools executed 2, result with 42.0, decision records and memory context shown.
- Tool Integrations > **Run Anthropic tool use**: "Scripted summary of tool results…" and the ToolRegistry execution metric rendered.
- Reliability > **Run scenario**: "Retry recovers a transient fault: Recovered".
- The server stderr has only the Uvicorn start line (no tracebacks). The server was stopped afterwards.
- AppTest covers the remaining widgets (Memory form, Mem0 add/recall, OpenAI/LangChain buttons, hostile radio, slider, all scenarios).
- No human browser review is required for the properties above.

## 13. LIVE / PAID CALL STATUS

- **0 live OpenAI calls, 0 paid OpenAI calls, 0 live Anthropic calls, 0 paid Anthropic calls.** No Mem0 remote calls.
- All provider traffic goes to in-process mock transports. The network-blocked suite recorded 0 attempts. Live verification was not performed and is shown as deferred on the page.

## 14. MODULE ISOLATION

**PASS.** All changes are in `module-05/` (`app.py`, `tests/test_app.py`, this report). `git diff --stat` on tracked files is empty, so Modules 1-4 and root files are unmodified. `app.py` and all Module 5 tests import no Module 1-4 package (AST test). There was no commit, push or tag: HEAD is still `9111fcc`, and its existing tag `v0.4.0-module-4` was not created by this story.

## 15. DEFINITION OF DONE

- [x] frozen architecture/source inspected
- [x] runnable Streamlit app exists
- [x] Autonomous Agent area works
- [x] Memory area works
- [x] Tool Integrations area works
- [x] Reliability area works
- [x] concise user guidance exists for each major workflow (What to do / expect / proves, in all 4 areas, tested)
- [x] tool-using agent lab visibly demonstrable
- [x] memory-enabled workflow visibly demonstrable
- [x] multi-step reasoning visibly demonstrable
- [x] retry/fallback visibly demonstrable
- [x] autonomous AI agent deliverable demonstrable
- [x] stateful workflow deliverable demonstrable
- [x] actual accepted Module 5 components are used (identity + spy tests)
- [x] no private chain-of-thought exposed
- [x] zero-key startup works
- [x] no automatic provider/paid calls
- [x] evidence classifications are accurate (every "live" line on the page carries "not"/"no"; tested)
- [x] safety/authority boundaries preserved
- [x] automated UI tests pass (34)
- [x] local Streamlit smoke test passes
- [x] Ruff PASS
- [x] pytest PASS: 220 passed
- [x] compileall PASS
- [x] accepted Stories 1-9 remain green (186 included in 220)
- [x] Module isolation PASS
- [x] no commit/push/tag
- [x] Story 11 not started

## 16. NEXT RECOMMENDED ACTION

Run an independent Story 10 acceptance review before Story 11.

Points for the reviewer:
- **Stand-ins are presentation-layer:** the keyword planner, the scripted LangChain model, the scripted provider responses and the Mem0 stand-in backend live in `app.py`, not `src/`. Each is labelled on the page. Confirm this placement is acceptable under architecture principle 13.
- **Mem0 on the page is adapter evidence only.** Genuine Mem0 evidence remains Story 5's offline run, because `mem0` is not installed in `.venv` and its default configuration would call a paid LLM.
- **Live credential UI was deliberately not built.** Live OpenAI/Anthropic schema compatibility remains deferred, as accepted in Stories 8-9.
- **For Story 11:** traceability/verification docs should record the 220-test baseline and this report. `docs/VERIFICATION.md` still ends at Story 4 and was not updated here because it is out of Story 10 scope.
