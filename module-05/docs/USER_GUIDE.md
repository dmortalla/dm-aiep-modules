# Module 5 Streamlit User Guide

## AI Agent Engineering — Hands-On Demonstration

This guide provides a practical reviewer path through the Module 5 Streamlit application.

Module 5 demonstrates a stateful, bounded, tool-using agent with three memory layers, application-owned tool authority, provider integrations, reliability controls, and explicit evidence boundaries.

The application has four interactive areas:

1. Autonomous Agent
2. Memory
3. Tool Integrations
4. Reliability

A focused first review takes about 10–15 minutes.

The ordinary reviewer path starts with no API keys and no provider cost. OpenAI and Anthropic live execution are available only through separate, explicitly authorized, potentially billable actions.

---

## 1. What You Need

For the ordinary zero-key reviewer path:

- Python 3.12
- this repository
- the project virtual environment or an equivalent environment with the declared dependencies

No OpenAI or Anthropic API key is required to start or review the deterministic demonstrations.

Optional capabilities:

- **OpenAI LIVE** — requires your own explicitly authorized OpenAI API key
- **Anthropic LIVE** — requires your own explicitly authorized Anthropic API key
- **Genuine local Mem0** — requires the separately documented offline Mem0 launch environment

The default public demonstration remains usable without any credential.

---

## 2. Launch the Application

### Public deployed application

Open:

https://dm-aiep-module-05.streamlit.app/

