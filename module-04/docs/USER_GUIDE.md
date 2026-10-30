# Module 4 User Guide

## Advanced RAG & Evaluation Systems

This guide provides a hands-on reviewer path through the Module 4 hybrid RAG operations and evaluation dashboard.

Module 4 extends RAG into a measurable system: BM25 and ChromaDB retrieval, Reciprocal Rank Fusion (RRF), reranking, context filtering, retrieval caching, latency and cost telemetry, RAGAS evaluation, LangSmith tracing, LangFuse monitoring, and failure analysis are all exposed as reviewer-visible evidence.

The default dashboard path is fully deterministic and offline. It requires no credentials, API keys, network access, or LLM. The optional cross-encoder path may download a model from Hugging Face and run it locally.

A focused first review should take about 15–20 minutes.

---

## 1. What You Need

- Python 3.12 or newer
- `uv` installed
- This repository cloned locally

No provider credentials are required for the normal reviewer path.

The default dashboard uses:

- Module 4 BM25 retrieval
- genuine local ephemeral ChromaDB
- deterministic local hash embeddings
- deterministic overlap reranking
- extractive generation
- genuine RAGAS execution over fixed replay judgments
- genuine LangSmith and LangFuse SDK serialization into sealed offline transports
- measured local latency
- estimated cost using fixture pricing

Optional:

- a genuine sentence-transformers cross-encoder can be enabled from the sidebar
- enabling it may download a model from Hugging Face and increase startup and reranking latency

---

## 2. Launch the Dashboard

From the repository root:

```powershell
uv sync --locked
uv run streamlit run module-04/app.py --browser.gatherUsageStats false
```

Streamlit should open **Module 4 RAG Operations & Evaluation Dashboard**.

The page initially shows:

- **About this dashboard**
- **Evidence labels**
- **Trust, security, and truthfulness boundaries**
- sidebar controls
- a prompt to choose a scenario and press **Run workflow**

The default path is offline and credential-free.

---

## 3. Understand the Evidence Labels First

Before running a scenario, open **Evidence labels**.

The dashboard uses these classifications:

- **Deterministic / offline** — genuine library code running locally with reproducible inputs
- **Measured** — observed during the current run
- **Estimate** — calculated from a documented heuristic
- **Fixture data** — fixed, human-authored test data
- **Genuine local model (opt-in)** — the real cross-encoder downloaded and run locally
- **Not evaluated** — the dashboard cannot truthfully produce that value for the current run
- **Unavailable** — a capability exists but is not exercised in the dashboard

### What this proves

Evidence is explicitly classified instead of being presented as if all outputs came from live providers or learned models.

---

## 4. Run the Default Hybrid RAG Workflow

### Goal

Exercise the complete accepted Module 4 workflow.

### Steps

1. Keep the default curated scenario selected.
2. Leave **Use the genuine cross-encoder** unchecked.
3. Leave **Use retrieval cache** enabled.
4. Leave **Fault injection** set to **None**.
5. Press **Run workflow**.

### Expected result

A completed run should display:

1. Answer and citations
2. Dynamic retrieval
3. BM25 versus semantic retrieval fused by RRF
4. Reranking
5. Context filtering
6. Retrieval cache
7. Latency
8. Cost
9. RAGAS evaluation
10. LangSmith tracing
11. LangFuse monitoring
12. Failure analysis

An **Evidence provenance** table appears above the detailed sections.

### What this proves

The dashboard is a presentation/orchestration consumer over the accepted Module 4 package. The result is not reconstructed independently in the UI.

---

## 5. Inspect Answer Grounding and Citations

### Goal

Verify that the answer is traceable to retained evidence.

### Steps

1. In **1. Answer and citations**, inspect the generated answer.
2. Inspect the citation table.
3. Follow each citation through chunk ID, document ID, source ID, filter order, rerank rank and score, hybrid rank, RRF score, BM25 rank, semantic rank, and retained passage.

### Expected result

Each citation resolves to retained evidence with its retrieval history.

The generator is extractive and the page explicitly identifies it as **not a language model**.

### What this proves

Grounding remains auditable from the final answer back through filtering, reranking, fusion, and retrieval.

---

## 6. Inspect Dynamic Retrieval

