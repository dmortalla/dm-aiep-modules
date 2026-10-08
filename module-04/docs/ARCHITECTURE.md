# Module 4 Architecture

## Module

**Advanced RAG & Evaluation Systems**

## Architectural Goal

Implement the authoritative Module 4 source requirements as an independently
demonstrable advance on Module 3's RAG foundations — hybrid retrieval,
reranking, context/latency/cost optimisation, RAGAS evaluation, and
LangSmith/LangFuse observability — while preserving the published behavior of
Modules 1-3.

Source faithfulness is the hard invariant. Production-oriented engineering
may extend the implementation but must not replace, omit, weaken, or
reinterpret source requirements. This document and
[SOURCE_REQUIREMENTS.md](SOURCE_REQUIREMENTS.md) were frozen together and
approved by human architecture review before any Story 2+ implementation
began.

## Approved Human Resolutions

The following eight decisions were presented as genuine ambiguities during
planning and were explicitly approved by the human prior to Story 1. They are
binding for every later story; no story may silently reinterpret them.

1. **Orchestration type.** Module 4 uses an independent `HybridRagResult`
   orchestration type. Module 3's frozen `RagResult`/`RagConfig` contracts
   (closed `Literal["core", "langchain"]` integration field, strict
   cross-stage `__post_init__` validation) are not modified. The M4
   orchestration composes M3's `retrieve`, `optimize_context`, and `generate`
   functions directly as building blocks. **[Superseded — Rule 44 isolation amendment, 2026-10-07; see below.]** The independent
   `HybridRagResult` type stands; composing Module 3 functions does not.
2. **RAGAS judge.** Normal (credential-free) tests invoke the real `ragas`
   library against an injected, deterministic judge double. Live-LLM-judge
   verification is a separately gated, explicitly opt-in path. The judge
   provider remains configurable, not hardcoded to one vendor.
3. **Cross-encoder model.** Normal tests use an injected deterministic
   scorer behind the `Reranker` boundary. Real `sentence-transformers`
   model execution is opt-in and runs only when explicitly requested. Model
   weights are never vendored into Git.
4. **LangSmith / LangFuse.** Normal gates exercise the genuine SDK call path
   against an offline mocked transport (mirroring Module 3's OpenAI/Pinecone
   offline-SDK-call pattern). Live verification against the real SaaS
   platforms is a separately gated, opt-in path. **[Limited — Story 12
   closeout amendment, 2026-10-08; see below.]** The offline genuine-SDK
   evidence is final; the separate live opt-in path was not built.
5. **Dynamic retrieval policy.** The dynamic-retrieval decision logic is a
   deterministic, documented, inspectable policy function. It is explicitly
   labeled an implementation decision, not a course-prescribed algorithm —
   the Module 4 source names the topic but not a method.
6. **Caching backend.** The required retrieval-caching implementation uses an
   in-memory cache only. Redis or other external caching infrastructure is
   not added.
7. **Package name.** The Module 4 package is named `advanced_rag_evaluation`,
   mirroring Module 3's `rag_engineering_foundations` naming convention.
8. **Cost measurement.** Cost measurement uses configurable, versioned
   pricing data and an explicit, documented counting convention. When a
   provider reports actual token usage, that figure is used and labeled as
   actual; otherwise the estimate is computed deterministically and
   explicitly labeled as an estimate, never presented as an exact cost.

## Repository Strategy

Module 4 follows the established multi-module repository convention, the
same shape used by Module 3:

    module-04/
        app.py
        docs/
            SOURCE_REQUIREMENTS.md
            ARCHITECTURE.md
            STORY_01.md ...
            TRACEABILITY.md
            VERIFICATION.md
        src/
            advanced_rag_evaluation/
        tests/

The root `pyproject.toml` remains the shared dependency and tooling
authority. Published Modules 1-3 must not be reorganized or modified merely
for symmetry or Module 4's convenience.

## Module 3 Reuse Classification

**[Superseded — Rule 44 isolation amendment, 2026-10-07; see below.]** Module 4 reuses no Module 3 implementation. This table is kept only as
the record of the original decision.

