# Module 3 Architecture

## Module

**RAG Engineering Foundations**

## Architectural Goal

Implement the authoritative Module 3 source requirements as an independently
demonstrable Retrieval-Augmented Generation system while preserving the
published behavior of Modules 1 and 2.

Source faithfulness is the hard invariant. Production-oriented engineering may
extend the implementation but must not replace, omit, weaken, or reinterpret
source requirements.

## Repository Strategy

Module 3 follows the established multi-module repository convention:

    module-03/
        app.py
        docs/
            SOURCE_REQUIREMENTS.md
            ARCHITECTURE.md
            TRACEABILITY.md
            VERIFICATION.md
        src/
            rag_engineering_foundations/
        tests/

The root `pyproject.toml` remains the shared dependency and tooling authority.

Published Modules 1 and 2 must not be reorganized merely for symmetry.

## Core Pipeline

The preferred conceptual flow is:

    Documents
        |
        v
    Ingestion + metadata
        |
        v
    Chunking
        |
        v
    Embedding generation
        |
        v
    Vector indexing / stores
        |
        v
    Query transformation
        |
        v
    Semantic retrieval
        |
        v
    Context optimisation
        |
        v
    Generation
        |
        v
    RAG response + retrieval evidence

## Package Boundaries

### Document Ingestion

Responsible for:

- accepting supported source documents;
- extracting document content;
- assigning source identity and provenance;
- metadata enrichment;
- producing validated ingestion contracts.

Document content and metadata are untrusted data.

### Chunking

Responsible for:

- fixed chunking;
- recursive chunking;
- semantic chunking;
- preserving document/chunk provenance;
- exposing meaningful comparison evidence.

Chunking logic must remain independent of Streamlit.

### Embeddings

Responsible for:

- embedding contracts;
- OpenAI Embeddings integration;
- deterministic/offline test doubles where appropriate;
- vector validation;
- actionable provider failures.

### Vector Retrieval

Responsible for:

- vector similarity and distance metrics;
- semantic retrieval;
- indexing strategies;
- ANN concepts;
- FAISS integration;
- ChromaDB integration;
- Pinecone integration.

Vector-store-specific behavior must remain behind explicit integration
boundaries rather than leaking throughout the RAG workflow.

### Query Transformation

Responsible for:

- transforming user queries for retrieval;
- retaining the original query and transformation provenance;
- preventing retrieved/external content from becoming application instructions.

### Context Optimisation

Responsible for:

- ranking/selecting retrieved chunks;
- applying explicit context budgets;
- preserving source metadata and provenance;
- producing inspectable retrieval/context evidence.

### RAG Pipeline

Responsible for orchestrating:

    query
      -> query transformation
      -> retrieval
      -> context optimisation
      -> generation
      -> response evidence

The pipeline must not hide retrieval provenance from the demonstration layer.

### LangChain Integration

LangChain must be genuinely exercised in a source-relevant RAG/retrieval
workflow while remaining behind an explicit integration boundary.

### External Integration Boundary

OpenAI Embeddings and Pinecone require genuine adapters.

Normal quality gates must remain runnable without mandatory live credentials.
Mocks/fakes may verify deterministic request/response behavior, while separate
live verification may establish remote-service behavior where appropriate.

Credentials must never be committed, logged, placed in retrieved context, or
treated as model-controlled data.

### Demonstration UI

`module-03/app.py` is the presentation layer.

The UI should allow a reviewer to exercise and inspect:

- document ingestion;
- fixed, recursive, and semantic chunking;
- embedding/vector concepts;
- vector retrieval;
- vector-store behavior where appropriate;
- query transformation;
- context optimisation;
- the complete RAG prototype.

Each major demonstration should communicate:

    What
      -> How
      -> Controls
      -> Expected result
      -> Actual result
      -> Why the result matters

The UI must call package functionality rather than duplicate domain logic.

## Dependency Direction

Preferred dependency direction:

    Streamlit UI
         |
         v
    RAG workflow / application services
         |
         +-----------------------+
         |                       |
         v                       v
    Query transformation     Ingestion
         |                       |
         v                       v
    Retrieval              Chunking
         |                       |
         +-----------+-----------+
                     |
                     v
              Embedding boundary
                     |
                     v
              Vector-store adapters
                     |
                     v
              Context optimisation
                     |
                     v
              Generation boundary