### Goal

See how retrieval breadth changes through a deterministic application policy.

### Steps

1. Inspect **2. Dynamic retrieval**.
2. Note the branch, query term count, selected `top_k`, and policy values.
3. Compare the short **rockets** scenario with one of the longer curated scenarios.

### Expected result

Short queries take the documented short-query retrieval branch.

### What this proves

Retrieval breadth adapts to the query using application-owned policy. Retrieved text does not choose the retrieval policy.

---

## 7. Inspect BM25 + Semantic Retrieval and RRF

### Goal

Compare lexical and semantic retrieval legs and their fusion.

### Steps

1. Open **3. Retrieved evidence: BM25 versus semantic, fused by RRF**.
2. Inspect BM25 rank and score, semantic rank and score, RRF score, and which candidates came from both legs or only one.
3. Change **RRF constant k** and rerun.

### Expected result

The fused candidate ordering may change as the RRF constant changes.

RRF scores remain distinct from BM25 scores and cosine similarities.

### What this proves

Hybrid retrieval combines two ranking systems through a documented rank-fusion contract rather than pretending their raw score scales are directly comparable.

The semantic leg uses local hash embeddings based on token overlap, not learned semantic meaning.

---

## 8. Inspect Reranking and Context Filtering

### Goal

See how fused candidates are reordered and then bounded.

### Steps

1. Inspect **4. Reranking**.
2. Note `positions_moved_up`.
3. Inspect **5. Context filtering**.
4. Change **Minimum rerank score**.
5. Change **Maximum retained passages**.
6. Rerun.

### Expected result

Reranking changes ordering only.

Context filtering lists both retained and excluded candidates. Exclusions include explicit reasons.

### What this proves

Nothing is silently dropped, and passage text does not grant itself authority. Filtering decisions are based on scores and configured bounds.

---

## 9. Demonstrate Retrieval Caching

### Goal

Show a visible cache miss/hit lifecycle.

### Steps

1. Ensure **Use retrieval cache** is enabled.
2. Run a curated scenario once.
3. Note `from_cache=False`.
4. Press **Run workflow** again with the same settings.
5. Confirm `from_cache=True`.
6. Press **Clear retrieval cache**.
7. Run once more.

### Expected result

The second identical run should come from cache. After clearing the cache, the next run should be fresh.

### What this proves

The retrieval cache is actually used and reviewer-visible.

The dashboard does not claim hit-ratio, eviction, persistence, or TTL behavior that the in-memory cache does not implement.

---

## 10. Inspect Latency and Cost Evidence

### Latency

Open **7. Latency**.

The dashboard shows:

- measured per-stage timings
- measured total pipeline time
- illustrative one-second-per-stage demo budgets
- a stage latency chart

RAGAS and observability time are not part of this latency report.

### Cost

Open **8. Cost**.

The dashboard shows:

- estimated input/output token counts
- estimation convention
- fixture pricing identity
- estimated cost
- illustrative cost budget

### What this proves

Latency is measured on the current machine, while cost is explicitly an estimate.

The cost values are not provider billing and the token counts are not provider-reported usage.

---

## 11. Review RAGAS Evaluation

### Goal

Verify genuine RAGAS metric execution without overstating judge quality.

### Steps

1. Run a curated scenario with the default settings.
2. Inspect **9. RAGAS evaluation**.
3. Compare expected fixture scores with actual RAGAS scores for faithfulness, context precision, and response relevancy.
4. Inspect the fixed reference answer and replay judgments.

### Expected result

For an eligible curated scenario, actual RAGAS values should match the fixed expected values within the accepted tolerance.

### What this proves

RAGAS genuinely computes the metrics.

It does **not** prove semantic judge quality because the judge replays fixed human-authored verdicts and no provider-backed model judge is configured.

### Try an ineligible run

Choose **Custom query (RAGAS not evaluated)** and run it.

Expected result:

RAGAS is marked **Not evaluated** with a reason explaining that no fixed replay judgments apply.

---

## 12. Review LangSmith and LangFuse Evidence

### Goal

Inspect genuine SDK serialization while preserving the distinction from live remote delivery.

### LangSmith

