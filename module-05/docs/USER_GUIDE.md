# Module 5 Streamlit User Guide

## AI Agent Engineering — Hands-On Demonstration

This guide provides a practical tour of the Module 5 Streamlit application.
It is designed for reviewers, students, recruiters, and other users who want
to understand what the agent demonstrates without first reading the source
code.

The application has four interactive areas:

1. Autonomous Agent
2. Memory
3. Tool Integrations
4. Reliability

A good first visit takes about 10-15 minutes.

## Important Evidence Labels

The public demonstration intentionally does not make live or paid OpenAI or
Anthropic calls.

- Deterministic means accepted Module 5 code is executing locally with
  deterministic demonstration inputs.
- LangChain means the genuine LangChain create_agent runtime is exercised
  with a local scripted chat model.
- Mocked transport means the genuine OpenAI or Anthropic SDK serializes and
  parses requests and responses through an in-process mock transport.
- Mem0 stand-in means the real Mem0MemoryAdapter contract is exercised over a
  local stand-in backend. It is not the Mem0 library.
- Live providers are not verified by this public demonstration.

These distinctions are intentional so that the demonstration does not claim
evidence it has not produced.

---

# Walkthrough 1 — Run a Multi-Step Autonomous Agent

## Goal

Demonstrate a bounded Reason -> Act -> Observe execution loop in which the
agent dynamically selects more than one application-approved tool.

## Steps

1. Open the **Autonomous Agent** tab.
2. Select the preset goal:

   **Multi-step: explain ReAct, then calculate 6 times 7**

3. Leave **Step budget** at `6`.
4. Leave **Use memory** enabled.
5. Press **Run agent**.
6. Inspect the resulting lifecycle trace, decision records, selected tools,
   observations, result, and workflow state.

## Expected result

The run should complete in approximately three agent steps.

The agent should use:

1. `knowledge_lookup`
2. `calculator`
3. a finish decision

The calculation result should be `42.0`.

## What this demonstrates

This exercises the real Module 5 AgentRunState, bounded agent runner,
ToolRegistry, application-visible decision records, dynamic tool selection,
schema validation, and terminal workflow state.

The displayed decision records are application-visible execution decisions,
not private model chain-of-thought.

---

# Walkthrough 2 — Demonstrate Stateful Memory

## Goal

Show that information and previous agent runs can influence later workflow
context without giving memory execution authority.

## Part A — Create an episode

1. Open **Autonomous Agent**.
2. Keep **Use memory** enabled.
3. Run the multi-step ReAct/calculator goal from Walkthrough 1.
4. Open the **Memory** tab.
5. Inspect:
   - Short-term memory
   - Episodic memory

The previous goal and run should now be represented in the session memory.

## Part B — Store a long-term fact

In **Long-term memory**, enter:

**Key**

    preferred_demo

**Fact**

    Use the multi-step ReAct demonstration when explaining this agent.

Press **Remember fact**.

Run another agent goal with memory enabled and inspect the workflow state's
retrieved memory/context fields.

## Part C — Demonstrate episodic continuity

Run the same multi-step goal again with memory enabled.

Inspect the result and memory state for evidence that the workflow recognizes
the previous episode.

## What this demonstrates

Module 5 separates:

- short-term session context,
- long-term facts,
- episodic records of previous runs.

Recalled memory remains untrusted context. It does not register tools, modify
the tool allowlist, or grant execution authority.

---

# Walkthrough 3 — Compare the Three Tool-Calling Paths

## Goal

Show that LangChain, OpenAI Function Calling, and Anthropic Tool Use all
operate behind the same application-owned tool authority boundary.

## Steps

1. Open **Tool Integrations**.
2. Select the multi-step ReAct/calculator goal.
3. Select **Well-behaved provider proposal**.
4. Run each integration separately:

   - **Run LangChain agent**
   - **Run OpenAI function calling**
   - **Run Anthropic tool use**

5. Inspect the tool calls, outputs, execution counts, and provider-specific
   request/response evidence shown after each run.

## Expected behavior

The LangChain path uses the genuine LangChain `create_agent` runtime with a
local scripted chat model.

The OpenAI path uses the genuine OpenAI SDK with an in-process mocked
transport.

The Anthropic path uses the genuine Anthropic SDK with an in-process mocked
transport.

