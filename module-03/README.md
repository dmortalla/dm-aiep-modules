# Module 3 — RAG Engineering Foundations

![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)
![pytest](https://img.shields.io/badge/tests-pytest-brightgreen)
![Ruff](https://img.shields.io/badge/code%20quality-Ruff-brightgreen)
![FAISS](https://img.shields.io/badge/vector%20search-FAISS-blue)
![ChromaDB](https://img.shields.io/badge/vector%20DB-ChromaDB-orange)
![LangChain](https://img.shields.io/badge/RAG-LangChain-1C3C3C)
![Pinecone](https://img.shields.io/badge/Pinecone-offline%20verified-000000)
![OpenAI Embeddings](https://img.shields.io/badge/OpenAI%20Embeddings-offline%20verified-412991)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B)

A retrieval-augmented generation foundation that is inspectable end to end:
ingestion and provenance, three chunking strategies, embeddings and similarity
metrics, vector retrieval and stores, query transformation, bounded context
assembly, a core RAG pipeline beside a LangChain pipeline, and knowledge
freshness through corpus refresh.

## Executive overview

Module 3 designs a scalable RAG pipeline as separate, testable stages with
immutable provenance and explicit trust boundaries. The core package has no
Streamlit dependency, a nine-area Streamlit application presents every stage, and
seven runnable examples exercise the stages directly. The module is standalone
and imports nothing from other modules.

## Status and reviewer start-here

Module 3 implementation and Stories 1–10 are complete, human-approved and
released as the annotated Git tag `v0.3.0-module-3`. The
[28-requirement evidence map](docs/TRACEABILITY.md) and
[verification record](docs/VERIFICATION.md) document the source reconciliation,
deterministic gates and human acceptance evidence. Normal tests and default UI
paths are credential-free.

Start with the Streamlit application, then the examples (see
[Run](#run-and-reviewer-instructions)).

## Architecture

The pipeline runs ingestion → chunking → embeddings → vector retrieval/stores →
query transformation → bounded context → generation, with package boundaries and
dependency direction fixed by the frozen
[architecture](docs/ARCHITECTURE.md).

```text
src/rag_engineering_foundations/
    ingestion.py, chunking.py            ingestion with provenance; fixed/recursive/semantic chunking
    embeddings.py, vectors.py            embeddings and similarity metrics
    faiss_index.py, chroma_index.py,     vector retrieval and stores
    pinecone_index.py, retrieval.py
    openai_embeddings.py                 OpenAI embeddings adapter
    query_transformation.py              query derivation and deterministic merge
    context_optimization.py              bounded, rank-preserving context
    rag_pipeline.py, langchain_rag.py    core and LangChain RAG
    generation.py                        local extractive generator
app.py                                   Streamlit presentation layer
examples/                                seven runnable examples
```

## Key capabilities

The nine Streamlit areas are Overview, Ingestion, Chunking comparison,
Embeddings & vectors, Vector search (FAISS), Vector stores (Chroma / Pinecone),
Query transformation & context, RAG prototype (core vs LangChain), and Knowledge
freshness. Together they demonstrate:

- ingestion and provenance;
- fixed, recursive and semantic chunking;
- embedding metrics;
- vector retrieval and stores;
- query transformation;
- bounded context;
- core and LangChain RAG;
- corpus-refresh knowledge freshness.

## Production-grade engineering

- Frozen architecture with explicit package boundaries and dependency direction.
- Immutable data and provenance, structural validation and bounds, with failure
  paths and UI behaviour tested.
- A fail-fast quality sequence: Ruff, pytest, compileall and `git diff --check`.
- Genuine local runtimes for FAISS, ChromaDB and LangChain.

## Security and trust boundaries

- Ingestion and chunking preserve exact content and offsets and keep derived
  metadata separate from untrusted caller attributes.
- Retrieved content cannot reach query-transformation policy; adversarial query
  strings remain data.
- Retrieval and store results are validated for identity, finite metrics,
  dimensions, namespace and malformed output. Provider metadata acquires no
  authority, and public provider errors omit payloads and credentials.
- Context assembly enforces whole-chunk, rank-preserving bounds with explicit
  exclusions.
- Injection-style strings and malicious metadata are tested through the core and
  LangChain paths; instructions in generated output stay inert.
- The UI renders no unsafe HTML, reimplements no domain logic and has a no-key
  guard for the optional OpenAI panel.

These checks establish application trust boundaries, not universal LLM
injection immunity.

## Verification and evidence

| Integration | Established evidence | Not established |
| --- | --- | --- |
| FAISS | Genuine local `IndexFlatIP`/`IndexFlatL2` add/search; ranking, metric orientation, provenance, invalid-output handling | Distributed deployment, persistence, ANN performance |
| ChromaDB | Genuine local ephemeral collection; explicit vectors, HNSW settings, metric conversions, cleanup | Remote Chroma, durability, production-scale recall/latency |
| Pinecone | Genuine SDK/integration boundary verified with deterministic offline fixtures | Live remote-service verification |
| OpenAI Embeddings | Genuine provider adapter; offline request/response verification through mock transports | Live API verification, trained semantic-quality results |
| LangChain | Genuine runtime RAG sequencing with real end-to-end output | Framework agents/tools, remote LLM generation |

At the Story 10 closeout (2026-10-03) the full-repository suite passed with 1054
tests and three accepted ChromaDB deprecation warnings, all seven examples
passed, and the human reviewer approved the Streamlit UI. Exact gates are in the
[verification record](docs/VERIFICATION.md). Fixture scores and receipts are not
measured remote behaviour.

## Limitations and evidence boundaries

`LocalHashEmbedder`, the tiny semantic topic signal and `LocalExtractiveGenerator`
are explicitly limited teaching implementations. They do not establish trained
semantic quality or source truth. Budgets count characters, not tokens; FAISS is
exact and Chroma is ephemeral; persistence, distributed operation and cloud
performance are not claimed. Live remote OpenAI/Pinecone verification is not
established. The optional OpenAI panel requires an explicitly supplied key.

## Run and reviewer instructions

From the repository root:

```powershell
uv sync --locked
uv run streamlit run module-03/app.py --browser.gatherUsageStats false
uv run python module-03/examples/rag_freshness.py
```

The other examples in [`examples/`](examples/) cover chunking comparison,
embedding metrics, vector search, Chroma search, offline Pinecone, and the
query/context pipeline.

## Documentation

[Architecture](docs/ARCHITECTURE.md) · [Source requirements](docs/SOURCE_REQUIREMENTS.md) ·
[Traceability](docs/TRACEABILITY.md) · [Verification](docs/VERIFICATION.md) ·
[Story 10 closeout](docs/STORY_10.md) · [Portfolio README](../README.md)

---

Developed from Techademy AI Engineering program requirements. Independent
implementation and engineering enhancements.