### Local zero-key launch

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m streamlit run module-05/app.py
```

The page should open with four tabs:

- **Autonomous Agent**
- **Memory**
- **Tool Integrations**
- **Reliability**

The application starts in a zero-key state.

Entering a provider credential alone does not make a provider request. Live execution occurs only after a separate explicitly labelled LIVE action.

---

## 3. Understand the Evidence Labels

The application intentionally separates evidence classes.

### Deterministic

Accepted Module 5 code runs locally with deterministic demonstration inputs.

### LangChain

The genuine LangChain `create_agent` runtime is exercised with a local scripted chat model.

No remote LLM is called in this path.

### Mocked transport

The genuine OpenAI or Anthropic SDK serializes requests and parses responses through an in-process mocked transport.

This is genuine SDK-boundary evidence, but it is **not** live provider evidence.

### Mem0 stand-in

The accepted `Mem0MemoryAdapter` runs over a local in-process stand-in backend.

This exercises the adapter contract but is **not** evidence of the Mem0 library itself.

### Genuine local Mem0

The real `mem0` library runs locally behind the accepted adapter using:

- local Qdrant
- a cached Hugging Face embedder
- a local fake LangChain LLM
- telemetry disabled
- Hugging Face Hub offline mode

This is local Mem0 evidence, not Mem0 cloud evidence.

### LIVE provider evidence

OpenAI and Anthropic have explicit live paths.

A run counts as LIVE provider evidence only after the user:

1. supplies their own credential,
2. explicitly authorizes it for the current Streamlit session,
3. presses the separately labelled LIVE button,
4. and the bounded provider workflow succeeds.

The accepted production-grade upgrade recorded genuine successful OpenAI and Anthropic live verification under explicit human authorization.

---

# Walkthrough 1 — Run a Multi-Step Autonomous Agent

## Goal

Demonstrate a bounded Reason → Act → Observe execution loop in which the agent dynamically selects more than one application-approved tool.

## Steps

1. Open **Autonomous Agent**.
2. Select:

   **Multi-step: explain ReAct, then calculate 6 times 7**

3. Leave **Step budget** at `6`.
4. Leave **Use memory** enabled.
5. Press **Run agent**.
6. Inspect:
   - lifecycle trace
   - decision records
   - selected tools
   - observations
   - final result
   - full workflow state

## Expected result

The run should complete in approximately three agent steps.

Expected sequence:

1. `knowledge_lookup`
2. `calculator`
3. explicit finish decision

The calculation result should be:

`42.0`

## What this demonstrates

This exercises:

- `AgentRunState`
- the bounded agent runner
- `ToolRegistry`
- application-visible decision records
- dynamic tool selection
- schema validation
- terminal workflow state

The displayed decision records are application-visible action decisions, not private model chain-of-thought.

---

# Walkthrough 2 — Demonstrate Stateful Memory

## Goal

Show that information and previous runs can influence later workflow context without granting memory execution authority.

## Part A — Create an episode

1. Open **Autonomous Agent**.
2. Keep **Use memory** enabled.
3. Run the multi-step ReAct/calculator goal.
4. Open **Memory**.
5. Inspect:
   - short-term memory
   - episodic memory

The previous goal and run should now appear in session memory.

## Part B — Store a long-term fact

Under **Long-term memory**, enter:

**Key**

`preferred_demo`

**Fact**

`Use the multi-step ReAct demonstration when explaining this agent.`

Press **Remember fact**.

Run another agent goal with memory enabled and inspect the workflow state's retrieved memory/context fields.

## Part C — Demonstrate episodic continuity

Run the same multi-step goal again with memory enabled.

Inspect the result and memory state for evidence that the workflow recognizes the prior episode.

## What this demonstrates

Module 5 separates:

- short-term session context
- long-term facts
- episodic records of prior runs

Recalled memory remains context only.

It does not:

- register tools
- alter the tool allowlist
- authorize execution
- expand provider authority

---

# Walkthrough 3 — Compare Tool-Calling Paths

## Goal

Show that LangChain, OpenAI Function Calling, and Anthropic Tool Use all operate behind the same application-owned `ToolRegistry` authority boundary.

## Part A — Deterministic / mocked demonstrations

1. Open **Tool Integrations**.
2. Select the multi-step ReAct/calculator goal.
3. Select **Well-behaved** provider proposal.
4. Run each demonstration:
   - **Run LangChain agent**
   - **Run OpenAI function calling**
   - **Run Anthropic tool use**
5. Inspect:
   - tool schemas sent
   - provider-specific request/response evidence
   - tools executed through `ToolRegistry`
   - final output

## Expected behavior

### LangChain

Uses the genuine LangChain `create_agent` runtime with a local scripted chat model.

### OpenAI deterministic demo

Uses the genuine OpenAI SDK with an in-process mocked transport.

### Anthropic deterministic demo

Uses the genuine Anthropic SDK with an in-process mocked transport.

All proposed tool calls return to the application-owned `ToolRegistry` before execution.

---

## Part B — Security demonstration

Select:

**Hostile: adds an invented 'shell' tool call**

Run the OpenAI and Anthropic deterministic demonstrations again.

## Expected behavior

The invented `shell` tool is rejected.

No shell tool exists in the allowlist, so no provider proposal gains execution authority merely because the provider returned it.

The hostile batch should be denied before unauthorized execution.

## What this demonstrates

Provider output is untrusted data.

Provider integration does not bypass:

- tool allowlisting
- JSON Schema validation
- application authorization
- execution budgets

---

# Walkthrough 4 — Optional OpenAI and Anthropic LIVE Execution

## Goal

Demonstrate the separately bounded live-provider paths without confusing them with the deterministic demonstrations.

## Important safety and cost boundary

These actions may consume provider quota and may incur cost.

Do not enter credentials you do not intend to use.

Credentials are:

- masked in the UI
- retained only in Streamlit session state
- not written to a project credential file
- not printed, logged, traced, or returned in tool output by the application

Entering a key alone does **not** make a provider request.

### Authorize a credential

1. Open **Tool Integrations**.
2. Expand **Manage live-provider API keys**.
3. Enter an OpenAI and/or Anthropic key.
4. Press **Authorize entered keys for this session**.
5. Confirm the selected provider reports that a session credential is authorized.

The entry field is then cleared so a second plaintext copy is not retained in widget state.

---

## OpenAI LIVE

1. Authorize an OpenAI credential.
2. Choose the desired goal.
3. Press **Run OpenAI LIVE - may incur cost**.

The application-owned live path uses:

- model: `gpt-5.6-terra`
- maximum provider requests: `3`
- maximum tool calls: `4`
- finite request timeout
- SDK retries disabled

## Expected result

On success, the result is labelled as LIVE OpenAI evidence.

Every proposed tool call still passes through `ToolRegistry`.

Live request bodies are intentionally not retained or displayed.

---

## Anthropic LIVE

1. Authorize an Anthropic credential.
2. Choose the desired goal.
3. Press **Run Anthropic LIVE - may incur cost**.

The application-owned live path uses:

- model: `claude-sonnet-5-5`
- maximum provider requests: `3`
- maximum tool calls: `4`
- maximum output tokens per request: `1024`
- finite request timeout
- SDK retries disabled

## Expected result

On success, the result is labelled as LIVE Anthropic evidence.

Every proposed tool call still passes through `ToolRegistry`.

Live request bodies are intentionally not retained or displayed.

---

## After live testing

Press:

**Clear all session credentials**

Then close the browser tab, especially on a shared computer.

Clearing the Streamlit session does not revoke the credential at the provider.

## What this demonstrates

Module 5 separates:

- deterministic provider demonstrations
- mocked SDK transport evidence
- explicit live provider execution

A credential does not itself grant tool authority, and a live provider cannot bypass the application-owned registry.

---

# Walkthrough 5 — Explore Reliability and Failure Handling

## Goal

See how the system behaves when operations fail, time out, exhaust budgets, or attempt unauthorized actions.

Open **Reliability** and run the scenarios individually.

## Recommended sequence

### 1. Retry recovers a transient fault

Expected:

**Recovered**

Demonstrates bounded retry of retryable failures.

### 2. Retry budget exhausted

Expected:

**Bounded failure**

Demonstrates that retry cannot continue indefinitely.

### 3. Operation within deadline

Expected:

**Success**

Provides the normal deadline comparison case.

### 4. Timeout enforced

Expected:

**Bounded failure**

Demonstrates a real cancelling deadline for the standalone awaitable timeout primitive.

### 5. Fallback after provider outage

Expected:

**Recovered**

Demonstrates explicit fallback behavior.

### 6. Execution budget exhausted

Expected:

**Bounded failure**

Demonstrates that the agent cannot run indefinitely when it never reaches a finish decision.

### 7. Unknown tool denied

Expected:

**Denied**

Demonstrates rejection of an invented `shell` tool before execution.

### 8. Injected argument denied

Expected:

**Denied**

Demonstrates JSON Schema enforcement against unexpected arguments.

### 9. Invalid call is not retried

Expected:

**Denied**

Validation/authorization failures are not treated as transient provider failures.

### 10. Tool failure fails closed

Expected:

**Bounded failure**

A runtime tool error such as division by zero is not converted into successful execution.

---

# Walkthrough 6 — Review Mem0 Boundaries

The Memory tab exposes two different Mem0-related paths.

## A. Mem0 adapter stand-in

The public/default path uses the real `Mem0MemoryAdapter` contract over a local in-process stand-in.

This path is deterministic and available without additional dependencies.

It is **not** evidence of the actual Mem0 library.

## B. Genuine local Mem0

The application also supports the actual Mem0 library through a separately constrained local-only launch.

From the repository root:

```powershell
$env:MEM0_TELEMETRY='False'; $env:HF_HUB_OFFLINE='1'; uv run --offline --no-sync --with mem0ai==2.2.1 streamlit run module-05/app.py --server.fileWatcherType none
```

Then:

1. Open **Memory**.
2. Press **Start genuine local Mem0**.
3. Add and recall a memory.

## Required safeguards

- `MEM0_TELEMETRY=False`
- `HF_HUB_OFFLINE=1`
- `uv --offline --no-sync`
- cached `mem0ai==2.2.1`

The application refuses to start genuine Mem0 if telemetry is on or the Hugging Face Hub is online.

## Genuine local configuration

Mem0 uses:

- local Qdrant
- cached `sentence-transformers/all-MiniLM-L6-v2`
- local fake LangChain LLM
- `infer=False` so memories are stored verbatim

## Important limitations

- `mem0ai` is not a declared project dependency.
- Genuine Mem0 relies on the cached overlay.
- If the cache is unavailable, the offline launch fails rather than downloading.
- Each genuine Mem0 start creates a temporary `module5-mem0-*` directory under `%TEMP%`.
- These temporary directories are not automatically removed at session end.
- This is not Mem0 cloud evidence.

---

# Suggested 10-Minute Reviewer Demo

For a quick evaluation:

1. **Autonomous Agent**
   - Run the ReAct + `6 x 7` goal.
   - Confirm `knowledge_lookup` and `calculator`.
   - Inspect workflow state.

2. **Memory**
   - Store one long-term fact.
   - Run the agent again with memory enabled.
   - Inspect short-term and episodic state.

3. **Tool Integrations**
   - Run one deterministic OpenAI or Anthropic demonstration.
   - Switch to the hostile proposal.
   - Confirm `shell` is rejected.

4. **Reliability**
   - Run **Retry recovers a transient fault**.
   - Run **Execution budget exhausted**.
   - Run **Unknown tool denied**.

5. **Optional live-provider review**
   - Only if you intentionally want a potentially billable provider call.
   - Authorize one provider credential.
   - Run the corresponding LIVE workflow.
   - Clear session credentials afterwards.

These demonstrations cover the central Module 5 ideas:

- bounded autonomous execution
- stateful memory
- provider/tool orchestration
- application-owned authority
- bounded recovery
- explicit live-provider authorization

---

# Security and Trust Boundaries

A reviewer should be able to verify all of the following:

- `ToolRegistry` is the sole tool-execution authority.
- Unknown tools are denied.
- Unexpected arguments are denied by schema validation.
- Provider output cannot register tools or alter the allowlist.
- Memory is context only and grants no authority.
- User, tool, memory, and provider text is treated as untrusted data.
- User-controlled text is rendered as plain text/code/JSON/dataframe rather than interpreted Markdown.
- The application contains no shell, eval, or arbitrary filesystem execution tool.
- Normal startup is zero-key.
- Provider credentials are session-only and explicitly authorized.
- Authorizing a key alone performs no provider request.
- Live-provider execution is a separate explicit action.
- Live request bodies are not retained or displayed.
- Provider exceptions are sanitized before presentation.
- Retry is bounded.
- Tool/validation failures are not retried as transient faults.
- Live SDK retries are disabled.
- Provider requests and tool calls are capped.
- Step budgets bound autonomous execution.

These controls establish the application's tested authority boundaries. They do not imply universal prompt-injection immunity, universal provider compatibility, or enterprise-wide security certification.

---

# Evidence and Claim Boundaries

## Source-complete release

The annotated tag:

`v0.5.0-module-5`

identifies the original source-complete Module 5 release.

That tag is immutable.

## Later production-grade upgrade

A later production-grade upgrade was published to `main` without moving the release tag.

It added:

- session-only credential authorization
- bounded OpenAI live execution
- bounded Anthropic live execution
- integrated retry and fallback behavior
- runtime state reconciliation
- deployment and production-control verification

Its documented verdict is production-ready **for the documented Streamlit deployment scope**.

The accepted upgrade includes genuine successful OpenAI and Anthropic live-provider verification under explicit human authorization.

## The public application does not claim

- enterprise-scale high availability
- multi-tenant production operations
- formal compliance certification
- unlimited provider/model compatibility
- Mem0 cloud verification
- guarantees outside the tested deployment and architecture boundary

---

# Run Verification

From the repository root:

```powershell
.\.venv\Scripts\ruff.exe check module-05
$env:PYTHONPATH='module-05/src'; .\.venv\Scripts\python.exe -m pytest module-05/tests -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m compileall -q module-05/app.py module-05/src module-05/tests
```

At the Story 11 release checkpoint:

- Ruff: PASS
- pytest: `224 passed, 4 skipped`
- compileall: PASS
- offline Mem0 overlay: `227 passed, 1 skipped`
- non-loopback network attempts: `0`

The later production-grade upgrade added its own verification and genuine live-provider evidence.

See:

- `docs/VERIFICATION.md`
- `docs/PRODUCTION_READINESS.md`

for authoritative gate and live-evidence details.

---

# Common Problems

## The application starts without live-provider buttons enabled

That is expected until a corresponding provider key is explicitly authorized in the current session.

## Entering an API key does not make a provider call

Correct. Authorization and provider execution are separate actions.

## The OpenAI or Anthropic LIVE button remains disabled

Authorize a nonblank credential for that provider first.

## A LIVE request fails

The UI reports a sanitized failure classification rather than raw provider exception text.

Check:

- credential validity
- provider quota/access
- model availability
- network connectivity

## The hostile `shell` proposal is rejected

That is expected and is one of the key security demonstrations.

## A validation error is not retried

That is intentional. Authorization and validation failures are not treated as transient connection faults.

## Genuine Mem0 does not start

Verify:

- `mem0ai==2.2.1` is already cached
- `MEM0_TELEMETRY=False`
- `HF_HUB_OFFLINE=1`
- the launch used `uv --offline --no-sync`

## Mem0 cloud does not appear

Correct. Module 5's accepted Mem0 evidence is local-only.

## Timeout is demonstrated in Reliability but not integrated into `run_agent`

That is intentional.

`run_with_timeout` is a standalone cancelling primitive for awaitable work. The synchronous decision-provider boundary in `run_agent` does not automatically replay ambiguous synchronous timeouts.

---

# What to Look For

A successful review should make these properties visible:

- the agent has a bounded lifecycle
- multi-step goals can invoke multiple tools
- tool execution is controlled by an application-owned allowlist
- arguments are validated before execution
- memory preserves context but grants no authority
- LangChain, OpenAI, and Anthropic integrations share the same authority boundary
- mocked-provider evidence is visibly distinct from LIVE provider evidence
- live-provider credentials require explicit session authorization
- live requests are bounded and potentially billable
- retry and fallback behavior are bounded
- standalone deadlines cancel slow awaitable work
- step budgets stop runaway autonomous execution
- unknown tools and injected arguments are denied
- failures are never presented as successful execution
- genuine local Mem0 is clearly separated from the adapter stand-in
- the public Streamlit deployment remains usable without any credential

Together, these behaviors demonstrate the two core Module 5 deliverables:

- Autonomous AI agent
- Stateful workflow system

---

# Go Deeper

- [Module 5 README](../README.md)
- [Source requirements](SOURCE_REQUIREMENTS.md)
- [Architecture](ARCHITECTURE.md)
- [Traceability](TRACEABILITY.md)
- [Verification](VERIFICATION.md)
- [Production readiness](PRODUCTION_READINESS.md)
- [`app.py`](../app.py)
- [`src/ai_agent_engineering/`](../src/ai_agent_engineering/)
- [`tests/`](../tests/)
