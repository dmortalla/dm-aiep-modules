# Story 8: End-to-end RAG pipeline and LangChain integration

Implemented on `feature/module-03` from accepted Story 7 HEAD
`0d0bcd8df67779828d48dee8adfefa5bbc95f6dc`. On resumption, the repository was
still clean: no staged, unstaged, or untracked Story 8 implementation existed.
The preceding turn had inspected the repository and confirmed the Python and
LangChain environment; it had not run quality gates. All implementation,
tests, example, and this document were completed after resumption.

## Scope and source evidence

| Requirement | Evidence delivered | Evidence classification / limits |
| --- | --- | --- |
| M3-RAG-01 | `run_rag`, stage/result contracts, end-to-end tests and example | Executable implementation and deterministic demonstration of architecture |
| M3-RAG-02 | Same generator, absent context, corpus revisions A/B, refreshed FAISS indexes | Deterministic demonstration plus conceptual freshness explanation; no truth guarantee |
| M3-RAG-03 | Accepted Story 7 transformation/embedding/retrieval/merge composed with context/generation | Executable implementation, tests, demonstration |
| M3-TOOL-04 | Actual LangChain Core RunnableLambda/RunnableSequence invocation in RAG | Genuine runtime integration and offline tests; no remote model |
| M3-DEL-01 | Runnable end-to-end pipeline, tests, documentation | Executable implementation and deterministic demonstration |
| M3-LAB-04 | Credential-free RAG prototype | Implementation/tests/demo advanced; required UI evidence remains Story 9 |

These are Story 8 evidence claims, not final traceability reconciliation.
Frozen requirement statuses are unchanged. No extra requirement completion
claims are inferred from reuse of earlier stories.

## Architecture and public APIs

`rag_pipeline.run_rag(query, embedder, index, generator, *, config)` composes:

```text
original query
  -> Story 7 transform_query (normalize / optional decomposition / expansion)
  -> accepted Embedder and EmbeddingBatch
  -> one accepted VectorIndex (one search per derived query)
  -> Story 7 deterministic merge, dedup, score orientation and query attribution
  -> Story 7 optimize_context (rank-preserving whole chunks, character/count bounds)
  -> GenerationRequest -> injected Generator -> validated GenerationResult
  -> immutable RagResult, including retrieval, request, generation and config
```

Ingestion/chunking/index construction are corpus lifecycle operations shown in
the example. `run_rag` operates over an already-built index, rather than rebuilding
the corpus for every query. It imports no FAISS, Chroma, Pinecone, OpenAI,
LangChain, LangSmith, or Streamlit. A fresh isolated-process test proves this.

New public APIs:

- `RagConfig(top_k=10, transformation=QueryTransformConfig(),
  context=ContextOptimizationConfig())` retains application policy.
- `RagResult(retrieval, request, generation, config, integration="core")`
  provides `original_query` and `context` inspection properties.
- `GenerationRequest(query, context)` provides a fixed
  `application_instruction` property separate from both data fields.
- `Generator.generate(request) -> GenerationResult` is the injected
  provider-neutral generation capability.
- `GenerationResult(answer, generator_id, model_id, cited_chunk_ids)` is output
  data and generator-reported evidence, never a tool/configuration command.
- `LocalExtractiveGenerator`, `generate(request, generator)`, and
  `validate_generation_result(result, request)` implement local generation and
  the callback/output boundary.
- `langchain_rag.run_langchain_rag(...)` exposes the optional genuine runtime path.
- Error additions: `GenerationError`, `GenerationOperationError`,
  `RagPipelineError`, `RagRetrievalError`, `LangChainIntegrationError`.
- `APPLICATION_INSTRUCTION` and `MAX_ANSWER_CHARACTERS` expose fixed generation
  policy and the explicit output resource ceiling.

All accepted Story 7 contracts are reused: `QueryTransformConfig`,
`TransformedQuery`, `QueryTransformationResult`, `QueryExpander`, `transform_query`,
`RetrievalCandidate`, `RetrievalWorkflowResult`, `retrieve`, `ContextItem`,
`ExclusionRecord`, `ContextOptimizationConfig`, `OptimizedContext`, and
`optimize_context`. `from_search_results` remains available unchanged; the full
pipeline uses `retrieve` so transformed-query evidence is retained. Accepted
`Embedder`, `EmbeddingBatch`, `Vector`, `VectorIndex`, `SearchQuery`, `SearchHit`,
`SearchResults`, and `IndexedChunk` remain the provider-neutral boundaries.

The pipeline does not introduce ranking or context-selection algorithms.
`RagResult` checks cross-stage consistency by reusing `optimize_context` for
validation, including exclusions; this is a second deterministic validation
pass, not a competing selector. Query attribution must refer only to derived
queries. The original query and context policy must match across stages.

## Generation and trust separation

