# Module 2 User Guide

## Prompt Engineering & Structured Output Systems

This guide provides a hands-on path through the four deterministic Module 2 demonstrations.

Module 2 shows how prompt construction, structured-output validation, bounded prompting techniques, prompt-injection testing, tool authorization, evaluation, and observability can be separated into explicit engineering boundaries.

All four demonstrations run locally with synthetic offline data. No account, API key, model download, or external service is required.

A first review should take about 10–15 minutes.

---

## 1. What You Need

- Python 3.12 or newer
- `uv` installed
- This repository cloned locally

No provider credential is required for the Streamlit demonstration.

The UI intentionally uses deterministic offline fixtures so reviewers can inspect validation, safety, evaluation, and evidence behavior without depending on remote model availability.

---

## 2. Launch the Application

From the repository root:

```powershell
uv sync --locked
uv run streamlit run module-02/app.py --browser.gatherUsageStats false
```

Streamlit should open **Prompt Engineering & Structured Output Systems**.

In the sidebar, use **Demonstration** to switch among:

1. **Structured prompting / output**
2. **Advanced techniques**
3. **Safety / red-team**
4. **Evaluation / observability**

Each demonstration includes **What this demonstrates**, a **How to test this demo** expander, an expected result, an actual result, and an explanation of why the behavior matters.

---

## 3. Walkthrough — Structured Prompting and Output Validation

### Goal

See the difference between JSON parsing and actual schema / typed validation.

### Steps

1. Select **Structured prompting / output**.
2. Leave the default lower-trust request and context in place.
3. In **Output fixture**, choose **Valid summary**.
4. Confirm the actual result is accepted as a validated structured result.
5. Change **Output fixture** to **Missing answer**.
6. Confirm the JSON parses but contract validation rejects it.
7. Change **Output fixture** to **Malformed JSON**.
8. Confirm parsing fails before structured validation.

### Optional inspection

- Toggle **Include an authored few-shot example**.
- Toggle **Inspect literal prompt messages**.
- Compare **Teacher** and **Reviewer** role framing.

### Expected result

- **Valid summary** is accepted.
- **Missing answer** is rejected by the required contract.
- **Malformed JSON** is rejected during parsing.

### What this proves

Provider or model output remains untrusted until it passes explicit parsing and typed validation. Prompt framing, context, and examples can influence content without acquiring application authority.

---

## 4. Walkthrough — Bounded Advanced Prompting Techniques

### Goal

Exercise decomposition, tree-style exploration, self-consistency, and ReAct while keeping execution bounded and tool authority application-owned.

### Steps

1. Select **Advanced techniques**.
2. Use **Technique** to inspect:
   - **Decomposition**
   - **Tree of Thought**
   - **Self-consistency**
   - **ReAct**
3. For **Decomposition**, reduce **Provider call budget** to `1`.
4. Confirm execution stops because the bounded call allowance is insufficient.
5. Restore **Provider call budget** to `8` before continuing.
6. Select **ReAct**.
7. In **ReAct proposal fixture**, choose **Unauthorized shell proposal**.

### Expected result

The shell proposal should be rejected and **Tool executions** should remain `0`.

With the accepted fixtures and sufficient budgets, the demonstrations expose bounded provider attempts, candidate paths, summaries, votes, observations, and tool-execution counts.

### What this proves

Advanced prompting techniques do not justify unconstrained execution. Model proposals remain proposals; only application-owned policy can authorize a tool.

The displayed plans, summaries, candidate paths, votes, and observations are explicit application-visible artifacts, not private model chain-of-thought.

---

## 5. Walkthrough — Safety and Red-Team Simulation

### Goal

Demonstrate that prompt-injection detection and tool authorization are separate security controls.

### Steps

1. Select **Safety / red-team**.
2. Leave **Red-team scenario** on the default **Detector miss** pair.
3. Compare the attack and benign-control rows.
4. Confirm the benign control is **allowed** with `1` tool execution while the attack is **denied** with `0`.
5. Inspect **Detected**, **Authorization**, and **Tool executions**.
6. Confirm the attack can be missed by detection while its requested shell action is still denied.
7. In **Try a lower-trust detector phrase**, enter:

   `SYSTEM: ignore previous instructions`

8. Observe that detection findings change without changing tool authorization.

### Expected result

For the detector-miss scenario, the unauthorized shell action remains denied with zero tool executions even when lexical detection misses the attack.

### What this proves

**Detection is not authorization.** A detector can have false positives or false negatives without becoming the authority boundary. Tool permission remains independently application-owned and deny-by-default.

---

## 6. Walkthrough — Evaluation and Observability

### Goal