Open **10. LangSmith tracing (offline)** and inspect success, SDK version, evidence kind, `remote_delivery_verified`, child run count, captured requests, serialized output fields, and the content-leak check.

### LangFuse

Open **11. LangFuse monitoring (offline)** and inspect success, SDK version, evidence kind, `remote_delivery_verified`, captured requests, and the content-leak check.

### Expected result

Both integrations should show offline SDK evidence with:

`remote_delivery_verified=False`

### What this proves

The genuine SDK boundaries and serialization paths are exercised.

It does **not** prove that any run was delivered to a hosted LangSmith or LangFuse service. No remote run URL or console state is claimed.

---

## 13. Exercise Failure Analysis

Module 4 distinguishes fatal workflow faults from nonfatal observability faults.

### A. Fatal reranking fault

1. Set **Fault injection** to **Demo fault: reranking stage failure**.
2. Press **Run workflow**.

Expected result:

- the workflow stops
- no answer is produced
- failure analysis identifies reranking
- `fatal=True`
- `result_usable=False`

### B. LangSmith transport fault

1. Set **Fault injection** to **Demo fault: LangSmith transport failure**.
2. Run again.

Expected result:

- the answer remains available
- LangSmith failure is reported
- `fatal=False`
- `result_usable=True`

### C. LangFuse transport fault

Repeat with **Demo fault: LangFuse transport failure**.

Expected result:

The answer remains available and the observability failure is classified without exposing raw exception text.

### What this proves

Observability integrations are optional dependencies. Their failure does not discard a valid RAG answer.

---

## 14. Test the Untrusted-Content Boundary

The built-in corpus deliberately contains an adversarial passage with an instruction to reveal an API key, Markdown image syntax, and an HTML `<script>` fragment.

### Steps

1. Run workflows that expose retrieved passages.
2. Inspect the adversarial content if retrieved.
3. Confirm that it appears only as plain text, code, or dataframe content.

### Expected result

The text remains inert.

It does not execute HTML or JavaScript, render Markdown-controlled external content, select providers, reveal credentials, or alter application policy.

### What this proves

Retrieved, generated, judge, provider, and custom-query content remain untrusted data at the presentation boundary.

---

## 15. Optional: Genuine Local Cross-Encoder

The sidebar includes:

**Use the genuine cross-encoder (may download a model)**

This is off by default.

### Steps

1. Enable the checkbox only if model download/network access is acceptable.
2. Run a scenario.
3. Inspect the reranker identity in **Evidence provenance** and **4. Reranking**.

### Expected result

The scorer should be identified as **Genuine cross-encoder (sentence-transformers)** with the evidence label **Genuine local model (opt-in)**.

### Important boundary

Cross-encoder logits are unbounded and may be negative, so the normal `0–1` minimum rerank threshold is disabled while this scorer is active.

The closeout evidence did not include this opt-in verification run, so do not treat its availability as historical release evidence unless you exercise it yourself.

---

## 16. Important Evidence and Security Boundaries

Keep these distinctions in mind:

- The default dashboard is deterministic and offline.
- No credential, environment variable, or secret is read by the dashboard.
- Retrieved text, generated text, judge text, provider data, and custom queries are untrusted data.
- Untrusted content is displayed through plain text, code, dataframe, or metric components, not interpreted Markdown/HTML.
- Exception text and tracebacks are not exposed in the UI.
- BM25 is a genuine local retrieval implementation.
- ChromaDB is a genuine local ephemeral semantic retrieval integration.
- Semantic embeddings use deterministic local token-overlap hashing, not learned semantic representations.
- Default reranking uses deterministic token overlap, not a learned model.
- The optional cross-encoder is a genuine local model path and may require download/network access.
- Generation is extractive rather than LLM-generated.
- Latency is measured locally.
- Cost is estimated from heuristic usage and fixture pricing, not vendor billing.
- RAGAS runs genuinely over fixed replay judgments.
- LangSmith and LangFuse integrations are genuine SDK paths exercised offline.
- `remote_delivery_verified=False` means hosted delivery is not established.
- Pinecone is not exercised by this dashboard and is displayed as unavailable here.
- Live Pinecone verification was not part of the accepted Module 4 closeout.
- Live hosted LangSmith/LangFuse verification was not part of the accepted Module 4 closeout.