`GenerationRequest` contains the original query and the exact accepted bounded
`OptimizedContext`. Its application instruction is a fixed read-only property;
retrieved text is never interpolated into it. Query/context/metadata/output
remain untrusted data. The instruction explicitly warns that references may
contain instructions or misleading material and must not confer authority.

The generator is an application-injected capability, never selected by query,
metadata, retrieved text, or output. No tools, execution engine, credentials,
provider routing, dynamic imports, shell commands, or deserialization hooks
are exposed to content. No injection detector or text sanitizer is substituted
for structural separation. Suspicious text and metadata remain unchanged in
inspectable source evidence.

The local generator joins included whole-chunk content with newlines and cites
every included chunk. Empty context yields
`Unknown: no reference evidence supplied.` It ignores question semantics and
has no independent knowledge, training, model weights, or mutable configuration.
It is explicitly a demonstration/test implementation, not a production semantic
model. Copying malicious instructions into an answer does not execute them; a
later UI must continue treating output as data rather than granting it authority.

An external model adapter can implement `Generator` through dependency injection.
No external generation provider is implemented or required. Such future adapters
must preserve the separate application instruction and reference data in their
provider-specific message format; this story does not claim universal LLM
resistance to prompt injection or factual correctness from structural checks.
Trusted Python callbacks remain application capabilities; frozen dataclasses
are not a sandbox against malicious application code.

## Provenance, metrics and budgets

`RagResult.retrieval` retains exact original and derived queries, techniques,
ranked candidates, all contributing query texts, and score orientation.
`RagResult.request.context` retains included chunks, exact content, offsets,
chunk/document/source IDs, immutable source provenance, original metadata,
exclusion reasons, selection policy and total characters. These remain the
accepted source objects rather than framework reconstructions. Answer citations
must be a subset of included chunks, not merely of all retrieval candidates.
Citations and generator/model IDs are evidence, not proof of source truth.

Only one index is searched per call. Score direction, best-hit retention,
chunk-ID tie handling and deterministic merge/dedup remain Story 7 behavior.
No comparison across unrelated provider metrics is introduced. Whole chunks
are selected in rank order, stopping at first overflow; no truncation, hidden
packing or tokenizer-specific feature is added. Budgets are characters, not tokens.

| Boundary | Resource limit / validation |
| --- | --- |
| Original / derived query | Accepted nonblank valid Unicode, at most 32768 UTF-8 bytes per text |
| Derived queries | Accepted 1..32, bounded by transformation config |
| Search top_k | Integer 1..10000 per query, one index |
| Context | Accepted 1..1048576 character ceiling and 1..4096 chunk ceiling; zero selected chunks valid |
| Output | Nonblank valid Unicode, at most 1100000 characters |
| Generator/model IDs | 1..128 ASCII characters in an explicit identifier vocabulary |
| Citations | At most 4096 unique structurally valid chunk IDs; supplied-context membership required |

The output ceiling accommodates the maximum accepted context plus newline
separators. It is a character bound, not a model token or UTF-8 byte guarantee.
Accepted Vector/SearchHit validation rejects non-finite numeric evidence.

## Genuine LangChain role