| Capability | Classification | Notes |
| --- | --- | --- |
| Document ingestion/provenance | Reuse concept/contract | Not an M4 topic; consumed as-is. |
| Fixed/recursive/semantic chunking | Reuse concept/contract | Not an M4 topic. |
| Embeddings | Reuse concept/contract | Semantic leg of hybrid retrieval reuses `Embedder`/`EmbeddingBatch` unchanged. |
| Vector metrics | Reuse concept/contract | Unchanged; fusion operates on resulting scores. |
| Semantic retrieval (`M3-RET-03`) | Extend through an M4 boundary | One input leg to the new `hybrid_retrieval` fusion layer; `retrieval.py` is not modified. |
| FAISS | Reuse concept/contract | Used unmodified as a `VectorIndex` adapter. |
| ChromaDB | Reuse concept/contract | Unmodified adapter, exercised inside the hybrid/caching workflow. |
| Pinecone | Reuse concept/contract | Same as ChromaDB. |
| Query transformation | Reuse concept/contract; dynamic-retrieval decision logic is new M4 code | The transform contract is unchanged; the new `dynamic_retrieval` module decides which config to apply. |
| Context optimisation | Extend through an M4 boundary | `context_filtering` runs as a new pre-stage composing with, not modifying, `optimize_context`. |
| RAG orchestration | Independent M4 implementation | See Approved Human Resolution 1. |
| LangChain | Not relevant to M4's required tools | Not in the Module 4 `TOOLS` list; not independently required M4 evidence. |
| Streamlit UI | Extend through an M4 boundary | New `module-04/app.py`, same What/How/Controls/Expected/Actual/Why pattern and UI-calls-package-functions dependency direction. |

## Proposed Package Layout (introduced across Stories 2-11; none of this code exists after Story 1)

    module-04/src/advanced_rag_evaluation/
        __init__.py
        errors.py
        corpus.py                     # Rule 44 amendment
        semantic_retrieval.py         # Rule 44 amendment (ChromaDB/Pinecone)
        bm25.py                       # Story 2
        hybrid_retrieval.py           # Story 3
        reranking.py                  # Story 4
        context_filtering.py          # Story 5
        retrieval_cache.py            # Story 5
        dynamic_retrieval.py          # Story 5
        telemetry/
            latency.py                # Story 6
            cost.py                   # Story 6
        evaluation/
            ragas_adapter.py          # Story 7
        observability/
            langsmith_adapter.py      # Story 8
            langfuse_adapter.py       # Story 9
            failure_analysis.py       # Story 9
        advanced_rag_pipeline.py      # Story 10 [Clarified — Story 10 placement amendment, 2026-10-08; see below]

Story 1 introduces only `__init__.py`; it imports nothing and initializes no
provider, client, or credential, matching Module 3's Story 1 precedent.

## Core Pipeline (target shape, realized across later stories)

    query
      -> dynamic_retrieval (policy: which legs/config to use)
      -> [BM25 leg] + [semantic leg] -> hybrid_retrieval (fusion)
      -> retrieval_cache (wraps either/both legs)
      -> reranking (cross-encoder)
      -> context_filtering (pre-stage)
      -> M3 optimize_context (unchanged)   [superseded: no M3 stage]
      -> M3 generate (unchanged)           [superseded: M4-owned, Story 10]
      -> evaluation (RAGAS: faithfulness, context precision, relevance)
      -> observability (LangSmith trace, LangFuse monitor, latency/cost record)
      -> HybridRagResult

## Boundary Definitions

- **BM25** (`bm25.py`): deterministic, offline, pure-local lexical index
  behind a structural `LexicalIndex` protocol parallel to M3's `VectorIndex`.
  **[Superseded — Rule 44 isolation amendment, 2026-10-07; see below.]** BM25 indexes Module 4 `CorpusChunk` objects.
- **Hybrid retrieval/fusion** (`hybrid_retrieval.py`): deterministic score
  fusion (default Reciprocal Rank Fusion) retaining both legs' original
  rank/score as evidence.
- **Reranking / cross-encoder** (`reranking.py`): `Reranker` protocol;
  retains pre- and post-rerank rank/score for auditability. Deterministic
  injected scorer for normal tests (Resolution 3).
- **Context filtering** (`context_filtering.py`): relevance-threshold/dedup
  pre-stage with its own exclusion evidence, running before M3's unmodified
  `optimize_context`.
- **Caching** (`retrieval_cache.py`): in-memory `RetrievalCache` (Resolution
  6); cache keys derive only from validated query/config input, never from
  retrieved content; cached entries retain provenance and an explicit
  `from_cache` marker.
- **Dynamic retrieval** (`dynamic_retrieval.py`): deterministic, documented
  policy function (Resolution 5) whose decision and rationale are retained as
  evidence.
- **Latency measurement** (`telemetry/latency.py`): per-stage timing records
  with an injectable clock for deterministic tests.
