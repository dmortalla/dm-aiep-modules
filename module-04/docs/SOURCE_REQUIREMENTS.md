# Module 4 Source Requirements

## Source Authority

This document records the requirements extracted from the authoritative
AI Engineering Program Module 4 source supplied by the user, frozen at
repository baseline `fcd9c8eb446df57fe609e47d52700250c512b59e` on `main`.

The source material is authoritative. Implementation choices may extend these
requirements, but must not silently replace, omit, weaken, or reinterpret them.

Any necessary deviation requires explicit human approval. Eight such
deviations/implementation decisions were reviewed and approved by the human
prior to Story 1; they are recorded in full in
[ARCHITECTURE.md](ARCHITECTURE.md#approved-human-resolutions) and are
referenced here only by number where a requirement's evidence depends on one.

## Module Identity

**Module:** 4
**Title:** Advanced RAG & Evaluation Systems [3 Hours]

## Objective

Advance learners toward production-grade RAG architectures.

## Source Requirements

### Retrieval / Search

| ID | Requirement | Source basis | Required Evidence | Status |
| --- | --- | --- | --- | --- |
| M4-RET-01 | Implement BM25 lexical retrieval | "BM25" | Implementation + tests + runnable demonstration | Complete |
| M4-RET-02 | Exercise semantic retrieval as a hybrid-retrieval leg | "semantic retrieval" | Module 4-owned `semantic_retrieval.py` semantic leg (ChromaDB-backed) fused by `hybrid_retrieval` + tests. *Originally: reuse of [M3-RET-03]; superseded by the Rule 44 isolation amendment.* | Complete |
| M4-RET-03 | Implement hybrid search architecture (fusion) | "hybrid search architectures" | Implementation + tests + runnable demonstration | Complete |
| M4-RET-04 | Implement query reranking | "query reranking" | Implementation + tests + runnable demonstration | Complete |
| M4-RET-05 | Implement a cross-encoder reranking pipeline | "cross-encoder pipelines" | Implementation + tests (injected deterministic scorer); real model run opt-in (approved resolution 3) | Complete |

### Optimisation

| ID | Requirement | Source basis | Required Evidence | Status |
| --- | --- | --- | --- | --- |
| M4-OPT-01 | Implement context filtering | "Context filtering" | Implementation + tests + runnable demonstration | Complete |
| M4-OPT-02 | Implement latency optimisation / measurement | "latency & cost optimisation" | Implementation + tests + runnable demonstration | Complete |
| M4-OPT-03 | Implement cost optimisation / measurement | "latency & cost optimisation" | Implementation + tests; configurable/versioned pricing data, labeled estimate vs. actual usage (approved resolution 8) | Complete |
| M4-OPT-04 | Implement retrieval caching | "retrieval caching" | Implementation + tests; in-memory cache only (approved resolution 6) | Complete |
| M4-OPT-05 | Implement dynamic retrieval | "dynamic retrieval" | Implementation + tests; deterministic documented policy, identified as an implementation decision (approved resolution 5) | Complete |

### Evaluation (RAGAS)

| ID | Requirement | Source basis | Required Evidence | Status |
| --- | --- | --- | --- | --- |
| M4-EVAL-01 | Implement RAGAS faithfulness evaluation | "RAGAS: faithfulness evaluation" | Genuine `ragas` invocation + tests (injected deterministic judge); live judge opt-in (approved resolution 2) | Complete |
| M4-EVAL-02 | Implement RAGAS context precision | "context precision" | Genuine `ragas` invocation + tests (injected deterministic judge) | Complete |
| M4-EVAL-03 | Implement RAGAS relevance scoring | "relevance scoring" | Genuine `ragas` invocation + tests (injected deterministic judge) | Complete |

### Observability

| ID | Requirement | Source basis | Required Evidence | Status |
| --- | --- | --- | --- | --- |
| M4-OBS-01 | Implement LangSmith tracing | "LangSmith tracing" | Genuine SDK call + tests (offline mocked transport); live opt-in (approved resolution 4). *Live opt-in path: final approved limitation, Story 12 closeout amendment.* | Complete — approved limitation |
| M4-OBS-02 | Implement LangFuse monitoring | "LangFuse monitoring" | Genuine SDK call + tests (offline mocked transport); live opt-in (approved resolution 4). *Live opt-in path: final approved limitation, Story 12 closeout amendment.* | Complete — approved limitation |
| M4-OBS-03 | Implement latency tracking | "latency tracking" | Implementation + tests + runnable demonstration | Complete |
| M4-OBS-04 | Implement failure analysis | "failure analysis" | Implementation + tests + runnable demonstration | Complete |

## Hands-On Labs

| ID | Source Lab | Required Evidence | Status |
| --- | --- | --- | --- |
| M4-LAB-01 | Build hybrid RAG workflow | Runnable implementation + tests + UI demonstration | Complete |
| M4-LAB-02 | Evaluate RAG with RAGAS | Runnable implementation + tests + UI demonstration | Complete |
| M4-LAB-03 | Implement reranking systems | Runnable implementation + tests + UI demonstration | Complete |
| M4-LAB-04 | Trace workflows with LangSmith | Runnable implementation + tests + UI demonstration | Complete |

## Required Tools

The source explicitly identifies the following technologies. Their presence
must be demonstrated with implementation evidence rather than documentation
claims alone.

| ID | Tool | Required Evidence | Status |
| --- | --- | --- | --- |
| M4-TOOL-01 | RAGAS | Genuine metric computation + tests | Complete |
| M4-TOOL-02 | LangSmith | Genuine tracing call + tests | Complete |
| M4-TOOL-03 | LangFuse | Genuine monitoring call + tests | Complete |
| M4-TOOL-04 | ChromaDB | Module 4-owned `ChromaSemanticIndex` over a genuine local ephemeral Chroma collection as the hybrid semantic leg + tests. *Originally: reuse of [M3-TOOL-02]; superseded by the Rule 44 isolation amendment.* | Complete |
| M4-TOOL-05 | Pinecone | Module 4-owned `PineconeSemanticIndex` integration boundary using the installed Pinecone SDK types, verified offline with an injected client + tests; live service verification not yet performed. *Originally: reuse of [M3-TOOL-03]; superseded by the Rule 44 isolation amendment.* | Complete — approved limitation |

## Required Deliverables

| ID | Deliverable | Acceptance Evidence | Status |
| --- | --- | --- | --- |
| M4-DEL-01 | Production-grade RAG architecture | Runnable end-to-end implementation + tests + documentation | Complete |
| M4-DEL-02 | Evaluation dashboard | Runnable, genuinely functional implementation + tests | Complete |

## Portfolio Demonstration Requirement

This repository additionally requires each completed module to expose a
proper runnable user interface or demonstrable front end.

The Module 4 UI must explain what each major workflow demonstrates, how to
use or test it, what result to expect, and what the actual result
demonstrates. The evaluation dashboard must be genuinely functional rather
than documentation or a static screenshot.

The UI is an additive presentation layer and must not replace or distort the
source-required implementation.

| ID | Requirement | Required Evidence | Status |
| --- | --- | --- | --- |
| M4-PORT-01 | Runnable self-explanatory Module 4 demonstration UI, including a genuinely functional evaluation dashboard | UI contract tests + manual/live verification | Complete |

## Python Engineering Standards

All Module 4 Python implementation must:

1. Use Google-style docstrings for modules, classes, public functions, and
   public methods where appropriate.
2. Include `Args`, `Returns`, and `Raises` sections when applicable.
3. Use type hints throughout public interfaces.
4. Implement intentional exception handling at genuine failure boundaries.
5. Never silently swallow exceptions.
6. Produce specific and actionable domain errors.
7. Preserve causal context with exception chaining where appropriate.
8. Test expected failure paths.
9. Keep error handling at the correct architectural boundary.
10. Pass Ruff, pytest, and compilation gates before completion.

## Engineering Acceptance Rules

1. Every frozen source requirement requires appropriate evidence.
2. Passing quality gates alone does not prove source completeness.
3. Related functionality elsewhere does not automatically satisfy a requirement.
4. Source-specified technologies must be genuinely integrated, not merely
   documented.
5. Additive improvements must not replace source requirements.
6. Documents, retrieved content, metadata, provider output, judge-model
   output, and other external content are untrusted until validated.
7. Retrieved content, cached content, and model/judge output cannot acquire
   application or tool authority.
8. Normal deterministic tests must not require live credentials.
9. Tests and quality rules must not be weakened merely to obtain green status.
10. Source deviations require explicit human approval; the eight resolutions
    in [ARCHITECTURE.md](ARCHITECTURE.md#approved-human-resolutions) are the
    only approved deviations as of this freeze.
11. Completion requires both deterministic quality gates and complete
    source-to-evidence traceability.
12. Published Modules 1-3 must not be modified for Module 4's convenience.
13. Telemetry and trace payloads emitted to LangSmith/LangFuse must redact
    raw retrieved content and credentials by default.

## Definition of Done

- [x] BM25 lexical retrieval is implemented.
- [x] Hybrid search architecture (fusion) is implemented.
- [x] Query reranking is implemented.
- [x] Cross-encoder reranking pipeline is implemented.
- [x] Context filtering is implemented.
- [x] Latency optimisation/measurement is implemented.
- [x] Cost optimisation/measurement is implemented.
- [x] Retrieval caching is implemented.
- [x] Dynamic retrieval is implemented.
- [x] RAGAS faithfulness evaluation is implemented.
- [x] RAGAS context precision is implemented.
- [x] RAGAS relevance scoring is implemented.
- [x] LangSmith tracing is implemented.
- [x] LangFuse monitoring is implemented.
- [x] Latency tracking is implemented.
- [x] Failure analysis is implemented.
- [x] Hybrid RAG workflow lab is runnable.
- [x] RAGAS evaluation lab is runnable.
- [x] Reranking systems lab is runnable.
- [x] LangSmith tracing lab is runnable.
- [x] Production-grade RAG architecture deliverable is complete.
- [x] Evaluation dashboard deliverable is complete and genuinely functional.
- [x] Self-explanatory Streamlit UI demonstrates Module 4 functionality
  (automated UI contract evidence; the manual Streamlit verification in
  [VERIFICATION.md](VERIFICATION.md) is the final human checkpoint).
- [x] Automated tests cover required behavior and failure paths.
- [x] Repository quality gates pass in fail-fast order.
- [x] Source-to-evidence traceability has no unexplained gaps.
- [x] Human review confirms source faithfulness (final human checkpoint,
  together with the manual Streamlit verification).

**Story 1 status:** this document freezes the requirements above with all
statuses `Pending`. No requirement is implemented by Story 1.

## Amendment — 2026-10-07 (Rule 44 isolation remediation)

The human approved superseding every earlier mapping that satisfied a Module
4 requirement by reusing a Module 3 implementation. Module 4 is standalone
(Rule 44) and has no runtime dependency on Modules 1-3. The evidence column
for M4-RET-02, M4-TOOL-04, and M4-TOOL-05 above now names Module 4-owned
evidence, with the original mapping kept in italics. The requirements, their
source basis, and their statuses are unchanged. FAISS is not a Module 4
requirement and has been removed from Module 4. Full details are in
[ARCHITECTURE.md](ARCHITECTURE.md), in the Rule 44 isolation amendment.

## Amendment — 2026-10-08 (Story 12 closeout)

Story 12 replaced every `Pending` status above with the final status that
the evidence supports. Requirement wording, source basis, and the evidence
column are unchanged, except for the italic note on M4-OBS-01 and
M4-OBS-02. The per-requirement evidence is in
[TRACEABILITY.md](TRACEABILITY.md), and the gate and demo results are in
[VERIFICATION.md](VERIFICATION.md).

Final totals: 25 `Complete`; 3 `Complete — approved limitation` (M4-OBS-01,
M4-OBS-02, M4-TOOL-05); 1 `Complete — automated evidence; human manual
verification pending` (M4-PORT-01). No requirement is missing.

The human approved these final limitations at Story 12 review:

- **M4-OBS-01 / M4-OBS-02 (HITL-1).** The LangSmith and LangFuse SDK
  integrations are genuine and verified offline. The separate live opt-in
  path anticipated by approved resolution 4 was not built. Live remote
  delivery has not been verified and is outside the final Module 4 scope.
- **M4-TOOL-05 (HITL-3).** "Live service verification not yet performed" is
  the final Module 4 limitation. The Module 4-owned genuine Pinecone SDK
  boundary with deterministic offline verification satisfies Module 4
  scope.

The matching architecture record is the Story 12 closeout amendment in
[ARCHITECTURE.md](ARCHITECTURE.md).

## Amendment — 2026-10-08 (Module 4 release closeout)

The human recorded the final manual Streamlit verification as **PASS** on
2026-10-08 and approved the final Module 4 requirement state for release.
M4-PORT-01 is therefore `Complete`, and the final Definition-of-Done item
(human review of source faithfulness, together with the manual Streamlit
verification) is checked. The verification details are in
[VERIFICATION.md](VERIFICATION.md).

Final totals (29 IDs): 26 `Complete`; 3 `Complete — approved limitation`
(M4-OBS-01, M4-OBS-02, M4-TOOL-05); 0 Partial; 0 Missing. The Story 12
amendment above, which recorded M4-PORT-01 as pending human verification,
is kept as historical record. The approved limitations are unchanged.