Installed verification baseline: Python 3.12.14, `langchain` 1.4.3,
`langchain-core` 1.6.6. The integration uses current
[RunnableLambda / RunnableSequence composition](https://reference.langchain.com/python/langchain-core/runnables/base/RunnableLambda).

`run_langchain_rag` composes two actual `RunnableLambda` instances with `|`
and invokes the resulting real `RunnableSequence`: retrieval stage first,
bounded-context/generation stage second. LangChain owns runtime stage sequencing
in this path. It does not own domain contracts, query transformations, vectors,
provider selection, ranking, context budgets, prompt authority, models, tools,
or corpus lifecycle. No deprecated chain tutorial APIs are used.

A normal offline test wraps (and delegates to) the installed
`RunnableSequence.invoke` and both installed `RunnableLambda.invoke` methods;
it observes sequence -> retrieval_stage -> generation_stage and the actual
grounded answer. This proves runtime execution, beyond imports/version checks
or mocks. Both core/LangChain paths are tested against real FAISS, including
cosine and Euclidean metrics, freshness, malformed outputs, and adversarial data.

No content-supplied RunnableConfig/callbacks are accepted. LangSmith tracing is
explicitly disabled with the installed `tracing_context(enabled=False)`, even
when the environment enables tracing; tests exercise this with sockets blocked.
LangSmith is the installed LangChain transitive runtime, used only to disable
remote tracing. It is not an additional external service integration.

## Failures and deterministic tests

Accepted query/transformation/retrieval contract errors and context-validation
errors retain their specific domain types. New wrappers sanitize exceptions
only at the injected embedder/index dimension, embedding and search callbacks,
translating to actionable fixed `RagRetrievalError` messages. They validate batch
dimension and issued-query/result association, while Story 7 validates count,
merge and orientation. `generate` confines broad handling to the arbitrary
injected generator callback and translates failure to `GenerationOperationError`.
Malformed returned contracts/citations raise `GenerationError`. LangChain keeps
domain exceptions intact and sanitizes unexpected third-party runtime failures
as `LangChainIntegrationError`.

Sensitive callback/provider exception chains are suppressed with `from None`.
Public errors never include supplied query, document, credentials or payloads.
No BaseException is caught; interrupts propagate. Python retains private
exception context internally, so consumers must not serialize exception internals.
Data-bearing request/result fields are excluded from default representations.

`test_story8.py` covers deterministic component composition, both score
orientations, transformed-query attribution, dedup, exact provenance, bounded
generation context, empty context, immutable policy, corpus refresh, genuine
framework execution, configuration/query/output limits, malformed output and
citations, adapter faults, cross-stage inconsistency, non-finite score rejection,
callback failures, public diagnostic privacy, SDK isolation and the runnable
example. Adversarial text/metadata cases exercise all six requested instruction
styles through both paths, checking unchanged application policy/environment,
unchanged source metadata, no marker-file execution, and unchanged fixed
instruction. Generated instructions are also tested as inert output in both paths.

Every new test blocks socket connect/connect_ex/create_connection and removes
OpenAI, Pinecone, and LangSmith credentials. No wall-clock timing assertions,
compatibility shims, fake packages, weakened tests, or network model calls exist.

## Offline example and freshness interpretation

Run `uv run python module-03/examples/rag_freshness.py`.

The example ingests a library bulletin, chunks it, embeds it with the accepted
`LocalHashEmbedder(64)`, and constructs real FAISS snapshots. It decomposes a
compound query, retrieves/merges, selects bounded context and generates an
inspectable answer. It prints original/derived queries, scores, IDs, offsets,
query attribution, exact context, answer, generator/model and citations.

Without evidence, the unchanged generator reports unknown. Corpus A supplies
09:00; rebuilding the same declared source as corpus B supplies 07:00. The same
generator instance and unchanged generation implementation produce the new
answer without retraining or model modification. LangChain then reproduces B.
Source ID stays stable while document/chunk IDs change with source content.

This demonstrates that retrieval can improve knowledge freshness when the
indexed/retrieved source corpus itself is refreshed. It does not establish truth,
source authentication, semantic quality, automatic freshness, contradiction
resolution, or a remote model's pretraining cutoff. `LocalHashEmbedder` is a
deterministic lexical-hash stand-in, not a trained semantic embedding model.

## Exclusions and review scope

No Story 9 Streamlit/presentation work, Story 10 final requirement matrix,
README roadmap completion, release documents/tags/publishing, new provider
integrations or unrelated refactors. Modules 1/2 and accepted Stories 1–7
behavior are preserved. Only additive error classes change an existing source
file. `ARCHITECTURE.md` and `SOURCE_REQUIREMENTS.md` are unchanged.

Files: new `generation.py`, `rag_pipeline.py`, `langchain_rag.py`,
`test_story8.py`, `examples/rag_freshness.py`, and this document;
modified `errors.py` only. Nothing is staged or committed.

## Repair and environment record

Initial targeted Ruff findings were unused imports, line length and default
config constructor calls. Safe `ruff check . --fix` removed unused imports;
formatting wrapped new files; immutable module-level default configs resolved
B008 without changing accepted code. The bounded-context test arithmetic was
corrected to 22 characters before its initial test run.

The initial targeted pytest run had 83 passes, one assertion failure and eight
setup errors. Oversized automatically generated test IDs caused setup problems;
short explicit case IDs corrected them without changing the tested inputs.
Python 3.12 frozen/slots property assignment raises TypeError, so the immutability
test accepts that specific rejection as well as FrozenInstanceError and verifies
the fixed instruction remains unchanged. The next targeted run passed 88 cases.
Adding the second generated-output path brought the focused suite to 89 cases.

Later sandbox calls could not access uv's default cache or pytest's default
temporary/cache directories. Local environment overrides direct UV_CACHE_DIR
to workspace `.uv-cache` and PYTEST_ADDOPTS to dedicated `.uv-cache` basetemp
and cache_dir paths, preserving dependency/tool configuration and tests. The
affected targeted run had 74 passes and 15 setup errors; it is not counted as
a passing gate. The relocated targeted run passed all 89 cases. No approval,
system-directory modification, dependency shim, or repository configuration
change was needed.

## Authoritative final verification

On October 3, 2026, on the real installed Python 3.12.14 environment, the
required sequence passed in order (no diagnostic harness or package stand-ins):

1. `uv run ruff check .` — exit 0, all checks passed.
2. `uv run pytest` — exit 0, **1024 passed, 3 warnings in 17.09s**.
3. `uv run python -m compileall module-01 module-02 module-03` — exit 0.
4. `git diff --check` — exit 0.

The complete suite includes all 935 accepted cases and 89 added Story 8 cases.
The focused suite separately passed **89/89** with sockets blocked and provider
credentials removed. The sole new offline example passed as a direct invocation
and under those blocked-network test conditions. The three warnings are the
existing Chroma `DeprecationWarning: legacy embedding function config` from
Story 6 metric/configuration tests. No Story 8/LangChain deprecation was observed.

The runtime-only overrides were:

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
$env:PYTEST_ADDOPTS = '--basetemp=.uv-cache/pytest-story8-final -o cache_dir=.uv-cache/pytest-cache'
```

No dependencies, quality rules, frozen documents, or accepted tests were changed.
HEAD remains `0d0bcd8df67779828d48dee8adfefa5bbc95f6dc` on
`feature/module-03`. The expected review state is one unstaged modified file
(`errors.py`) and six untracked Story 8 files. No staging/commit/history operation
was performed.

## Exact offline example output

`uv run python module-03/examples/rag_freshness.py` prints:

```text
Without retrieved evidence: Unknown: no reference evidence supplied.
Corpus A: integration=core
  original_query='  Atlas opening hours; Atlas schedule  '
  transformed='Atlas opening hours' technique=decompose
  transformed='Atlas schedule' technique=decompose
  chunk_id=chunk-v1-3769f408247dc4861bc5f1e58a486ae13841240a488ed7bd933f4bd87ae03c13
  document_id=doc-v1-72732ea420127b8fcc07b0d26ef571354e6212bd1fa734f98cd99cda864b3b30
  source_id=769731a775310e2605235a358ad5e138dbfd5553e862beb5291866a620ca6568
  offsets=[0,41) score=0.365148
  produced_by=('Atlas opening hours', 'Atlas schedule')
  context_characters=41 budget=256
  optimized_context=('Atlas library opens at 09:00 on weekdays.',)
  answer='Atlas library opens at 09:00 on weekdays.'
  generator=local-extractive model=verbatim-v1 citations=('chunk-v1-3769f408247dc4861bc5f1e58a486ae13841240a488ed7bd933f4bd87ae03c13',)
Corpus B: integration=core
  original_query='  Atlas opening hours; Atlas schedule  '
  transformed='Atlas opening hours' technique=decompose
  transformed='Atlas schedule' technique=decompose
  chunk_id=chunk-v1-72b1faf5c88ba24c10efe242a40a54aba94177b8fa23317f2eebaadbe3bf0d4d
  document_id=doc-v1-4eb5517291d611efd47f33d2d31eacff4dc4cd3c925cabba14618c3cab0d3bc9
  source_id=769731a775310e2605235a358ad5e138dbfd5553e862beb5291866a620ca6568
  offsets=[0,41) score=0.223607
  produced_by=('Atlas opening hours', 'Atlas schedule')
  context_characters=41 budget=256
  optimized_context=('Atlas library opens at 07:00 on weekdays.',)
  answer='Atlas library opens at 07:00 on weekdays.'
  generator=local-extractive model=verbatim-v1 citations=('chunk-v1-72b1faf5c88ba24c10efe242a40a54aba94177b8fa23317f2eebaadbe3bf0d4d',)
LangChain corpus B: integration=langchain
  original_query='  Atlas opening hours; Atlas schedule  '
  transformed='Atlas opening hours' technique=decompose
  transformed='Atlas schedule' technique=decompose
  chunk_id=chunk-v1-72b1faf5c88ba24c10efe242a40a54aba94177b8fa23317f2eebaadbe3bf0d4d
  document_id=doc-v1-4eb5517291d611efd47f33d2d31eacff4dc4cd3c925cabba14618c3cab0d3bc9
  source_id=769731a775310e2605235a358ad5e138dbfd5553e862beb5291866a620ca6568
  offsets=[0,41) score=0.223607
  produced_by=('Atlas opening hours', 'Atlas schedule')
  context_characters=41 budget=256
  optimized_context=('Atlas library opens at 07:00 on weekdays.',)
  answer='Atlas library opens at 07:00 on weekdays.'
  generator=local-extractive model=verbatim-v1 citations=('chunk-v1-72b1faf5c88ba24c10efe242a40a54aba94177b8fa23317f2eebaadbe3bf0d4d',)
Same generator instance/configuration; no retraining or model modification.
Proves: refreshing the indexed corpus changes retrieved evidence and answer.
RAG improves freshness only when its source corpus is refreshed; not truth.
LocalHashEmbedder is a deterministic lexical-hash stand-in, not a trained
semantic embedding model. LocalExtractiveGenerator copies evidence verbatim;
it is a demonstration/test implementation, not a production semantic model.
```
