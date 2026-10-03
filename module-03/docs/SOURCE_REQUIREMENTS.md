# Module 3 Source Requirements

## Source Authority

This document records the requirements extracted from the authoritative
AI Engineering Program Module 3 source supplied by the user.

The source material is authoritative. Implementation choices may extend these
requirements, but must not silently replace, omit, weaken, or reinterpret them.

Any necessary deviation requires explicit human approval.

## Module Identity

**Module:** 3  
**Title:** RAG Engineering Foundations

## Objective

Teach developers how to design scalable Retrieval-Augmented Generation systems.

## Source Requirements

### RAG Architecture and Retrieval Pipeline

| ID | Requirement | Required Evidence | Status |
| --- | --- | --- | --- |
| M3-RAG-01 | Demonstrate RAG architecture | Implementation + tests + runnable demonstration | Pending |
| M3-RAG-02 | Explain and demonstrate the knowledge-freshness problem addressed by RAG | Documentation + runnable demonstration | Pending |
| M3-RAG-03 | Implement a retrieval pipeline | Implementation + tests + runnable demonstration | Pending |
| M3-RAG-04 | Implement query transformation | Implementation + tests + runnable demonstration | Pending |

### Embeddings and Semantic Retrieval

| ID | Requirement | Required Evidence | Status |
| --- | --- | --- | --- |
| M3-RET-01 | Generate embeddings for retrieval | Implementation + tests | Pending |
| M3-RET-02 | Demonstrate vector similarity and distance metrics | Implementation + tests + runnable demonstration | Pending |
| M3-RET-03 | Implement semantic retrieval | Implementation + tests + runnable demonstration | Pending |
| M3-RET-04 | Demonstrate indexing strategies and approximate-nearest-neighbor concepts | Implementation/demonstration + tests where applicable | Pending |

### Vector Stores

| ID | Requirement | Required Evidence | Status |
| --- | --- | --- | --- |
| M3-VS-01 | Integrate FAISS for vector retrieval | Genuine runtime integration + tests | Pending |
| M3-VS-02 | Integrate ChromaDB for vector retrieval | Genuine runtime integration + tests | Pending |
| M3-VS-03 | Integrate Pinecone for vector retrieval | Genuine integration boundary + tests and/or live verification | Pending |

### Chunking and Context Engineering

| ID | Requirement | Required Evidence | Status |
| --- | --- | --- | --- |
| M3-CTX-01 | Implement fixed chunking | Implementation + tests + runnable demonstration | Pending |
| M3-CTX-02 | Implement recursive chunking | Implementation + tests + runnable demonstration | Pending |
| M3-CTX-03 | Implement semantic chunking | Implementation + tests + runnable demonstration | Pending |
| M3-CTX-04 | Implement metadata enrichment | Implementation + tests | Pending |
| M3-CTX-05 | Implement context optimisation | Implementation + tests + runnable demonstration | Pending |

## Hands-On Labs

| ID | Source Lab | Required Evidence | Status |
| --- | --- | --- | --- |
| M3-LAB-01 | Build a document-ingestion pipeline | Runnable implementation + tests + UI demonstration | Pending |
| M3-LAB-02 | Create a vector-search workflow | Runnable implementation + tests + UI demonstration | Pending |
| M3-LAB-03 | Implement chunking strategies | Runnable fixed/recursive/semantic implementations + comparison evidence | Pending |
| M3-LAB-04 | Build a RAG prototype | Runnable end-to-end implementation + tests + UI demonstration | Pending |

## Required Tools

The source explicitly identifies the following technologies. Their presence must
be demonstrated with implementation evidence rather than documentation claims
alone.

| ID | Tool | Required Evidence | Status |
| --- | --- | --- | --- |
| M3-TOOL-01 | FAISS | Runtime integration + tests | Pending |
| M3-TOOL-02 | ChromaDB | Runtime integration + tests | Pending |
| M3-TOOL-03 | Pinecone | Integration boundary + tests and/or live verification | Pending |
| M3-TOOL-04 | LangChain | Runtime RAG/retrieval integration + tests | Pending |
| M3-TOOL-05 | OpenAI Embeddings | Provider integration + tests and/or live verification | Pending |

## Required Deliverables

| ID | Deliverable | Acceptance Evidence | Status |
| --- | --- | --- | --- |
| M3-DEL-01 | Working RAG pipeline | Runnable end-to-end implementation + tests + documentation | Pending |
| M3-DEL-02 | Vector retrieval system | Runnable implementation + tests + retrieval evidence | Pending |

## Portfolio Demonstration Requirement

This repository additionally requires each completed module to expose a proper
runnable user interface or demonstrable front end.

The Module 3 UI must explain what each major workflow demonstrates, how to use
or test it, what result to expect, and what the actual result demonstrates.

The UI is an additive presentation layer and must not replace or distort the
source-required implementation.

| ID | Requirement | Required Evidence | Status |
| --- | --- | --- | --- |
| M3-PORT-01 | Runnable self-explanatory Module 3 demonstration UI | UI contract tests + manual/live verification | Pending |

## Python Engineering Standards

All Module 3 Python implementation must:

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
4. Source-specified technologies must be genuinely integrated.
5. Additive improvements must not replace source requirements.
6. Documents, retrieved content, metadata, provider output, and other external
   content are untrusted until validated.
7. Retrieved content cannot acquire application or tool authority.
8. Normal deterministic tests must not require live credentials.
9. Tests and quality rules must not be weakened merely to obtain green status.
10. Source deviations require explicit human approval.
11. Completion requires both deterministic quality gates and complete
    source-to-evidence traceability.

## Definition of Done

- [ ] RAG architecture is demonstrated.
- [ ] Knowledge-freshness problem is demonstrated.
- [ ] Document-ingestion pipeline is implemented.
- [ ] Fixed chunking is implemented.
- [ ] Recursive chunking is implemented.
- [ ] Semantic chunking is implemented.
- [ ] Metadata enrichment is implemented.
- [ ] Embedding generation is implemented.
- [ ] Vector similarity and distance metrics are demonstrated.
- [ ] Semantic retrieval is implemented.
- [ ] Indexing strategies and ANN concepts are demonstrated.
- [ ] FAISS is genuinely integrated.
- [ ] ChromaDB is genuinely integrated.
- [ ] Pinecone is genuinely integrated.
- [ ] LangChain is genuinely integrated.
- [ ] OpenAI Embeddings are genuinely integrated.
- [ ] Query transformation is implemented.
- [ ] Context optimisation is implemented.
- [ ] Vector-search workflow is runnable.
- [ ] End-to-end RAG prototype is runnable.
- [ ] Working RAG pipeline is complete.
- [ ] Vector retrieval system is complete.
- [ ] Self-explanatory Streamlit UI demonstrates Module 3 functionality.
- [ ] Automated tests cover required behavior and failure paths.
- [ ] Repository quality gates pass in fail-fast order.
- [ ] Source-to-evidence traceability has no unexplained gaps.
- [ ] Human review confirms source faithfulness.
