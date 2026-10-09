# Module 5 Story 9 — Anthropic Tool Use: Final Report

Date: 2026-10-08. Evidence class: deterministic + mocked-transport. No live Anthropic evidence.

## 1. STORY 9 STATUS

**COMPLETE**, pending independent acceptance review.

M5-R03 (Anthropic Tool Use) is implemented under the frozen architecture as
`providers/anthropic_tools.py` (the file named in ARCHITECTURE.md §4 and §10).
No architecture change, no dependency change, Story 10 not started.

## 2. SDK DISCOVERY

All discovery ran offline (`python -I`, socket `connect` patched to raise). No client was
constructed during discovery.

| Item | Locally discovered value |
| --- | --- |
| Python / SDK | CPython 3.12.14, `anthropic` 1.11.0 (pin `anthropic>=1.11.0`, unchanged) |
| Request API | `Anthropic.messages.create(*, max_tokens, messages, model, ..., tools, tool_choice, ...)` — `max_tokens` required |
| Tool input type | `anthropic.types.ToolParam` (TypedDict): required `name`, `input_schema` (`InputSchema`, `type: "object"`); optional `description`, `strict`, `type: "custom"`, `cache_control`, `allowed_callers`, `defer_loading`, `input_examples`, `eager_input_streaming` |
| Response type | `anthropic.types.Message`: `id, content, model, role, stop_reason, stop_sequence, usage, container, diagnostics, stop_details, type` |
| Stop reasons | `end_turn, max_tokens, stop_sequence, tool_use, pause_turn, refusal, model_context_window_exceeded` |
| Content blocks | discriminated union `ContentBlock` of 12 types incl. `TextBlock`, `ToolUseBlock`, `ThinkingBlock`, `ServerToolUseBlock`, server tool result blocks |
| Tool-use block | `ToolUseBlock`: `id, name, input: Dict[str, object], type, caller (DirectCaller \| ServerToolCaller \| ServerToolCaller20260120 \| None), toolset_name` |
| Continuation | Stateless: resend history. `MessageParam{role, content}`; result block `ToolResultBlockParam{type:"tool_result", tool_use_id, content: str \| blocks, is_error?}` |
| Transport | SDK 1.11.0 uses **`httpx2`** (`http_client: httpx2.Client`), not `httpx`. `httpx2` 2.13.1 is installed (root dev group) and provides `MockTransport` |
| Local typed construction | Yes: `ToolUseBlock(...)` constructs; `TypeAdapter(ToolParam).validate_python(...)` validates |
| Credential eligibility | `ANTHROPIC_API_KEY` present in process env: **No**. `RUN_LIVE_LLM_TESTS=1`: **No**. Root `.env` exists (git-ignored) and does not contain the name `ANTHROPIC_API_KEY` (name-only grep, no values read or printed). **Not eligible for live verification.** |

Key differences from OpenAI found locally: no `previous_response_id` (history is resent),
tool input arrives as an already-parsed object (not a JSON string), stop reasons are
explicit and include non-terminal/abnormal values, and tool-use blocks carry a `caller`.

## 3. IMPLEMENTATION CHANGES

