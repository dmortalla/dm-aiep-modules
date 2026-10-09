# Module 5 Requirement Traceability

Story 11 reconciliation, 2026-10-08. Every row below was checked against the
current source, tests and runtime evidence, not against earlier documentation.

Paths are relative to `module-05/`. `src/` means `src/ai_agent_engineering/`.
Test names are in `tests/`. Test counts come from the Story 11 final gate (see
`VERIFICATION.md`).

## Evidence classes

| Class | Meaning |
| --- | --- |
| **DET** | Deterministic local execution of Module 5 code. |
| **LC** | Genuine LangChain `create_agent` runtime driven by a local scripted chat model. No LLM is called. |
| **MOCK-SDK** | The real OpenAI or Anthropic SDK serializes requests and parses responses; the HTTP transport is an in-process mock at a `*.invalid` URL. **Not live provider evidence.** |
| **MEM0-LOCAL** | The real `mem0` 2.2.1 library running locally (Qdrant on disk, cached Hugging Face embedder, local fake LangChain LLM) in the offline uv overlay. **Not Mem0 cloud or remote evidence.** |
| **STAND-IN** | The accepted `Mem0MemoryAdapter` over an in-process backend in `app.py`. Adapter evidence only; not the Mem0 library. |
| **UI** | Streamlit AppTest plus a real local Streamlit server smoke run. |

No requirement in this module carries live OpenAI, live Anthropic or remote
Mem0 evidence. Live verification was never performed.

## Matrix

### Agent systems

| ID | Requirement | Implementation | Verification evidence | Class | Status |
| --- | --- | --- | --- | --- | --- |
| M5-T01 | Agent lifecycle | `src/models.py` `AgentStatus` (12 states); `src/agent/lifecycle.py` `transition`, `allowed_transitions` | `test_lifecycle.py` (14: happy path, continuation, terminal isolation, invalid and forged transitions); UI lifecycle trace `test_agent_area_runs_multi_step_goal_to_completion` | DET, UI | COMPLETE |
| M5-T02 | Agent architectures | Layered single-agent design: state (`models.py`), control (`agent/`), tools (`tools/`), memory (`memory/`), providers/integrations, resilience; `docs/ARCHITECTURE.md` | Whole suite exercises each layer; `test_app.py::test_demonstrations_use_the_accepted_module_5_components` | DET | COMPLETE |
| M5-T03 | ReAct framework | `src/agent/react.py` `AgentDecision`, `DecisionRecord`; `src/agent/runner.py` `run_agent` (reason, act, observe loop) | `test_react.py` (7), `test_runner.py::test_runner_supports_multi_step_reasoning_cycle`; UI decision records | DET, UI | COMPLETE |
| M5-T04 | Goal-oriented systems | `AgentRunState.goal` (validated, non-empty); `run_agent` runs to an explicit goal result | `test_models.py::test_state_normalizes_goal_and_starts_received`, `test_empty_goal_is_rejected`; `test_app.py::test_empty_goal_is_rejected_by_the_run_state` | DET, UI | COMPLETE |
| M5-T05 | Execution loops | `run_agent` finite loop; `AgentRunState.max_steps`, `consume_step`, `BUDGET_EXHAUSTED` | `test_runner.py::test_execution_budget_terminates_loop`, `test_models.py::test_step_budget_is_consumed_without_exceeding_limit`; `test_app.py::test_agent_area_shows_budget_exhaustion` | DET, UI | COMPLETE |

### Tools and execution

