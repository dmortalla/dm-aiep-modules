# Story 7: Genuine RAGAS evaluation

Implements the evaluation boundary against the frozen source requirements,
the human-approved architecture (including the Story 5 amendment), and the
human-accepted Story 1–6 baseline of **1416 passed / 0 failed**. Published
Modules 1–3, accepted Story 1–6 code and documentation, the 29 frozen
requirement IDs/content/statuses, and architecture decisions remain unchanged.
Only evaluation-domain error subclasses are appended to the existing Module 4
error hierarchy. Story 1's historical acceptance remains 1056 passed / 0 failed.

## Scope and requirement evidence

| Requirement | Story 7 implementation and deterministic evidence |
| --- | --- |
| M4-EVAL-01 | Real `ragas.metrics.Faithfulness.single_turn_ascore`: RAGAS generates statements, obtains support judgments, and calculates the supported-statement proportion. Tests exercise 1, 0.5, and 0 outcomes. |
| M4-EVAL-02 | Real `LLMContextPrecisionWithReference.single_turn_ascore`: one usefulness judgment per ordered retrieved context, with RAGAS computing average precision against the explicit reference answer. Tests distinguish useful-first (approximately 1) from useful-second (approximately 0.5), and all-irrelevant (0). |
| M4-EVAL-03 | Real `ResponseRelevancy.single_turn_ascore`: RAGAS generates relevance questions, uses injected embeddings, and computes cosine similarity with its noncommittal-answer multiplier. Tests cover identical/unrelated questions and an evasive answer. |
| M4-TOOL-01 | The real pinned RAGAS package executes all three public metric methods, original prompt generation/parsing, and original metric calculations. Method spies assert actual `ragas.metrics.*` origins while forwarding to the real implementations. No metric formula is implemented in Module 4. |
| M4-LAB-02 | Credential-free executable [ragas_evaluation_demo.py](../examples/ragas_evaluation_demo.py) evaluates three cases and prints expected/actual results with deterministic/offline labels. The later UI portion of the frozen lab evidence remains assigned to Story 11. This story does not claim complete UI evidence. |

The frozen requirements matrix remains unchanged, including its Pending
statuses. This per-story record supplies implementation evidence without
performing Story 12 traceability/closeout work.

## Files and integration boundary

- [ragas_adapter.py](../src/advanced_rag_evaluation/evaluation/ragas_adapter.py):
  validated immutable `EvaluationCase`, `EvaluationConfig`, `EvaluationScores`,
  `EvaluationResult`, `ReplayReply`, `ReplayJudge`, and `JudgeCall`; the
  provider-neutral `Judge` protocol, configured `RagasEvaluator`, and
  `build_replay_judge` fixture helper.
- [_ragas_runtime.py](../src/advanced_rag_evaluation/evaluation/_ragas_runtime.py):
  lazy RAGAS bridge, strict raw model-output validation, public metric execution,
  and reuse of the existing Module 3 `Embedder`/`EmbeddingBatch` contracts.
- [evaluation/__init__.py](../src/advanced_rag_evaluation/evaluation/__init__.py):
  package marker with no SDK initialization.
- [errors.py](../src/advanced_rag_evaluation/errors.py): appends `EvaluationError`,
  `EvaluationInputError`, `EvaluationIntegrationError`, `EvaluationResultError`.
- [test_ragas_evaluation.py](../tests/test_ragas_evaluation.py): deterministic
  integration, validation, failure, provenance, security, and demo tests.
- [ragas_evaluation_demo.py](../examples/ragas_evaluation_demo.py): executable lab.
- Root `pyproject.toml`/`uv.lock`: necessary RAGAS dependency integration.
- This `STORY_07.md`: implementation, limitations, and verification record.

Evaluation consumes an ordered tuple of the existing Module 3 `DocumentChunk`
objects. Optional `FilteredContext` evidence retains the exact original Story 5
object and requires identical retained chunk objects in identical order. The
composition test uses genuine BM25, FAISS semantic retrieval, hybrid fusion,
reranking, and filtering, retaining the full upstream evidence graph. There is
no synthetic Module 3 `RetrievalCandidate` adapter and no call to its
`optimize_context`; the Story 5 amendment is preserved.

## Deterministic versus provider-backed evidence

The mandatory path uses exactly `ReplayJudge` and Module 3 `LocalHashEmbedder`.
The judge matches complete RAGAS-generated prompts to explicitly supplied JSON
responses. It performs no semantic judgment or metric calculation. The helper
builds those prompts using the pinned RAGAS prompt models, rather than routing
on instructions in evaluation content. Relevance embeddings are genuine local
hash vectors from the accepted Module 3 implementation, not trained semantic
embeddings. The resulting classification is `deterministic_offline`, with
`exact-prompt-replay-v1` and the actual local embedding dimension recorded.

Any different injected model type requires `allow_provider_backed=True` and
explicit identifiers appropriate to its actual type. The provider-neutral
application-supplied asynchronous `Judge.complete` and existing Module 3
`Embedder.embed` are the extension boundaries. Neither evaluation content nor
model output can enable this opt-in, select a model, or configure credentials
or a destination. There is no automatic default provider or fallback.