- **Cost measurement** (`telemetry/cost.py`): configurable/versioned pricing
  table; actual provider usage used and labeled as actual when available,
  otherwise a clearly labeled deterministic estimate (Resolution 8).
- **RAGAS / faithfulness / context precision / relevance** (`evaluation/
  ragas_adapter.py`): genuine `ragas` call; deterministic injected judge for
  normal tests, live judge opt-in (Resolution 2).
- **LangSmith / LangFuse** (`observability/langsmith_adapter.py`,
  `observability/langfuse_adapter.py`): genuine SDK call over an offline
  mocked transport for normal tests, live opt-in (Resolution 4); telemetry
  redacts raw content/credentials by default; tracing/monitoring failures are
  logged, not fatal to the RAG answer.
  **[Limited — Story 12 closeout amendment, 2026-10-08; see below.]** No
  live opt-in transport exists; both adapters accept only their offline
  transports.
- **Failure analysis** (`observability/failure_analysis.py`): maps caught
  domain errors to a fixed, actionable category vocabulary.
- **ChromaDB / Pinecone**: unmodified M3 adapters, exercised as a hybrid leg.
  **[Superseded — Rule 44 isolation amendment, 2026-10-07; see below.]** Both are Module 4-owned boundaries in `semantic_retrieval.py`.
- **Evaluation dashboard / presentation** (`module-04/app.py`): calls package
  functions only; renders real evaluation-run output, not static content;
  every demonstration follows What -> How -> Controls -> Expected result ->
  Actual result -> Why it matters.

## Dependency Direction

Preferred dependency direction, matching Module 3's invariant:

    Streamlit UI (module-04/app.py)
         |
         v
    advanced_rag_pipeline (M4 orchestration)
         |
         +----------------+----------------+
         v                v                v
    hybrid_retrieval   evaluation      observability
         |                |                |
    bm25 / M3 retrieval   M3 generate   telemetry (latency/cost)
         |
    retrieval_cache, context_filtering, dynamic_retrieval, reranking

Core contracts, retrieval logic, evaluation logic, and observability adapters
must not depend on Streamlit. Module 4 code never imports or modifies Module
3 source files; it imports Module 3's public package API only. **[Superseded — Rule 44 isolation amendment, 2026-10-07; see below.]**
Module 4 imports no Module 1-3 package at all.

## Security and Trust Boundaries

1. Retrieved, cached, reranked, and fused content remains untrusted data at
   every new boundary.
2. Cross-encoder scores and RAGAS judge output are data/metrics, never
   instructions the pipeline executes.
3. Dynamic-retrieval decisions and cache keys derive only from validated
   application inputs, never from retrieved/document content.
4. Credentials for RAGAS judges, LangSmith, and LangFuse cannot originate
   from documents, prompts, retrieved context, or model output, and are
   never logged or placed in trace payloads.
5. Telemetry/trace payloads redact raw chunk content and credentials by
   default; richer payloads require explicit opt-in.
6. Cached entries retain original retrieval provenance/trust classification
   and an explicit `from_cache` marker.
7. External-service failures (BM25 library, cross-encoder, RAGAS judge,
   LangSmith, LangFuse) become actionable domain errors; observability
   failures are non-fatal to the underlying RAG answer.
8. RAGAS/LangSmith/LangFuse outputs are read-only evidence; they cannot grant
   retrieved or model content application or tool authority.

## Testing Strategy

Deterministic tests must cover at least: BM25 ranking, hybrid fusion
provenance, reranking pre/post-rank evidence (injected scorer), context
filtering, in-memory cache hit/miss and provenance retention, dynamic
retrieval policy determinism, latency/cost recording, RAGAS metric
computation with an injected judge, LangSmith/LangFuse adapters over offline
mocked transports, failure-path handling for every new external boundary,
end-to-end `HybridRagResult` composition, and the Streamlit dashboard/UI
contract. Normal tests must not require live credentials.

## Quality Gates

Quality gates remain fail-fast, matching Module 3:

1. `uv run ruff check .`
2. `uv run pytest`
3. `uv run python -m compileall` against relevant source, tests, and apps.

Safe deterministic Ruff fixes may be applied before the formal gate. Unsafe
fixes must never be applied automatically.

## Self-Healing Boundary

Agentic implementation may detect a quality-gate failure, classify the
diagnostic, apply a deterministic safe repair where appropriate, use bounded
semantic repair when deterministic repair is insufficient, rerun the failed
gate, then rerun the complete fail-fast sequence. Agents must not weaken
tests, quality rules, architecture, or source requirements merely to obtain
green status.