| ID | Requirement | Implementation | Verification evidence | Class | Status |
| --- | --- | --- | --- | --- | --- |
| M5-T06 | Function calling | `src/tools/registry.py` `validate_call`/`execute`; `src/providers/openai_tools.py` (Responses API loop, Chat and Responses schemas); `src/providers/anthropic_tools.py` (Messages API loop); `src/integrations/langchain_agent.py` | `test_openai_tools.py` (31), `test_anthropic_tools.py` (38), `test_langchain_agent.py` (3) | DET, MOCK-SDK, LC | COMPLETE |
| M5-T07 | Tool schemas | `src/tools/schemas.py` `ToolDefinition` (JSON Schema validated by `jsonschema`); provider schema conversion in both provider modules | `test_tool_schemas.py` (10); `test_anthropic_tools.py::test_anthropic_tools_satisfy_installed_sdk_tool_param`; `test_openai_tools.py::test_response_tool_schema_preserves_calculator_contract` | DET, MOCK-SDK | COMPLETE |
| M5-T08 | Tool orchestration | `ToolRegistry` allowlist is the single execution path for the runner, LangChain bridge and both provider loops | `test_tool_registry.py` (8); `test_app.py::test_every_execution_passes_registry_validation`, `test_integrations_execute_through_registry` | DET, LC, MOCK-SDK | COMPLETE |
| M5-T09 | Dynamic tool selection | `ToolRegistry.select_for_goal`; decision providers choose tools at run time (`build_deterministic_decider`, UI planner `plan_tool_calls`) | `test_tool_registry.py::test_dynamic_selection_chooses_allowlisted_candidate`, `test_dynamic_selection_fails_closed_without_candidate`; `test_app.py::test_planner_only_proposes_allowlisted_tools` | DET, UI | COMPLETE |
| M5-T10 | Multi-step execution | `run_agent` multi-tool loop; bounded multi-request loops in both provider modules | `test_runner.py::test_runner_supports_multi_step_reasoning_cycle`; `test_openai_tools.py::test_request_loop_supports_multi_step_tool_use`; `test_anthropic_tools.py::test_request_loop_supports_multi_step_tool_use` | DET, MOCK-SDK | COMPLETE |

### Memory and state

| ID | Requirement | Implementation | Verification evidence | Class | Status |
| --- | --- | --- | --- | --- | --- |
| M5-T11 | Short-term memory | `src/memory/short_term.py` `ShortTermMemory` (bounded, clearable) | `test_memory.py` short-term tests; UI Memory area | DET, UI | COMPLETE |
| M5-T12 | Long-term memory | `src/memory/long_term.py` `LongTermMemory`; `src/memory/mem0_adapter.py` `Mem0MemoryAdapter` | `test_memory.py` long-term tests; `test_mem0_adapter.py` (20); `test_app_genuine_mem0.py` genuine round trip; `test_app.py::test_memory_area_stores_long_term_facts_used_by_next_run` | DET, STAND-IN, MEM0-LOCAL | COMPLETE |
| M5-T13 | Episodic memory | `src/memory/episodic.py` `Episode`, `EpisodicMemory` (bounded) | `test_memory.py::test_episode_records_prior_agent_experience`, `test_episodic_memory_is_bounded`; `test_app.py::test_agent_area_records_runs_into_memory_area` | DET, UI | COMPLETE |
| M5-T14 | State management | `AgentRunState` typed state; lifecycle-owned transitions; per-run independent collections | `test_models.py::test_mutable_state_collections_are_not_shared_between_runs`; `test_runner.py::test_runner_rejects_nonfresh_state`; UI workflow-state snapshot | DET, UI | COMPLETE |
| M5-T15 | Context continuity | Long-term and episodic memory survive runs; `app.py` `run_autonomous_agent` loads memory into `AgentRunState` before a run and records the run afterwards | `test_memory.py::test_long_term_memory_survives_run_object_boundaries`, `test_episodic_memory_supports_recent_context`; `test_app.py::test_memory_area_stores_long_term_facts_used_by_next_run` | DET, UI | COMPLETE (see note 1) |

### Reliability and safety