An application that has separately configured its models can use:

```python
result = await RagasEvaluator(
    configured_judge,
    configured_embedder,
    judge_id="application-selected-judge",
    embedding_id="application-selected-embedding-model",
    allow_provider_backed=True,
).evaluate(case)
```

This path is tested with **offline provider doubles**, including failure and
timeout cases. **No live/provider-backed remote verification was performed.**
The `provider_backed` label describes the explicitly selected model boundary;
it is not independent attestation that an arbitrary injected implementation
actually contacted a remote provider. Future live evidence must identify the
actual configured provider/models and execution separately. No standalone
vendor-specific live script or new provider credential policy was introduced.

## Dependencies and compatibility findings

Before dependency edits, both the root manifest and lockfile were inspected.
The final manifest adds only `ragas==0.3.1` and
`langchain-community==0.3.31`, without extras. Exact pins make the prompt/API
boundary reproducible and prevent the resolver selecting incompatible newer
families. The compatibility pin is an engineering dependency selection, not
a change to source requirements or approved architecture.

RAGAS 0.4.3 was first attempted; resolution failed because its `instructor`
dependency requires an older `jiter` family than accepted OpenAI 3.22.1.
RAGAS 0.2.15 then resolved but failed to import against LangChain Community
0.4.2, which removed the imported VertexAI module. That dependency experiment
was undone, and inspection hashes confirmed the original files/lock state
were restored before the compatible combination was selected. Official
metadata established that RAGAS 0.3.1 does not require `instructor` and
Community 0.3.31 permits the accepted LangChain 1.x versions. The final
combination imports and executes real metrics successfully.

Existing OpenAI 3.22.1, LangChain 1.4.3, LangChain Core 1.6.6, and all other
existing locked versions remain unchanged **except `fsspec`, lowered from
2026.9.0 to 2026.7.0** by Datasets 5.1.0's declared upper bound. No repository
module directly uses `fsspec`; this necessary transitive change is disclosed
and verified through the full regression suite. No dependency override,
ignored constraint, SDK shim, vendor patch, or accepted source repair was used.

The lockfile adds 16 packages:

```text
appdirs 1.4.4                 dataclasses-json 0.6.7
datasets 5.1.0               dill 0.4.1
diskcache 5.6.3              httpx-sse 0.4.3
langchain-community 0.3.31   langchain-openai 1.6.7
marshmallow 3.26.2           multiprocess 0.70.19
mypy-extensions 1.1.0        nest-asyncio 1.6.0
ragas 0.3.1                  sqlalchemy 2.1.3
tiktoken 0.14.0              typing-inspect 0.9.0
```

RAGAS declares the transitive OpenAI/LangChain adapters; they are not a
hardcoded provider choice by Module 4. Its optional tracing/test-generation
extras are not enabled. No LangSmith tracing or LangFuse implementation is
introduced by Story 7.