New: `module-05/src/ai_agent_engineering/providers/anthropic_tools.py` (361 lines)
- `to_anthropic_tool`, `anthropic_tools(registry)` — registry-derived `{name, description, input_schema}`; `strict` deliberately not set (application validation is the authority; avoids an unverified provider schema-compatibility claim like Story 8's deferred `minLength` question).
- `normalize_tool_use_block` → `AnthropicToolUse(tool_use_id, name, arguments)`.
- `execute_anthropic_tool_use` → `registry.execute` only.
- `run_anthropic_tool_use(client, registry, *, model, user_input, max_tokens=1024, max_requests=4, max_tool_calls=8)` → `AnthropicToolUseResult(output_text, stop_reason, executed_calls, request_count)`.
- Caps: `MAX_ANTHROPIC_REQUESTS=10`, `MAX_ANTHROPIC_TOOL_CALLS=20`, `MAX_ANTHROPIC_OUTPUT_TOKENS=4096`.
- Errors: `AnthropicToolUseError(ValueError)`, `AnthropicToolLoopBudgetError(RuntimeError)`.

Modified (additive only): `providers/__init__.py` — exports the 12 new names. No lines removed.

New: `module-05/tests/test_anthropic_tools.py` — 38 tests.

Untouched: `openai_tools.py`, ToolRegistry, schemas, builtins, all Story 1–8 code and tests.

## 4. ANTHROPIC TOOL-USE EVIDENCE

- Schemas: all three registry tools convert; each validates against the installed SDK's `ToolParam` via pydantic `TypeAdapter`; calculator keeps `required` and `additionalProperties: false`.
- Normalization: a real `anthropic.types.ToolUseBlock` (with `caller={"type":"direct"}`) normalizes to the expected `AnthropicToolUse`.
- Request serialization and response parsing are done by a real `anthropic.Anthropic` client; only the HTTP transport is an `httpx2.MockTransport` (`https://anthropic-mock.invalid/v1/messages`).

## 5. REQUEST-LOOP EVIDENCE

Asserted on the exact JSON bodies the SDK sent:
- Request 1: `{model, max_tokens: 1024, messages: [{role:user, content:goal}], tools: anthropic_tools(registry)}`.
- Request 2: history = user goal → assistant turn rebuilt from normalized data (`text` + `tool_use{id,name,input}`) → user turn of `tool_result{tool_use_id, content: json.dumps(result)}`.
- Multi-step: 3 requests (message lengths 1, 3, 5), two calculator executions, terminal text `"50"`, `stop_reason="end_turn"`.
- Parallel tool use: two blocks in one message produce two `tool_result` blocks in order.
- Termination: terminal only on `end_turn`/`stop_sequence`; `tool_use` continues; every other stop reason fails closed. Endless `tool_use` stops at exactly `max_requests` (3) with `AnthropicToolLoopBudgetError`. A batch exceeding `max_tool_calls` is refused before any execution. Invalid budgets (0, over cap, `bool`) are rejected before any request.

## 6. SECURITY / AUTHORITY EVIDENCE

All denials below assert zero tool executions (registry spy) and no extra request.
- Invented tool `shell` → `UnknownToolError`; allowlist unchanged.
- Injected extra argument (`command`) in the 2nd block of a batch → `ToolValidationError` before the 1st valid block runs (whole batch pre-validated).
- Schema-invalid arguments (`operation:"power"`, string `right`) → `ToolValidationError`.
- Non-object input, missing/empty id or name, duplicate `tool_use` ids → `AnthropicToolUseError`.
- Non-direct `caller` (server/code-execution) → denied.
- Unrequested `server_tool_use` / any non-`text`/`tool_use` block → denied.
- Inconsistent stops (`tool_use` without blocks; `end_turn` with tool blocks; `max_tokens`, `refusal`, `pause_turn`) → denied.
- Continuation echoes only normalized, validated fields; raw provider blocks are never forwarded.
- The function never creates a client or reads credentials; the credential grants provider access only.

## 7. REPAIR LOG

No failures in Ruff, pytest, or compileall. **0 semantic repairs, 0 Ruff fixes.**

Not a gate failure, recorded for transparency: my first ad-hoc network-guard harness
(evidence tooling in the scratchpad, not project code) also blocked loopback, which broke
asyncio's Windows self-pipe in `test_timeout.py` (3 errors). I narrowed the guard to allow
loopback only and reran: 186 passed, 0 non-loopback attempts. No project file changed.

## 8. QUALITY GATES

Fail-fast order, from repo root using `.venv`:
1. `ruff check module-05` — **PASS** ("All checks passed!")
2. `PYTHONPATH=module-05/src python -m pytest module-05/tests -q -p no:cacheprovider` — **PASS: 186 passed / 0 failed** (148 baseline + 38 new; baseline re-confirmed at 148 before changes)
3. `python -m compileall -q module-05/src module-05/tests` — **PASS** (exit 0)

## 9. LIVE / PAID CALL STATUS

- **0 live Anthropic calls. 0 paid Anthropic calls.**
- Full suite rerun with non-loopback `socket.connect`/`connect_ex`/`getaddrinfo` blocked: 186 passed, **0 non-loopback network attempts**.
- Live verification not eligible (no credential, no `RUN_LIVE_LLM_TESTS=1`). No live test was added, consistent with Story 8.
- Evidence classification: mocked-transport/local, **not** live Anthropic evidence.

## 10. MODULE ISOLATION

**PASS.** Changes are confined to `module-05/`. `git diff --stat` on tracked files is empty
(Modules 1–4 and root files unmodified). The new module imports only stdlib and
`ai_agent_engineering.tools`; tests import `anthropic`, `httpx2`, `pydantic`, `pytest`.
No commit, push or tag (HEAD still `9111fcc`).

## 11. DEFINITION OF DONE

- [x] authoritative source inspected
- [x] frozen architecture inspected
- [x] installed Anthropic SDK inspected
- [x] Anthropic tool schemas generated correctly
- [x] request path implemented
- [x] real local SDK types/contracts exercised
- [x] Anthropic tool-use response normalized
- [x] tool execution only through ToolRegistry
- [x] tool result continuation implemented
- [x] bounded terminal continuation demonstrated
- [x] invented tools denied
- [x] malformed/injected arguments denied
- [x] provider output cannot expand authority
- [x] normal verification makes zero live calls
- [x] normal verification makes zero paid calls
- [x] Ruff PASS
- [x] pytest PASS — 186 passed
- [x] compileall PASS
- [x] Module isolation PASS
- [x] accepted Stories 1–8 remain green
- [x] no commit/push/tag
- [x] Story 10 not started

## 12. NEXT RECOMMENDED ACTION

Run an independent acceptance review of Story 9 before starting Story 10.

Notes for the reviewer:
- **Rule 44 refactor opportunity (reported, not done):** `_bounded_budget`, the model/input
  checks, the "pre-validate whole batch, then execute via registry" step, and the result
  dataclass shape are now duplicated across `openai_tools.py` and `anthropic_tools.py`.
  A small shared helper (e.g. a `validate_then_execute_batch(registry, calls)`) is the
  evident abstraction. Normalization and continuation differ genuinely and should stay
  provider-specific.
- **Deferred live evidence:** whether live Anthropic accepts these schemas (including
  `minLength`) and real `stop_reason` behavior can only be settled by an approved live call.
  If approved later, the proposed call is one `run_anthropic_tool_use` with the default
  registry, goal "What is 6 times 7?", `max_requests=2`, `max_tokens=256`: at most 2 requests,
  roughly 2–3k input tokens and ≤512 output tokens in total. Exact cost depends on the model
  chosen and should be priced at approval time (not verified here).
- **Design choice to confirm:** tool handler exceptions propagate (fail closed) rather than
  being returned to the model as `is_error` tool results, matching Story 8.