| ID | Requirement | Implementation | Verification evidence | Class | Status |
| --- | --- | --- | --- | --- | --- |
| M5-T16 | Retry strategies | `src/resilience/retry.py` `run_with_retry` (bounded attempts, retryable types only, cause preserved) | `test_retry.py` (7); `test_app.py::test_retry_recovers_after_exactly_three_attempts`; Reliability scenarios | DET, UI | COMPLETE |
| M5-T17 | Timeout handling | `src/resilience/timeout.py` `run_with_timeout` (`asyncio.wait_for`, cancels the task, typed `OperationTimeoutError`) | `test_timeout.py` (3); Reliability "Timeout enforced" / "Operation within deadline" | DET, UI | COMPLETE (see note 2) |
| M5-T18 | Failure recovery | `src/resilience/fallback.py` `run_with_fallback` (explicit recoverable types, `used_fallback` visible); runner fails closed on invalid decisions; budget exhaustion is a terminal state | `test_fallback.py` (5); `test_runner.py::test_invalid_decision_object_fails_run`; `test_app.py::test_every_reliability_scenario_is_classified` | DET, UI | COMPLETE (see note 2) |
| M5-T19 | Validation | Lifecycle transition validation; JSON Schema argument validation; decision-shape validation; provider-response validation; Mem0 result normalization | `test_lifecycle.py`, `test_tool_schemas.py`, `test_react.py::test_invalid_decision_shapes_are_rejected`, malformed-response tests in both provider files, `test_mem0_adapter.py::test_malformed_provider_results_fail_closed` | DET, MOCK-SDK | COMPLETE |
| M5-T20 | Safe execution patterns | Allowlist only (no shell, eval or filesystem tool); unknown tools and injected arguments denied before any handler runs; whole provider batches pre-validated; request and tool-call caps; memory is data | `test_runner.py::test_unknown_tool_proposal_cannot_gain_authority`, `test_invalid_tool_arguments_never_execute`; hostile-batch tests in both provider files; `test_app.py::test_app_has_no_shell_eval_or_credential_access`, `test_hostile_memory_gains_no_tool_authority`, `test_unsafe_agent_proposals_never_execute` | DET, MOCK-SDK, UI | COMPLETE |

### Hands-on labs

| ID | Requirement | Implementation | Verification evidence | Class | Status |
| --- | --- | --- | --- | --- | --- |
| M5-L01 | Build tool-using AI agent | `run_agent` + `ToolRegistry` + three teaching tools (`src/tools/builtins.py`); UI Autonomous Agent > Run agent | `test_runner.py::test_runner_executes_tool_observes_and_finishes`; `test_app.py::test_agent_area_runs_multi_step_goal_to_completion`; Story 11 Streamlit smoke run | DET, UI | COMPLETE |
| M5-L02 | Implement memory-enabled workflows | Native memory + Mem0 adapter; UI agent run with memory on + Memory area | `test_app.py::test_agent_area_records_runs_into_memory_area`, `test_memory_area_stores_long_term_facts_used_by_next_run`; `test_app_genuine_mem0.py::test_ui_runs_genuine_mem0_end_to_end` (overlay) | DET, UI, MEM0-LOCAL | COMPLETE |
| M5-L03 | Create multi-step reasoning systems | Multi-step ReAct runner; UI multi-step presets | `test_runner.py::test_runner_supports_multi_step_reasoning_cycle`; `test_app.py::test_agent_area_runs_multi_step_goal_to_completion` (decisions tool, tool, finish) | DET, UI | COMPLETE |
| M5-L04 | Build retry/fallback mechanisms | `src/resilience/`; UI Reliability area (10 scenarios) | `test_retry.py`, `test_fallback.py`, `test_timeout.py`; `test_app.py::test_reliability_area_renders_each_outcome_kind` | DET, UI | COMPLETE |

### Required tools