## Codex / Claude Training Role

Module 4 is also a training case for the future module-lifecycle engineering
system. Per-story evidence should be classified into: agent policy, reusable
provider-neutral skill, deterministic automation, and human authority. A
single story's observation is not generalized into universal policy.

## Planned Stories

1. Source freeze, approved architecture, package scaffold (this story).
2. BM25 lexical retrieval.
3. Hybrid retrieval / fusion.
4. Reranking and cross-encoder pipeline.
5. Context filtering, retrieval caching, dynamic retrieval.
6. Latency and cost measurement.
7. RAGAS evaluation (faithfulness, context precision, relevance).
8. LangSmith tracing.
9. LangFuse monitoring and failure analysis.
10. End-to-end hybrid RAG orchestration (`HybridRagResult`).
11. Streamlit evaluation dashboard and demonstration UI.
12. Traceability, verification, documentation, and release readiness.

## Definition of Done for Architecture Phase

- [x] Authoritative Module 4 source inspected.
- [x] Existing repository/module pattern inspected.
- [x] Source requirements captured with stable IDs.
- [x] Module 3 reuse classified capability-by-capability.
- [x] Hybrid retrieval/fusion boundary defined.
- [x] Reranking/cross-encoder boundary defined.
- [x] Context filtering, caching, dynamic retrieval boundaries defined.
- [x] Latency/cost measurement boundaries defined.
- [x] RAGAS boundary defined.
- [x] LangSmith/LangFuse boundaries defined.
- [x] Evaluation dashboard and presentation boundary defined.
- [x] Security/trust boundaries defined.
- [x] Testing and quality-gate policy defined.
- [x] Codex/Claude training role preserved.
- [x] Human architecture approval (eight resolutions recorded above).

## HUMAN-APPROVED ARCHITECTURE AMENDMENT — 2026-10-05 (Story 5 review)

This amendment is appended after the original freeze above, which remains
unaltered historical record. It does not rewrite or remove any original
wording; it supersedes only the single point described below for Story 5
onward, including Story 10's final orchestration.

**Original text (unchanged above, for reference):** the "Boundary
Definitions" section's context-filtering entry described this stage as
running "before M3's unmodified `optimize_context`," implying a literal
call into that Module 3 function.

**Amendment:** independent human review of Story 5 confirmed that Module
3's `context_optimization.optimize_context` requires exact
`retrieval_workflow.RetrievalCandidate` objects, representing Module 3's
older, single-leg retrieval evidence model. Story 3/4's
`HybridCandidate`/`RerankedCandidate` evidence (BM25 + semantic fusion +
reranking) has no compatible shape. Constructing a synthetic
`RetrievalCandidate`/`SearchHit` adapter merely to satisfy the original
architecture wording would risk losing or misrepresenting Module 4's
lexical/semantic/RRF/reranking provenance, and was rejected.

**Approved resolution:** `context_filtering.py` is a self-sufficient
Module 4-native filtering stage over Story 4's `RerankedResults`. It does
**not** call Module 3's `optimize_context`, and does **not** fabricate an
adapter to do so. Module 3 remains unmodified. See
`module-04/docs/STORY_05.md` for the full implementation evidence and
reasoning this amendment ratifies.

