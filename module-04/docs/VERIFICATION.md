# Module 4 Verification Record

This record holds the final Story 12 verification evidence for Module 4. The
mapping from requirements to evidence is in [TRACEABILITY.md](TRACEABILITY.md).

## Environment

Gates were run on 2026-10-08 against a mirror of the Story 12 working tree:

- The Modules 1-3 tree came from commit `fcd9c8e`.
- The mirror also carried the working-tree `pyproject.toml`, `uv.lock`,
  `module-02/tests/test_package_contract.py`,
  `module-03/tests/test_closeout.py`, and the full Story 12 `module-04/`.
- It ran on Linux with Python 3.13.16 after `uv sync --frozen`, with
  `HF_HUB_OFFLINE=1`.
- `module-05/` (untracked, out of scope) was not present.

`git diff --check` and the untracked-file whitespace check ran on the
authoritative working tree itself. Earlier story gates ran on Windows with
Python 3.12; this record does not claim a Windows re-run.

## Fail-fast quality gates

| # | Gate | Result |
| --- | --- | --- |
| 1 | `ruff check module-01 module-02 module-03 module-04` | All checks passed (exit 0) |
| 2 | `pytest` (full suite, `-p no:cacheprovider`) | **1844 passed, 3 warnings**, 44.86 s (exit 0). The warnings are the existing ChromaDB `DeprecationWarning`s from `module-03/tests/test_story6_stores.py`. |
| 3 | `python -m compileall -q module-01 module-02 module-03 module-04/src module-04/tests module-04/examples module-04/app.py` | exit 0 |
| 4 | `git -c core.autocrlf=true diff --check` (the repository's Windows setting), plus `git diff --no-index --check`, CR, and final-newline scans of all 66 untracked `module-04/` files | `diff --check` exit 0 (LF→CRLF notices only). The 8 Story 12 files are clean. Four earlier Module 4 files have only CRLF line endings and no other whitespace issue (see note). |
| 5 | Rule 44: `module-04/tests/test_module_isolation.py`, plus a grep for imports of Module 1-3 packages across `module-04/**/*.py` | 13 passed; 0 import matches |

**Ruff scope.** The 2026-10-08 human decision records the formal Ruff gate
as Modules 1-4. Repository-wide `ruff check .` on the authoritative tree is
blocked only by two B017 findings in the untracked, out-of-scope
`module-05/`. In the mirror, which has no `module-05/`, `ruff check .` also
passed.

**Line-ending note (gate 4).** `src/advanced_rag_evaluation/advanced_rag_pipeline.py`
and `tests/test_generation.py` (Story 10), `src/advanced_rag_evaluation/observability/__init__.py`
(Story 8), and `docs/STORY_08.md` (2 of 115 lines) contain CRLF line endings.
They have no other trailing whitespace. Without `core.autocrlf` the CRs read
as trailing whitespace, but `core.autocrlf=true` normalizes them at commit.
Story 12 did not change these files; line-ending normalization is a release
step. The same applies to the CRLF working copy of
`module-02/tests/test_package_contract.py`.

**Module 4 tests: 789.**

| Test file | Tests |
| --- | --- |
| `test_ragas_evaluation.py` | 140 |
| `test_langfuse_monitoring.py` | 74 |
| `test_semantic_retrieval.py` | 70 |
| `test_cost.py` | 58 |
| `test_latency.py` | 58 |
| `test_generation.py` | 54 |
| `test_bm25.py` | 48 |
| `test_reranking.py` | 43 |
| `test_retrieval_cache.py` | 42 |
| `test_dynamic_retrieval.py` | 40 |
| `test_hybrid_retrieval.py` | 38 |
| `test_context_filtering.py` | 33 |
| `test_advanced_rag_pipeline.py` | 30 |
| `test_langsmith_tracing.py` | 24 |
| `test_app.py` | 23 |
| `test_module_isolation.py` | 13 |
| `test_package_contract.py` | 1 |

## Offline demonstrations

All nine offline demos ran with `python module-04/examples/<name>.py` and
exited 0:

| Demo | Key output |
| --- | --- |
| `bm25_search.py` | Ranked BM25 results for two queries |
| `hybrid_search.py` | BM25 and ChromaDB legs fused by RRF |
| `reranking_demo.py` | Deterministic reranking with pre-rerank evidence |
| `optimization_demo.py` | Dynamic decision; cache `from_cache=False`, then `True`, then `False` (2 retrieve calls for 3 queries); filtering |
| `telemetry_demo.py` | Latency budgets; actual and estimated cost |
| `hybrid_rag_workflow.py` | End-to-end answer with a citation; second run `from_cache=True` |
| `ragas_evaluation_demo.py` | Faithfulness / context precision / relevancy: supported 1/1/1, mixed-reordered 0.5/0.5/1, evasive 0/1/0 (`ragas=0.3.1`, `deterministic_offline`) |
| `langsmith_tracing_demo.py` | `sdk=0.14.3 success=True requests=6 children=2`; remote delivery verified: False |
| `langfuse_monitoring_demo.py` | `sdk=4.15.4 success=True requests=1 spans=2`; remote delivery verified: False; points to `module-04/app.py` section 11 |

`cross_encoder_verification.py` was not run. It is the explicit opt-in path
that downloads a Hugging Face model. One genuine model run is recorded in
[STORY_04.md](STORY_04.md).

## What is not verified live (final approved scope)

- **LangSmith and LangFuse remote delivery.** Final approved limitation
  (HITL-1). The SDK integrations are genuine and verified offline only.
- **Pinecone service behaviour.** Final approved limitation (HITL-3).
  "Live service verification not yet performed". The genuine SDK boundary
  is verified offline with an injected client.
- **Provider-backed RAGAS judge.** The boundary exists and is tested with
  offline doubles. Dashboard RAGAS uses curated replay judgments only.
- **LLM generation and actual token cost.** Generation is extractive. Cost
  is a labelled estimate at fixture pricing.
- **Learned semantic similarity.** `HashEmbedder` measures token overlap.

## Release gates (Windows, 2026-10-08)

The governed Module 4 release closeout re-ran the gates on the authoritative
Windows working tree with Python 3.12, `uv run --locked`, and
`HF_HUB_OFFLINE=1`. This was after the documentation, README roadmap, and
Module 3 closeout assertion were reconciled. No model-download or
live-provider path was run.

| # | Gate | Result |
| --- | --- | --- |
| 1 | `ruff check module-01 module-02 module-03 module-04` | All checks passed (exit 0) |
| 2 | `pytest -q -p no:cacheprovider` (full suite) | **1844 passed, 3 warnings** (the existing ChromaDB `DeprecationWarning`s), exit 0 |
| 3 | `python -m compileall -q module-01 module-02 module-03 module-04/src module-04/tests module-04/examples module-04/app.py` | exit 0 |
| 4 | `git diff --check`, plus `git diff --no-index --check` (CR at end of line allowed) and final-newline checks of all 66 untracked `module-04/` files | exit 0; 0 issues. The four CRLF files noted above are unchanged and are normalized by `core.autocrlf=true` at commit. |
| 5 | Rule 44: `module-04/tests/test_module_isolation.py`, plus a grep for imports of Module 1-3 packages across `module-04/**/*.py` | 13 passed; 0 import matches |
| 6 | Requirement status and Definition of Done | 29 IDs in `SOURCE_REQUIREMENTS.md` and `TRACEABILITY.md`: 26 Complete, 3 Complete — approved limitation, 0 Partial, 0 Missing. Definition of Done: 27 of 27 checked. |
| 7 | Root `README.md` roadmap | Modules 1-4 ✅ Complete; Modules 5-12 Planned |
| 8 | `git status` | Only the intended release files changed; `module-05/` and local evidence files are excluded from the release |

## Manual Streamlit verification (human checkpoint)

This is the final human-facing check before release, required by
M4-PORT-01. The human performed it on the Windows repository environment
and recorded the result as **PASS** on 2026-10-08. No agent performed or
re-ran it.

Start the app with:

```
uv sync --locked
uv run streamlit run module-04/app.py --browser.gatherUsageStats false
```

The human verification established that:

- the dashboard launches successfully on the Windows repository environment;
- the initial page is self-explanatory and usable;
- the sidebar is appropriately control-focused;
- the complete default Scenario 1 workflow executes and renders all 12
  dashboard sections;
- answer/citation, retrieval, reranking, filtering, latency, cost, RAGAS,
  LangSmith, LangFuse and failure-analysis evidence render correctly;
- adversarial retrieved text remains displayed as untrusted data rather
  than being treated as instructions;
- retrieval caching works: the first run was uncached and the second
  identical run reported `from_cache=True`.

The checklist below was prepared at Story 12. Each row records what the
human report itemised. Rows it did not itemise individually stay covered by
the automated `tests/test_app.py` evidence and fall under the overall PASS.

| # | Check | Result |
| --- | --- | --- |
| 1 | The page starts with no credentials and no `.env`; the sidebar guidance renders | Pass (launch, self-explanatory page, control-focused sidebar) |
| 2 | The three curated scenarios render sections 1–12 with Expected / Actual / Why. RAGAS shows 1/1/1, 1/0.5/1, and 1/1/0.408248. | Pass for the default Scenario 1 (all 12 sections, RAGAS evidence); Scenarios 2–3 not itemised |
| 3 | A repeated run shows `from_cache=True`; **Clear retrieval cache** makes the next run a miss | Pass (first run uncached, second `from_cache=True`); the clear-cache step was not itemised |
| 4 | A custom query, and a changed filter on a curated scenario, both show RAGAS *Not evaluated* | Not itemised |
| 5 | Reranking fault: only provenance and failure analysis show (`reranking`, `fatal=True`) | Not itemised (failure-analysis evidence rendered correctly) |
| 6 | LangSmith and LangFuse faults are nonfatal (`result_usable=True`) and the answer is kept | Not itemised (LangSmith and LangFuse evidence rendered correctly) |
| 7 | Provenance shows `remote_delivery_verified=False`, Pinecone *Unavailable*, cost *Estimate* | Not itemised |
| 8 | The adversarial passage renders as inert text (no image or script) | Pass |
| 9 | Optional (downloads a model): the cross-encoder opt-in caption is visible before activation, the threshold is disabled, and the reranker is labelled *Genuine local model (opt-in)* | Not performed (optional model download) |

**Overall result: PASS** (human, 2026-10-08). M4-PORT-01 is `Complete`.