| ID | Requirement | Implementation | Verification evidence | Class | Status |
| --- | --- | --- | --- | --- | --- |
| M5-R01 | LangChain Agents | `src/integrations/langchain_agent.py`: real `langchain.agents.create_agent`, registry tools exposed as `StructuredTool`s that delegate to `ToolRegistry.execute` | `test_langchain_agent.py` (3); `test_app.py::test_integrations_execute_through_registry[run_langchain]` | LC (no remote LLM) | COMPLETE |
| M5-R02 | OpenAI Function Calling | `src/providers/openai_tools.py` `run_openai_function_calling` (Responses API, `previous_response_id` continuation, request and tool-call caps) | `test_openai_tools.py` (31) with a real `OpenAI` client over `httpx.MockTransport` | MOCK-SDK. **Not live OpenAI evidence.** | COMPLETE (live deferred) |
| M5-R03 | Anthropic Tool Use | `src/providers/anthropic_tools.py` `run_anthropic_tool_use` (Messages API, history resend, `tool_result` continuation, stop-reason checks) | `test_anthropic_tools.py` (38) with a real `Anthropic` client over `httpx2.MockTransport` | MOCK-SDK. **Not live Anthropic evidence.** | COMPLETE (live deferred) |
| M5-R04 | Mem0 | `src/memory/mem0_adapter.py` `Mem0MemoryAdapter`; `app.py` `build_genuine_mem0` (real `mem0.Memory.from_config`, offline preconditions enforced) | `test_mem0_adapter.py` (20, contract); `test_app_genuine_mem0.py` (8; 4 genuine tests run only in the offline overlay); Story 5 run (`story-05-mem0-local-evidence.txt`); Story 10 repair run (`story-10-mem0-repair-report.md`) | MEM0-LOCAL + STAND-IN. **Not Mem0 cloud evidence.** | COMPLETE (see note 3) |

### Deliverables

| ID | Requirement | Implementation | Verification evidence | Class | Status |
| --- | --- | --- | --- | --- | --- |
| M5-D01 | Autonomous AI agent | `run_agent` with dynamic selection, validated execution, memory context and explicit termination; UI Autonomous Agent area | `test_runner.py` (7); `test_app.py` agent-area tests; Story 11 Streamlit smoke run | DET, UI | COMPLETE |
| M5-D02 | Stateful workflow system | `AgentRunState` + lifecycle + memory components; UI workflow-state snapshot and Memory area | `test_models.py`, `test_lifecycle.py`, `test_memory.py`; `test_app.py::test_agent_area_records_runs_into_memory_area` | DET, UI | COMPLETE |

**Result: 30/30 source requirements have implementation and verification
evidence.** Topics 20/20, labs 4/4, required tools 4/4, deliverables 2/2.

## Cross-cutting checks

| Check | Result | Evidence |
| --- | --- | --- |
| UI exists and is runnable | PASS | `app.py`; Story 11 Streamlit smoke run (`VERIFICATION.md`) |
| UI has do / expect / proves guidance | PASS | `test_app.py::test_every_area_has_do_expect_proves_guidance` |
| UI does not claim live provider verification | PASS | `test_app.py::test_evidence_labels_never_claim_live_verification` |
| Zero-key startup, no automatic provider calls | PASS | `test_app.py::test_app_starts_without_credentials_or_provider_clients`; netguard runs record 0 non-loopback attempts |
| Module isolation | PASS | `test_app.py::test_app_and_tests_import_no_other_academic_module` (AST); Story 11 grep of `module-05/` for Module 1-4 package names finds only that test's deny-list |
| Evidence honesty | PASS | Classes above; `VERIFICATION.md` evidence-classification section |

## Notes

1. **Where memory meets the agent.** `run_agent` itself does not read or write
   memory. Loading memory into `AgentRunState` before a run and recording the
   run afterwards is done by `app.py` `run_autonomous_agent`. This was accepted
   in Story 10. It is recorded here so the integration point is not mistaken
   for runner behaviour.
2. **Reliability is composed, not wired into the runner.** `run_with_retry`,
   `run_with_timeout` and `run_with_fallback` are standalone primitives used
   by the Reliability area. `run_agent` never enters `TIMED_OUT` and never
   writes `retry_count` or `fallback_history`; those state fields exist but
   stay at their defaults. When a proposed tool is denied or a tool raises,
   `run_agent` raises the typed error and leaves the lifecycle at the step
   where it stopped (for example `tool_selected` or `executing`) rather than
   moving to `FAILED`. Nothing is reported as success. The source requirements
   are met; the architecture's fuller integration (ARCHITECTURE.md sections 3,
   13 and 16) is only partly realised. See ARCHITECTURE.md section 28.
3. **Mem0 evidence boundaries.** Genuine Mem0 runs only in the cached Story 5
   uv overlay. `mem0` is not a declared dependency and is not in `.venv`; there
   the four genuine tests skip and the UI explains why. Story 5's genuine run
   had Mem0 telemetry on (see `VERIFICATION.md`).