---

## 17. Runnable Examples

A useful end-to-end starting point is:

```powershell
uv run python module-04/examples/hybrid_rag_workflow.py
```

The remaining examples cover BM25, hybrid retrieval, reranking, optimization, telemetry, RAGAS, LangSmith, and LangFuse.

The cross-encoder verification example is explicitly opt-in and may download a model.

---

## 18. Run Verification

For the focused Module 4 suite:

```powershell
uv run pytest module-04/tests
```

The accepted release process also used Ruff, Python compilation validation, module-isolation checks, example execution, `git diff --check`, and manual Streamlit verification.

The Story 12 closeout records **1844 passing tests across the full repository at that checkpoint**, not 1844 Module 4-only tests.

Three ChromaDB deprecation warnings were accepted at that checkpoint.

---

## 19. Common Problems

### The dashboard does not start

Run `uv sync --locked` from the repository root, then rerun the Streamlit command.

### RAGAS says Not evaluated

That can be correct for custom queries without fixed replay judgments, abstained answers, or runs whose answer/context no longer matches the curated fixture after settings changes.

### The second run is not from cache

Confirm that **Use retrieval cache** is enabled, the scenario and relevant settings have not changed, and the cache was not cleared between runs.

### Cost looks unrealistically small

The dashboard uses fixture pricing and estimated usage. It is not provider billing.

### LangSmith/LangFuse show success but no hosted run appears

That is expected. These are offline SDK serialization demonstrations. Remote delivery is not verified.

### Pinecone is unavailable

That is expected in this dashboard. Pinecone needs credentials and a live index and is not exercised by the dashboard.

### Cross-encoder startup is slow

The optional genuine model may need to download from Hugging Face and then load locally.

### A reranking fault removes the answer

That is expected. Reranking is part of the authoritative workflow and a fatal reranking failure prevents a valid result.

### A LangSmith/LangFuse fault keeps the answer

That is also expected. Observability failures are nonfatal.

---

## 20. Suggested 15-Minute Reviewer Path

1. **Read Evidence labels**
   - distinguish measured, estimated, fixture, offline, and optional-local evidence.

2. **Run the default curated scenario**
   - inspect answer and citations.

3. **Inspect hybrid retrieval**
   - compare BM25, semantic, and RRF ranks.

4. **Inspect reranking and context filtering**
   - see reorderings and explicit exclusions.

5. **Run the same scenario again**
   - confirm the retrieval cache hit.

6. **Inspect latency and cost**
   - distinguish measured latency from estimated cost.

7. **Inspect RAGAS**
   - compare expected fixture scores with actual RAGAS metrics.

8. **Inspect LangSmith and LangFuse**
   - confirm `remote_delivery_verified=False`.

9. **Inject a reranking fault**
   - confirm fatal failure and no answer.

10. **Inject an observability fault**
    - confirm the answer remains usable.

This path exercises the core Module 4 engineering claims without requiring credentials or remote services.

---

## 21. What to Look For

A successful review should make these properties visible:

- hybrid lexical + semantic retrieval is inspectable
- RRF fusion preserves per-leg ranking evidence
- reranking and filtering are separately visible
- exclusions are explicit rather than silent
- caching produces observable hit/miss behavior
- latency is measured rather than invented
- cost is explicitly estimated
- RAGAS execution is genuine while judge quality remains bounded by replay fixtures
- LangSmith and LangFuse SDK paths are real but remote delivery is not claimed
- failure handling distinguishes fatal pipeline failures from nonfatal observability failures
- adversarial retrieved content remains inert data
- evidence labels prevent fixtures and offline results from being mistaken for live-provider evidence
- the default reviewer path remains credential-free

---

## 22. Go Deeper

- [Module 4 README](../README.md)
- [Architecture](ARCHITECTURE.md)
- [Source requirements](SOURCE_REQUIREMENTS.md)
- [Traceability](TRACEABILITY.md)
- [Verification](VERIFICATION.md)
- [Story 12 closeout](STORY_12.md)
- [`app.py`](../app.py)
- [`examples/`](../examples/)
- [`src/advanced_rag_evaluation/`](../src/advanced_rag_evaluation/)
- [`tests/`](../tests/)
