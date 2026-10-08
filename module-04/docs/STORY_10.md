# Story 10 — End-to-end hybrid RAG orchestration and generation

Status: implemented for independent human review. Stories 1–9 and the Rule 44
isolation remediation are accepted. Authority: SOURCE_REQUIREMENTS.md, frozen
ARCHITECTURE.md with its Story 5 and Rule 44 amendments, then accepted evidence
contracts. The generation/orchestration file placement and error split were
accepted by human review and recorded as the 2026-10-08 Story 10 placement
amendment in ARCHITECTURE.md. Story 11/12 work is not included.

## Requirement evidence

| Requirement | Implementation and evidence |
| --- | --- |
| M4-LAB-01 | `advanced_rag_pipeline.run_hybrid_rag` runs the full workflow into an independent `HybridRagResult`; `examples/hybrid_rag_workflow.py` is the runnable offline lab. UI demonstration is Story 11. |
| M4-DEL-01 | The orchestration composes every accepted stage with cross-validated evidence; documentation and traceability close in Story 12. |
| Approved Resolution 1 | `HybridRagResult` is Module 4's own orchestration type; generation is Module 4-owned (`generation.py`), per the Rule 44 amendment. |
| Approved Resolution 8 | Generation cost uses generator-reported actual usage when present, otherwise a labeled `character-ratio-v1` estimate. |

## Generation boundary (`generation.py`)

`GenerationRequest(query, context)` takes Story 5's `FilteredContext` directly
and retains it by identity. No Module 3 type (`OptimizedContext`,
`ContextItem`, `RetrievalCandidate`) is imported, imitated, or translated to;
no intermediate context type is introduced. Inputs are bounded to the same
limits as Story 7's `EvaluationCase` (64 items, 524288 context bytes, 32768
query/answer bytes).

`AnswerGenerator` is the provider-neutral boundary (`generator_id`,
`generate(request) -> GeneratorOutput`). `ExtractiveAnswerGenerator`
(`module-4-extractive:v1`) is deterministic and credential-free: for the
leading retained items in filter order it quotes the sentence with the most
query-term overlap and adds a `[n]` marker. It is not a language model.
The Module 4 source names no generation model or provider, so no provider
adapter was added; an application may inject one through the boundary.

`generate_answer` abstains with fixed text, without calling the generator,
when no context was retained. Otherwise generator output must be an exact
`GeneratorOutput` whose cited identifiers are all retained chunks; each
becomes a `Citation` holding the `ContextFilterItem` by identity, so the
filter order, rerank rank/score, RRF score, both legs' rank/score, and chunk
provenance stay reachable without copying. `GeneratedAnswer` re-validates
that every citation is a retained item of its own request, markers are
contiguous, and abstention is used exactly when the context is empty.

Every generation failure is the accepted `GenerationError`, with fixed
messages and no chained generator exception, matching the remediation's
`SemanticProviderError` precedent. Only its docstring was updated. A new
`HybridRagError` covers orchestration configuration and result evidence.

## Orchestration (`advanced_rag_pipeline.py`)

Stages, each timed with Story 6 `measure_stage`: `dynamic_retrieval`,
`retrieval` (BM25 + semantic leg, RRF fusion, optional Story 5 cache),
`reranking`, `context_filtering`, `generation`. The dynamic decision sets the
fusion and rerank `top_k`. A stage failure is caught at its boundary and
re-raised as `HybridRagStageFailure` carrying Story 9's `FailureAnalysis`
(the result-availability fact Story 9 left to this story), with the stage's
domain error as cause. `HybridRagResult` re-validates the identity chain
(retrieval → reranked → context → answer), the shared query, and the exact
stage list. `to_evaluation_case` builds a Story 7 case from the retained
chunks and `FilteredContext` by identity; `result.latency` feeds the Story 8/9
adapters unchanged.

## Security

Retrieved text and generator output are inert data. No generator output,
citation, or retrieved text selects configuration, stages, models,
credentials, or control flow; fabricated citations or citations of excluded
chunks are rejected. Result and answer `repr`s exclude query, chunk, and
answer text.

## Tests

`tests/test_generation.py` (54) and `tests/test_advanced_rag_pipeline.py` (30)
cover normal generation, determinism, abstention, injected generators, usage
labels, sanitized failures, malformed/fabricated output, provenance reach,
end-to-end composition, caching, cost, stage-failure classification, result
validation, genuine RAGAS scoring and offline LangSmith tracing of a pipeline
result, the offline demo, and Rule 44 import isolation. The permanent
`test_module_isolation.py` guard also scans the new files.

## Residual risks

- An injected generator call is synchronous and not time-bounded; output size
  is bounded after return.
- One retrieval cache must serve one index pair; keys do not encode index
  identity (unchanged Story 5 contract).
- Extractive answers demonstrate grounding and citation, not abstractive
  answer quality; live provider generation is not implemented or claimed.