**Binding on later stories:** Story 10's final `HybridRagResult`
orchestration must preserve this Module 4-native filtering/evidence model.
It must not fabricate an `optimize_context`-compatible `RetrievalCandidate`
adapter merely to force a literal call into that Module 3 function. Any
future need for a separate, explicit context-budget boundary (character/
token budgeting analogous to Module 3's budget, but over Module 4 evidence)
is out of scope for this amendment and must be raised as its own explicit
human-in-the-loop decision at the story that would introduce it, not
assumed here.

## HUMAN-APPROVED ARCHITECTURE AMENDMENT — 2026-10-07 (Rule 44 isolation remediation)

This amendment is appended after the original freeze and the Story 5
amendment above, both of which remain historical record. Where earlier text
is superseded, it has been left in place and marked with a short
"Superseded — Rule 44 isolation amendment" note rather than deleted, so the
history of the decision stays visible. This amendment states current
architectural truth wherever it conflicts with earlier wording.

**Rule 44 (standalone ownership).** Each academic module is standalone.
Module 4 runtime source, tests, and examples import nothing from
`ai_engineering_foundations` (Module 1), `prompt_engineering_systems`
(Module 2), or `rag_engineering_foundations` (Module 3). Third-party libraries
required by Module 4 remain allowed. There is no runtime dependency on
Modules 1-3.

**Superseded decisions.** The following earlier approvals instructed Module 4
to reuse Module 3 implementations; they are superseded by this amendment:

- Approved Human Resolution 1, in its final sentence only (composing Module
  3's `retrieve`, `optimize_context`, and `generate`). The independent
  `HybridRagResult` orchestration type remains approved. Story 10 must build
  its generation and orchestration from Module 4-owned code.
- The "Module 3 Reuse Classification" table in its entirety.
- The Core Pipeline's "M3 optimize_context" and "M3 generate" stages, the
  BM25 boundary's reference to Module 3's `VectorIndex`, the ChromaDB/
  Pinecone boundary entry, and the Dependency Direction's Module 3 nodes and
  "imports Module 3's public package API only" sentence.
- In [SOURCE_REQUIREMENTS.md](SOURCE_REQUIREMENTS.md), the evidence mappings
  for M4-RET-02, M4-TOOL-04, and M4-TOOL-05. The requirements themselves and
  their source basis are unchanged.

The per-story documents (`STORY_01.md` to `STORY_09.md`) are accepted
historical evidence and are not rewritten; their references to Module 3
contracts describe the implementation as it was reviewed at the time.

**Current Module 4-owned foundation.**

- `corpus.py` owns the minimal chunk contract Module 4 needs:
  `CorpusChunk` (stable `chunk_id`, zero-based `index`, inert `content`
  hidden from `repr`) and `ChunkProvenance` (`source_id`, `document_id`).
  `build_corpus` assigns deterministic identity to passages the application
  has already split. It is deliberately not an ingestion or chunking
  subsystem.
- `semantic_retrieval.py` owns the semantic leg (M4-RET-02): the `Embedder`
  boundary and validated `EmbeddingBatch`; `HashEmbedder`, a deterministic,
  credential-free feature-hashing embedder for tests and demonstrations
  (labelled `module-4-local-hash:<dimension>`; it measures token overlap, not
  learned meaning); `SemanticQuery`/`SemanticHit`/`SemanticResults`
  evidence; and two vector-store boundaries.
- **ChromaDB** (M4-TOOL-04) is Module 4's semantic retrieval implementation
  for the hybrid workflow. `ChromaSemanticIndex` runs a genuine in-process
  `chromadb.EphemeralClient` collection (telemetry disabled, cosine space,
  application-supplied vectors, no default embedding function or model
  download), validates every response, recomputes ordering with a
  `chunk_id` tie-break, returns the application's own chunk objects, and
  deletes the collection it created on `close`. Remote Chroma services are
  not exercised or claimed.
- **Pinecone** (M4-TOOL-05) is a Module 4-owned integration boundary.
  `PineconeSemanticIndex` accepts an injected index client, upserts the
  installed SDK's `pinecone.Vector` records (identifiers and vectors only),
  and accepts only genuine `pinecone.QueryResponse`/`ScoredVector` responses
  whose identifiers, scores, and size validate. `connect_pinecone_index`
  builds a real SDK index handle from application-supplied credentials and
  host. Deterministic tests verify this boundary offline with an injected
  double; live Pinecone service behavior has not been verified.
- Provider failures become `SemanticProviderError` with fixed messages and no
  chained provider exception, so credentials and payloads cannot leak.
  `errors.py` also adds `CorpusError`, the `SemanticRetrievalError` family,
  and a `GenerationError` classification type for failure analysis; Story 10
  still owns generation itself.

**FAISS removed.** FAISS entered Module 4 only through the superseded reuse
of Module 3; it is not listed by the Module 4 source and is not a Module 4
requirement. Module 4 contains no FAISS adapter or import. (`faiss-cpu`
remains a repository dependency because Module 3 uses it.)

**Hybrid retrieval.** `hybrid_retrieval.fuse_results` now fuses Story 2's
`LexicalResults` with Module 4's `SemanticResults`. Its RRF arithmetic,
evidence retention, and tie-breaking are unchanged.

**Current dependency direction.**

    Streamlit UI (module-04/app.py, Story 11)
         |
         v
    advanced_rag_pipeline (M4 orchestration, Story 10)
         |
         +----------------+----------------+
         v                v                v
    hybrid_retrieval   evaluation      observability
         |                |                |
    bm25 + semantic_retrieval (ChromaDB / Pinecone)   telemetry (latency/cost)
         |
    corpus, retrieval_cache, context_filtering, dynamic_retrieval, reranking

**Permanent guard.** `module-04/tests/test_module_isolation.py` parses every
Module 4 Python file under `src/`, `tests/`, and `examples/` with `ast` and
fails on any import of the three earlier packages (including string-literal
dynamic imports), whether or not that import executes during the test run.
It also imports every runtime module in a clean interpreter and fails if any
earlier package is loaded transitively.

**Not affected.** This amendment does not implement Story 10 or Story 11,
does not complete any later story, and does not modify Modules 1-3.

## HUMAN-APPROVED ARCHITECTURE AMENDMENT — 2026-10-08 (Story 10 placement)

This amendment is appended after the original freeze and the Story 5 and
Rule 44 amendments above, which remain historical record. The Proposed
Package Layout entry `advanced_rag_pipeline.py  # Story 10` is left in place
and marked "Clarified": it described the Story 10 pipeline component at the
architectural level and did not require every generation contract and
implementation to reside in that one source file.

**Decision.** Human architecture review accepted the Story 10 placement:

- `generation.py` is the Module 4-owned generation boundary. It owns the
  generation request/result/citation contracts (`GenerationRequest`,
  `GeneratorOutput`, `GeneratedAnswer`, `Citation`), the `AnswerGenerator`
  boundary and the default deterministic `ExtractiveAnswerGenerator`,
  citation validation against the retained `FilteredContext`, and
  generation-specific handling (`generate_answer`, including abstention when
  no context is retained).
- `advanced_rag_pipeline.py` is the orchestration boundary. It owns
  end-to-end hybrid RAG orchestration (`run_hybrid_rag`), stage timing,
  generation invocation, and the aggregate `HybridRagResult`.
- `GenerationError` (accepted in the Rule 44 remediation) covers
  generation-boundary failures.
- `HybridRagError` covers pipeline/orchestration-boundary failures and is
  distinct from `GenerationError`.

Generation must not be moved back into `advanced_rag_pipeline.py`. The
dependency direction is unchanged: `advanced_rag_pipeline` depends on
`generation`, never the reverse, and neither imports Modules 1-3 (Rule 44).

**Not affected.** No source requirement, earlier approved resolution, or
Story 1-9 decision changes. This amendment does not begin Story 11 or
Story 12.

## HUMAN-APPROVED ARCHITECTURE AMENDMENT — 2026-10-08 (Story 12 closeout)

This amendment is appended after the original freeze and the Story 5, Rule
44, and Story 10 placement amendments above, which remain historical record.
Superseded or limited wording is left in place and marked, not deleted.

**HITL-1: LangSmith/LangFuse live opt-in is a final approved limitation.**
Approved Resolution 4 anticipated a separately gated, opt-in path for live
verification against the real SaaS platforms. That path was not built.
`LangSmithTracer` accepts only `OfflineTransport`, and `LangFuseMonitor`
accepts only `OfflineMonitoringTransport`. The human decided that the
authoritative source requires LangSmith tracing and LangFuse monitoring but
not verified remote SaaS delivery. The genuine SDK integrations with
deterministic offline verification therefore satisfy the final Module 4
scope. Live remote delivery has not been verified. It is outside the final
Module 4 scope, not unfinished Module 4 work. Evidence keeps reporting
`evidence_kind="deterministic_offline"` and `remote_delivery_verified=False`.

**HITL-3: Pinecone live verification is a final approved limitation.** The
Rule 44 amendment's wording, "live service verification not yet performed",
is approved as the final Module 4 limitation. The Module 4-owned genuine
Pinecone SDK boundary (`PineconeSemanticIndex`, `connect_pinecone_index`)
with deterministic offline verification satisfies Module 4 scope. No live
Pinecone service, index, or credential is provisioned or contacted.

**HITL-2: root README deferred to release.** The Module 4 roadmap change in
the root `README.md` is deferred to the governed Module 4 release step. Any
historical closeout assertion that depends on the README is reconciled there.

**Closeout documents.** [TRACEABILITY.md](TRACEABILITY.md) and
[VERIFICATION.md](VERIFICATION.md), named in the Repository Strategy above,
now exist. [STORY_12.md](STORY_12.md) records the closeout.

**Not affected.** No runtime code, contract, dependency, transport, provider,
credential, or service changes. Rule 44 isolation, the Story 5 and Story 10
amendments, and the other seven approved resolutions are unchanged.