All proposed tool calls return to the application-owned ToolRegistry before
execution.

## Security demonstration

Now select:

**Hostile: adds an invented 'shell' tool call**

Run the OpenAI and Anthropic demonstrations again.

## Expected behavior

The invented `shell` tool should be rejected.

No shell tool exists in the application's allowlist, and no proposed provider
call gains execution authority merely because a provider returned it.

This is one of the most important security properties demonstrated by the
module.

---

# Walkthrough 4 — Explore Reliability and Failure Handling

## Goal

See how the system behaves when operations fail, time out, exhaust budgets,
or attempt unauthorized actions.

Open **Reliability** and run the scenarios individually.

## Recommended sequence

### 1. Retry recovers a transient fault

Expected classification:

**Recovered**

Demonstrates bounded retry of retryable failures.

### 2. Retry budget exhausted

Expected classification:

**Bounded failure**

Demonstrates that retries cannot continue indefinitely.

### 3. Operation within deadline

Expected classification:

**Success**

Provides the normal timeout-control comparison case.

### 4. Timeout enforced

Expected classification:

**Bounded failure**

Demonstrates a real cancelling deadline.

### 5. Fallback after provider outage

Expected classification:

**Recovered**

Demonstrates explicit fallback behavior.

### 6. Execution budget exhausted

Expected classification:

**Bounded failure**

Demonstrates that the agent cannot run indefinitely when it fails to reach a
finish decision.

### 7. Unknown tool denied

Expected classification:

**Denied**

Demonstrates rejection of an invented `shell` tool before execution.

### 8. Injected argument denied

Expected classification:

**Denied**

Demonstrates JSON Schema enforcement against unexpected tool arguments.

### 9. Invalid call is not retried

Expected classification:

**Denied**

Demonstrates that validation/authorization failures are not treated as
transient failures.

### 10. Tool failure fails closed

Expected classification:

**Bounded failure**

Demonstrates that a runtime tool failure such as division by zero is not
reported as successful execution.

---

# Suggested 10-Minute Reviewer Demo

For a quick evaluation of the project, use this sequence:

1. **Autonomous Agent**
   - Run the ReAct + `6 x 7` multi-step goal.
   - Confirm `knowledge_lookup` and `calculator`.
   - Inspect the workflow state.

2. **Memory**
   - Store one long-term fact.
   - Run the agent again with memory enabled.
   - Inspect short-term and episodic state.

3. **Tool Integrations**
   - Run one well-behaved OpenAI or Anthropic demonstration.
   - Switch to the hostile proposal.
   - Confirm that `shell` is rejected.

4. **Reliability**
   - Run **Retry recovers a transient fault**.
   - Run **Execution budget exhausted**.
   - Run **Unknown tool denied**.

Those four demonstrations cover the central Module 5 ideas: autonomous
execution, stateful memory, provider/tool orchestration, bounded recovery, and
application-owned authority.

---

# What the Public Demo Does Not Claim

The application is intentionally precise about its evidence.

It does not claim:

- live OpenAI verification,
- live Anthropic verification,
- paid provider execution,
- Mem0 cloud verification,
- production deployment architecture.

The public Streamlit application is the presentation layer for the accepted
Module 5 implementation.

The OpenAI and Anthropic demonstrations exercise genuine SDK boundaries using
mocked transports. The LangChain demonstration uses the genuine LangChain
agent runtime with a local scripted model.

The public Memory tab also includes a deterministic Mem0 adapter stand-in.
Genuine local Mem0 requires the separately documented offline development
environment and is not expected to run from the public Streamlit deployment.

---

# What to Look For

A successful review should make these properties visible:

- The agent has a bounded lifecycle.
- Multi-step goals can invoke multiple tools.
- Tool execution is controlled by an application-owned allowlist.
- Tool arguments are validated before execution.
- Memory preserves context but grants no authority.
- LangChain, OpenAI, and Anthropic integrations share the same authority
  boundary.
- Retry and fallback behavior is bounded.
- Timeouts stop slow operations.
- Step budgets stop runaway execution.
- Unknown tools and injected arguments are denied.
- Failures are never presented as successful execution.

Together, these behaviors demonstrate the two Module 5 deliverables:

- Autonomous AI agent
- Stateful workflow system