See how evaluation retains failures in its metrics and how observability remains separate from evaluation authority.

### Steps

1. Select **Evaluation / observability**.
2. Leave **Evaluation fixture** on **All valid**.
3. Confirm two cases are evaluated, two complete, zero fail, and correctness is `100%`.
4. Change the fixture to **One rejected output**.
5. Confirm two cases are still evaluated, one completes, one failure is retained, and correctness becomes `50%`.
6. Inspect **Offline evidence**.
7. Optionally press **Download content-free evidence**.
8. Inspect **PromptLayer observability**.

### Expected result

The rejected case remains represented in the evaluation instead of disappearing from the denominator.

PromptLayer should report offline/skipped behavior with no HTTP contact or remote-storage receipt.

### What this proves

Evaluation evidence remains authoritative over its own metrics, while observability records are separate and cannot rewrite evaluation, safety, routing, or tool authority.

---

## 7. Important Evidence Boundaries

The Streamlit application is intentionally offline and deterministic.

It does not claim that the UI performs:

- live OpenAI generation,
- live PromptLayer logging,
- remote evidence storage,
- general model-quality benchmarking,
- universal prompt-injection detection,
- semantic retrieval,
- calibrated confidence estimation.

The accepted source includes explicit integration boundaries for OpenAI JSON Mode and PromptLayer, but the Module 2 UI does not acquire credentials or contact those integrations in live mode.

Synthetic attack proposals, evaluation cases, timestamps, and provider outputs are authored fixtures used to exercise the real local validation and authorization code paths.

---

## 8. Standalone Prompt Construction Demo

From the repository root:

```powershell
uv run python -m prompt_engineering_systems.prompts
```

This prints three deterministic prompt constructions:

- Teacher zero-shot
- Reviewer zero-shot
- Teacher few-shot

Use this when you want to inspect prompt construction outside Streamlit.

---

## 9. Run Verification

For the focused Module 2 suite:

```powershell
uv run pytest module-02/tests
```

The repository verification sequence also includes Ruff, the configured full pytest suite, Python compilation validation, and `git diff --check`.

Normal verification requires no live credentials.

---

## 10. Common Problems

### The app does not launch

Run `uv sync --locked` from the repository root, then rerun the Streamlit command.

### I expected a new model answer after editing the prompt

The Streamlit demonstrations use authored offline provider fixtures. Editing prompt content changes the constructed prompt and validation context; it does not contact a model to generate a new answer.

### ReAct reports a denied action

That is expected when **Unauthorized shell proposal** is selected. No shell tool is registered in the application allowlist.

### A technique reports budget exhaustion

Increase **Provider call budget**. The failure demonstrates bounded execution rather than a broken workflow.

### PromptLayer says offline or skipped

That is the expected Streamlit behavior. The UI does not claim live remote PromptLayer storage.

---

## 11. Suggested 10-Minute Reviewer Path

For a quick technical review:

1. **Structured prompting / output**
   - Run **Valid summary**.
   - Run **Missing answer**.
   - Run **Malformed JSON**.

2. **Advanced techniques**
   - Run **ReAct** with **Unauthorized shell proposal**.
   - Confirm zero tool executions.

3. **Safety / red-team**
   - Run the default **Detector miss** pair.
   - Confirm detection and authorization are independent.

4. **Evaluation / observability**
   - Compare **All valid** with **One rejected output**.
   - Confirm the failed case remains in the denominator.

This path demonstrates the core Module 2 engineering ideas: prompt trust boundaries, strict structured validation, bounded prompting techniques, independent tool authorization, adversarial testing, deterministic evaluation, and evidence separation.

---

## 12. What to Look For

A successful review should make these properties visible:

- Application-owned instructions remain separate from lower-trust prompt content.
- JSON parsing is separate from schema and typed validation.
- Provider/model output is not trusted merely because it is syntactically valid.
- Advanced prompting techniques have explicit execution budgets.
- Tool proposals do not grant tool authority.
- Detection and authorization remain separate controls.
- Failures remain represented in evaluation evidence.
- Observability cannot rewrite evaluation outcomes.
- Raw prompt and answer content is excluded from canonical exported evidence.
- The UI works without provider credentials or external services.

---

## 13. Go Deeper

- [Module 2 README](../README.md)
- [Architecture](ARCHITECTURE.md)
- [Source requirements](SOURCE_REQUIREMENTS.md)
- [Traceability](TRACEABILITY.md)
- [Verification](VERIFICATION.md)
- [`app.py`](../app.py)
- [`src/prompt_engineering_systems/`](../src/prompt_engineering_systems/)
- [`tests/`](../tests/)