Primary compatibility/metric references:
[RAGAS 0.3.1 metadata](https://pypi.org/pypi/ragas/0.3.1/json),
[Community 0.3.31 metadata](https://pypi.org/pypi/langchain-community/0.3.31/json),
[RAGAS metrics reference](https://docs.ragas.io/en/v0.3.1/references/metrics/).
The installed pinned source was also inspected directly before implementation.

## Security and authority evidence

- Query, answer, reference, retrieved text, prompt, JSON judgment, and reasons
  remain untrusted data. No `eval`, `exec`, unsafe deserialization, dynamic
  imports derived from content, shell execution, or content-derived credentials,
  configuration, paths, or network destinations exist in the implementation.
- Inputs are bounded Unicode strings; contexts are 1..64 unique validated
  chunks, at most 32768 UTF-8 bytes each and 524288 bytes combined. Empty
  contexts are explicitly rejected as undefined for this boundary; Story 5's
  valid empty-filtered result is not changed.
- Judge responses are bounded raw JSON. Before RAGAS parsing, validation rejects
  duplicate/unknown keys, type coercion, nonbinary/bool verdicts, blank text,
  changed/dropped/reordered NLI statements, and schema mismatches. Output
  validation strengthens trust handling without replacing metric algorithms.
  The schema comes from the fixed pinned RAGAS prompt template, not data.
- Finite, ordered, nonzero embedding batches are required. RAGAS scores retain
  their actual values, including relevance's cosine domain [-1, 1]. The 1e-12
  domain tolerance handles roundoff without clipping. NaN, infinity, wrong
  types, or invalid ranges produce errors rather than default/partial success.
- Prompts/completions and original chunk objects are retained as explicit
  repr-hidden evidence. They are accessible for deliberate inspection but do
  not acquire authority. No raw evaluation content is printed by the lab.
- Provider/SDK failures and asynchronous metric timeouts are wrapped in
  actionable, content-safe errors with exception chaining; cancellation
  propagates. No live fallback follows offline fixture failure.
- RAGAS usage tracking is disabled by fixed process-wide application policy
  (`RAGAS_DO_NOT_TRACK=true`, clearing the SDK's cached decision). Explicit empty
  callback managers prevent inherited automatic tracing. The isolated demo test
  supplies hostile tracing configuration and blocks outbound sockets throughout
  import/scoring/shutdown. On Windows, the test permits only asyncio's internal
  socketpair construction, not application/provider loopback traffic.
- Injection tests include schema/input-marker-shaped text, instructions to
  write a file, choose a hostile endpoint, source credentials, import/execute
  code, and change strictness. They assert unchanged configuration, no file
  creation/network use, retained exact data, and repr safety.

## Demonstration and limitations

Run `uv run python module-04/examples/ragas_evaluation_demo.py`.

| Case | Faithfulness | Context precision | Response relevance |
| --- | --- | --- | --- |
| Supported answer, useful context first | 1 | approximately 1 | approximately 1 |
| One unsupported claim, useful context second | 0.5 | approximately 0.5 | approximately 1 |
| Evasive answer | 0 | approximately 1 | 0 |

These actual outputs were observed through genuine RAGAS execution. Each case
made seven judge calls at default strictness 3: two faithfulness calls, two
context-usefulness calls, three relevance-question calls. Precision's small
epsilon and cosine roundoff are retained, not normalized into invented scores.

Limitations: replay judgments and local hash embeddings prove integration and
determinism, not real semantic assessment quality. Context precision requires
an explicit reference answer; no reference synthesis is performed. The bridge
depends on pinned RAGAS prompt models and template format; future upgrades
require integration verification. RAGAS's public metric method still creates
its fixed local analytics identity/buffer internally, but tracking is disabled
and no evaluation data controls that filesystem destination. The async timeout
cancels asynchronous judge work; a synchronous injected Module 3 Embedder must
enforce its own provider I/O timeout, since Python cannot interrupt a blocking
sync provider call through this metric API. No hard cancellation of synchronous
embedding I/O is claimed.

Story 8 tracing, Story 9 monitoring/failure analysis, Story 10 orchestration,
Story 11 UI, Story 12 closeout, unrelated refactors, and generalized agent/skill
files remain out of scope and untouched.

## Tests and repair-loop activity

140 new collected tests in `test_ragas_evaluation.py` cover genuine metrics and
their call paths, exact replay determinism, strictness, reference selection,
numeric domains, malformed judge/SDK/embedding output, input budgets,
integration failures, asynchronous timeouts/cancellation, opt-in enforcement,
labels, immutable original provenance, injection-shaped data, SDK-independent
imports, and the isolated runnable demo.

Bounded repairs were confined to this story's additions: mechanical Ruff
format/import fixes; correcting the Windows self-pipe network guard; correcting
new test assumptions to use Module 3's actual Vector-based `SearchQuery` and
hashed provenance properties; and validating each SDK score before proceeding
to later metrics. No existing test was weakened or edited. The failed
dependency experiments above were replaced by a compatible dependency choice,
without changing accepted OpenAI/LangChain contracts. No unsafe Ruff fix used.

## Results — October 5, 2026

Complete fail-fast quality-gate sequence:

1. `uv run ruff check .` — exit 0, all checks passed.
2. `uv run pytest` — exit 0, **1556 passed / 0 failed**, three existing ChromaDB
   deprecation warnings, in **31.62s**. This is the accepted 1416-case baseline
   plus 140 new Story 7 cases; no regressions or skipped cases.
3. `uv run python -m compileall module-01 module-02 module-03 module-04` —
   exit 0, successful compilation.
4. `git diff --check` — exit 0, no whitespace errors. Git emitted only existing
   LF-to-CRLF normalization notices for working-tree files.

The credential-free demonstration was also executed directly and produced the
expected three score sets recorded above. Its isolated contract test exercises
the same runnable script with outbound sockets blocked and no credentials.

## Training observations

- **Agent policy:** inspect both declared dependency compatibility and actual
  imports before considering an accepted-contract change. A failed newest-version
  resolution does not establish that every genuine integration requires a
  semantic repair; inspect compatible releases before escalating.
- **Reusable provider-neutral skill:** keep judge completion and ordered
  embedding generation injectable; replay structured model outputs while the
  genuine evaluation library computes scores. Retain original evidence objects
  and distinguish configured-provider labels from independently verified live
  execution.
- **Deterministic automation:** exercise public SDK methods under outbound-network
  guards, verify executable demos in isolated processes, and accommodate only
  the operating system's internal asyncio socketpair construction. Validate raw
  model JSON before coercion and compare frozen-file hashes after changes.
- **Human authority:** no accepted behavior, architecture amendment, source
  interpretation, or human-approved decision required repair. Dependency pins,
  reference-based precision, relevance metric selection, and bounded input
  conventions are implementation choices within the approved Story 7 scope.
  Independent human acceptance remains outstanding; no commit, merge, tag,
  release, or Story 8 work has been performed.
