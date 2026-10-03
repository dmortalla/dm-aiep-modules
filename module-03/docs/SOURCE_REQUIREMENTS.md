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
| M3-RAG-01 | Demonstrate RAG architecture | Implementation + tests + runnable demonstration | Complete |
| M3-RAG-02 | Explain and demonstrate the knowledge-freshness problem addressed by RAG | Documentation + runnable demonstration | Complete |
| M3-RAG-03 | Implement a retrieval pipeline | Implementation + tests + runnable demonstration | Complete |
| M3-RAG-04 | Implement query transformation | Implementation + tests + runnable demonstration | Complete |

### Embeddings and Semantic Retrieval

| ID | Requirement | Required Evidence | Status |
| --- | --- | --- | --- |
| M3-RET-01 | Generate embeddings for retrieval | Implementation + tests | Complete |
| M3-RET-02 | Demonstrate vector similarity and distance metrics | Implementation + tests + runnable demonstration | Complete |
| M3-RET-03 | Implement semantic retrieval | Implementation + tests + runnable demonstration | Complete |
| M3-RET-04 | Demonstrate indexing strategies and approximate-nearest-neighbor concepts | Implementation/demonstration + tests where applicable | Complete |

### Vector Stores

| ID | Requirement | Required Evidence | Status |
| --- | --- | --- | --- |
| M3-VS-01 | Integrate FAISS for vector retrieval | Genuine runtime integration + tests | Complete |
| M3-VS-02 | Integrate ChromaDB for vector retrieval | Genuine runtime integration + tests | Complete |
| M3-VS-03 | Integrate Pinecone for vector retrieval | Genuine integration boundary + tests and/or live verification | Complete |

### Chunking and Context Engineering

| ID | Requirement | Required Evidence | Status |
| --- | --- | --- | --- |
| M3-CTX-01 | Implement fixed chunking | Implementation + tests + runnable demonstration | Complete |
| M3-CTX-02 | Implement recursive chunking | Implementation + tests + runnable demonstration | Complete |
| M3-CTX-03 | Implement semantic chunking | Implementation + tests + runnable demonstration | Complete |
| M3-CTX-04 | Implement metadata enrichment | Implementation + tests | Complete |
| M3-CTX-05 | Implement context optimisation | Implementation + tests + runnable demonstration | Complete |

## Hands-On Labs

| ID | Source Lab | Required Evidence | Status |
| --- | --- | --- | --- |
| M3-LAB-01 | Build a document-ingestion pipeline | Runnable implementation + tests + UI demonstration | Complete |
| M3-LAB-02 | Create a vector-search workflow | Runnable implementation + tests + UI demonstration | Complete |
| M3-LAB-03 | Implement chunking strategies | Runnable fixed/recursive/semantic implementations + comparison evidence | Complete |
| M3-LAB-04 | Build a RAG prototype | Runnable end-to-end implementation + tests + UI demonstration | Complete |

## Required Tools

The source explicitly identifies the following technologies. Their presence must
be demonstrated with implementation evidence rather than documentation claims
alone.

| ID | Tool | Required Evidence | Status |
| --- | --- | --- | --- |
| M3-TOOL-01 | FAISS | Runtime integration + tests | Complete |
| M3-TOOL-02 | ChromaDB | Runtime integration + tests | Complete |
| M3-TOOL-03 | Pinecone | Integration boundary + tests and/or live verification | Complete |
| M3-TOOL-04 | LangChain | Runtime RAG/retrieval integration + tests | Complete |
| M3-TOOL-05 | OpenAI Embeddings | Provider integration + tests and/or live verification | Complete |

## Required Deliverables

| ID | Deliverable | Acceptance Evidence | Status |
| --- | --- | --- | --- |
| M3-DEL-01 | Working RAG pipeline | Runnable end-to-end implementation + tests + documentation | Complete |
| M3-DEL-02 | Vector retrieval system | Runnable implementation + tests + retrieval evidence | Complete |

## Portfolio Demonstration Requirement

This repository additionally requires each completed module to expose a proper
runnable user interface or demonstrable front end.

The Module 3 UI must explain what each major workflow demonstrates, how to use
or test it, what result to expect, and what the actual result demonstrates.

The UI is an additive presentation layer and must not replace or distort the
source-required implementation.

| ID | Requirement | Required Evidence | Status |
| --- | --- | --- | --- |
| M3-PORT-01 | Runnable self-explanatory Module 3 demonstration UI | UI contract tests + manual/live verification | Complete |

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

- [x] RAG architecture is demonstrated.
- [x] Knowledge-freshness problem is demonstrated.
- [x] Document-ingestion pipeline is implemented.
- [x] Fixed chunking is implemented.
- [x] Recursive chunking is implemented.
- [x] Semantic chunking is implemented.
- [x] Metadata enrichment is implemented.
- [x] Embedding generation is implemented.
- [x] Vector similarity and distance metrics are demonstrated.
- [x] Semantic retrieval is implemented.
- [x] Indexing strategies and ANN concepts are demonstrated.
- [x] FAISS is genuinely integrated.
- [x] ChromaDB is genuinely integrated.
- [x] Pinecone is genuinely integrated.
- [x] LangChain is genuinely integrated.
- [x] OpenAI Embeddings are genuinely integrated.
- [x] Query transformation is implemented.
- [x] Context optimisation is implemented.
- [x] Vector-search workflow is runnable.
- [x] End-to-end RAG prototype is runnable.
- [x] Working RAG pipeline is complete.
- [x] Vector retrieval system is complete.
- [x] Self-explanatory Streamlit UI demonstrates Module 3 functionality.
- [x] Automated tests cover required behavior and failure paths.
- [x] Repository quality gates pass in fail-fast order.
- [x] Source-to-evidence traceability has no unexplained gaps.
- [x] Human review confirms source faithfulness.