Core contracts, ingestion, chunking, retrieval logic, and validation must not
depend on Streamlit.

## Security and Trust Boundaries

1. Source documents are untrusted.
2. Retrieved chunks are untrusted.
3. Metadata is untrusted unless application-authored and validated.
4. Retrieved text cannot become system/application authority.
5. Model output cannot directly control privileged behavior.
6. Credentials cannot originate from documents, prompts, retrieved context, or
   model output.
7. Retrieval provenance must remain distinguishable from application policy.
8. External-service failures must become actionable domain errors.

## Testing Strategy

Deterministic tests must cover at least:

- ingestion and provenance;
- malformed/unsupported input;
- metadata enrichment;
- fixed chunking;
- recursive chunking;
- semantic chunking;
- embedding contracts;
- similarity/distance behavior;
- semantic retrieval;
- indexing/ANN demonstrations where applicable;
- FAISS integration;
- ChromaDB integration;
- Pinecone adapter behavior;
- OpenAI Embeddings adapter behavior;
- LangChain integration;
- query transformation;
- context optimisation and budgets;
- end-to-end RAG orchestration;
- untrusted-content boundaries;
- external integration failure paths;
- Streamlit UI contracts.

Normal tests must not require live credentials.

## Quality Gates

Quality gates remain fail-fast:

1. `uv run ruff check .`
2. `uv run pytest`
3. `uv run python -m compileall` against relevant source, tests, and apps.

A later passing gate cannot override an earlier failure.

Safe deterministic Ruff fixes may be applied before the formal gate.
Unsafe fixes must never be applied automatically.

## Self-Healing Boundary

Agentic implementation may:

1. detect quality-gate failures;
2. classify the diagnostic;
3. apply deterministic safe repairs where appropriate;
4. use bounded semantic repair when deterministic repair is insufficient;
5. rerun the failed gate;
6. rerun the complete fail-fast sequence.

Agents must not weaken tests, quality rules, architecture, or source
requirements merely to obtain green status.

## Codex / Claude Training Role

Module 3 is a training case for the future module-lifecycle engineering system.

Implementation work should provide evidence for classification into:

1. agent policy;
2. reusable provider-neutral skill;
3. deterministic automation;
4. human authority.

Codex and Claude Code should ultimately operate under semantically equivalent
repository policy. Repeated evidence, rather than speculation, determines which
procedures are mature enough for shared automation.

PowerShell/manual intervention should be limited to deterministic setup,
verification, recovery, bookkeeping, and explicit human-authority decisions
when agent delegation would provide useful training evidence.

## Architecture Invariants

1. Module 3 source requirements remain authoritative.
2. Published Modules 1 and 2 remain behaviorally intact.
3. UI code is not the domain implementation.
4. External and retrieved content remains untrusted.
5. Retrieved content cannot acquire application authority.
6. Normal automated tests do not require live credentials.
7. Secrets are never committed or exposed through RAG context.
8. External integrations have explicit boundaries.
9. Retrieval provenance remains inspectable.
10. Source completeness and test success are independently verified.
11. Source deviations require explicit human approval.

## Planned Stories

1. Source freeze, architecture, package scaffold, dependency integration.
2. Document ingestion and metadata/provenance contracts.
3. Fixed, recursive, and semantic chunking.
4. Embeddings, vector similarity, and distance metrics.
5. FAISS vector retrieval.
6. ChromaDB and Pinecone integrations plus indexing/ANN concepts.
7. Query transformation and context optimisation.
8. End-to-end RAG pipeline and LangChain integration.
9. Self-explanatory Streamlit demonstration UI.
10. Traceability, verification, documentation, and release readiness.

## Definition of Done for Architecture Phase

- [x] Authoritative Module 3 source inspected.
- [x] Existing repository/module pattern inspected.
- [x] Source requirements captured with stable IDs.
- [x] RAG pipeline boundary defined.
- [x] Ingestion boundary defined.
- [x] Chunking boundary defined.
- [x] Embedding boundary defined.
- [x] Vector retrieval/store boundary defined.
- [x] Query transformation boundary defined.
- [x] Context optimisation boundary defined.
- [x] External integration boundary defined.
- [x] Security/trust boundaries defined.
- [x] Runnable UI boundary defined.
- [x] Testing and quality-gate policy defined.
- [x] Codex/Claude training role preserved.
- [x] Human architecture approval.
