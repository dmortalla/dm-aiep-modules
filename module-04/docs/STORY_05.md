# Story 5: Context filtering, retrieval caching, and dynamic retrieval

Implements `M4-OPT-01`, `M4-OPT-04`, and `M4-OPT-05` against the architecture
and source requirements frozen in Story 1 and Stories 2-4's accepted
contracts. Story 1's architecture, its eight approved human resolutions, and
Stories 2-4's accepted public contracts remain unchanged by this story.
[SOURCE_REQUIREMENTS.md](SOURCE_REQUIREMENTS.md) and
[ARCHITECTURE.md](ARCHITECTURE.md) remain frozen authority and were not
rewritten to match this implementation. All published Modules 1-3 behavior
is unchanged.

Story 4's human-review resolutions are carried forward unchanged: live
cross-encoder verification remains separate from normal gates, and no new
cross-encoder behavior was added this story.

## Scope

- `advanced_rag_evaluation/errors.py`: adds `ContextFilterError`/
  `ContextFilterConfigurationError`, `RetrievalCacheError`/
  `RetrievalCacheConfigurationError`, `DynamicRetrievalError`/
  `DynamicRetrievalConfigurationError`.
- `advanced_rag_evaluation/context_filtering.py`: `ContextFilterConfig`,
  `ContextFilterItem`, `FilterExclusion`, `FilteredContext`,
  `filter_context`.
- `advanced_rag_evaluation/retrieval_cache.py`: `fingerprint_configs`,
  `RetrievalCacheKey`, `CacheLookup`, `RetrievalCache` protocol,
  `InMemoryRetrievalCache`, `CachedRetrieval`, `get_or_retrieve`.
- `advanced_rag_evaluation/dynamic_retrieval.py`:
  `DynamicRetrievalPolicyConfig`, `DynamicRetrievalDecision`,
  `decide_retrieval`.
- `module-04/tests/test_context_filtering.py` (32 tests),
  `test_retrieval_cache.py` (37 tests), `test_dynamic_retrieval.py`
  (40 tests) — 109 new deterministic tests total, built against genuine
  Story 2-4 output.
- `module-04/examples/optimization_demo.py`: credential-free runnable
  demonstration of the full composed pipeline, executed directly as part of
  this story's verification.

## Explicitly excluded from this story

Latency/cost telemetry, pricing tables, token-cost estimation (Story 6),
RAGAS (Story 7), LangSmith (Story 8), LangFuse/failure analysis (Story 9),
the `HybridRagResult` orchestration (Story 10), and the Streamlit dashboard
(Story 11) are not implemented. No weighted fusion, Redis/external cache
infrastructure, or model caching was added. No new cross-encoder behavior
was added. Module 3 source files were not opened for editing.

## M4-OPT-01 implementation evidence (context filtering)

`context_filtering.filter_context(reranked, config)` is exercised by 32
tests: it takes a genuine Story 4 `RerankedResults` (itself built from real
Story 2 BM25 + real Module 3 FAISS semantic + real Story 3 RRF fusion) and
returns a validated `FilteredContext` whose `items`/`excluded` are provably
(a) a deterministic function of input and config
(`test_filtering_is_deterministic`), (b) threshold-correct at the inclusive
boundary (`test_score_exactly_at_threshold_is_retained_inclusive`), (c)
count-capped after thresholding, in existing rank order
(`test_count_cap_applies_after_threshold_in_existing_rank_order`), and (d)
exhaustively reasoned — every non-retained candidate appears in `excluded`
with a fixed reason, and an all-filtered result is explicitly valid
(`test_all_filtered_out_is_a_valid_empty_result`), never an error.

## M4-OPT-04 implementation evidence (retrieval caching)

`retrieval_cache.get_or_retrieve(cache, key, retrieve)` is exercised by 37
tests, including a genuine miss-then-hit sequence over real Story 3
`HybridResults`: `test_first_call_is_a_miss_that_invokes_retrieve_once` and
`test_second_identical_call_is_a_hit_that_never_invokes_retrieve` together
prove a real miss followed by a real hit, with `retrieve()`'s invocation
count asserted directly (not inferred). `test_cache_hit_does_not_strip_or_rewrite_retrieval_evidence`
confirms the hit returns the exact stored object
(`hit.hybrid is original`), not a copy or derivative.

## M4-OPT-05 implementation evidence (dynamic retrieval)

`dynamic_retrieval.decide_retrieval(query, config)` is exercised by 40
tests covering both policy branches, exact-threshold behavior, determinism,
configured bound enforcement, and that the returned `rationale` text
actually names the branch, term count, and threshold that produced the
decision (`TestRationaleReflectsSelectedBranch`), not merely a bare value.

## Context-filter contract and evidence model

- `ContextFilterConfig(min_rerank_score=0.0, max_candidates=10)`:
  `min_rerank_score` is an **inclusive** lower bound compared directly
  against Story 4's `rerank_score`; because that score's scale is entirely
  scorer-dependent (`DeterministicOverlapScorer` returns `[0, 1]`; a genuine
  cross-encoder returns unbounded, often-negative logits), this default of
  `0.0` is only meaningful for a nonnegative-scale scorer. An application
  using the real cross-encoder adapter must supply a scorer-appropriate
  (commonly negative) threshold; `min_rerank_score=float("-inf")` disables
  thresholding entirely, keeping only the count cap.
- `ContextFilterItem` wraps the originating `RerankedCandidate` by reference
  (`field(repr=False)`), exposing `chunk_id`/`document_id`/`hybrid_rank`/
  `rrf_score`/`rerank_rank`/`rerank_score` as read-only delegating
  properties — every one of the fields Story 5's own instructions named for
  preservation, reachable through the exact upstream objects, never copied
  or recomputed.
- `FilteredContext` additionally validates that every retained item
  genuinely originates from the supplied `RerankedResults`
  (`test_rejects_item_not_drawn_from_reranked`), the same cross-stage
  consistency invariant Story 4 added for `RerankedResults` over
  `HybridResults`.
- Candidate chunk *content* is never read by the filtering decision — only
  `rerank_score` (a number) and position among already-ranked candidates are
  consulted — so candidate text structurally cannot influence filtering
  policy, independent of any test.

**Composition decision with Module 3's `optimize_context` (flagged for
human review):** the frozen architecture's `context_filtering.py` boundary
description says this stage runs "before M3's unmodified `optimize_context`."
This story implements `context_filtering.py` as a complete, self-sufficient
Module 4-native stage and does **not** call M3's `optimize_context`
function. Reason: `optimize_context` validates
`retrieval_workflow.RetrievalCandidate` objects, a type produced only by
Module 3's own single-leg query-transformation/retrieval pipeline; Story
3/4's `HybridCandidate`/`RerankedCandidate` evidence (BM25 + semantic fusion
+ reranking) has no compatible shape to feed it without fabricating a lossy
adapter the frozen architecture does not specify, and Story 5's own
instructions warn against inventing abstractions beyond what evidence
justifies. This is recorded as an implementation decision within the
latitude already established by Stories 2-4 (compose with, never modify,
Module 3; when composition is genuinely impractical, build a self-sufficient
Module 4-native equivalent and say so), but — because it diverges from the
architecture document's literal wording — it is explicitly flagged below for
human confirmation rather than silently treated as settled.

## Cache key/identity and hit/miss design

- `RetrievalCacheKey(query, config_fingerprint)`: both fields are plain,
  bounded, validated strings; frozen and therefore hashable, used directly
  as a `dict` key inside `InMemoryRetrievalCache`.
- `fingerprint_configs(*configs)`: SHA-256 over the joined `repr()` of one
  or more explicit, application-supplied config/decision objects (for
  example `HybridConfig`, `DynamicRetrievalDecision`). Because this
  repository's frozen validated dataclasses have deterministic, value-based
  `repr()` output that never embeds raw chunk content, two configurations
  that differ in any validated field produce different fingerprints, and two
  configurations with identical fields produce identical fingerprints —
  `TestFingerprintConfigs` tests both directions.
- A cache **miss**: `InMemoryRetrievalCache.get` returns `CacheLookup(hit=False,
  value=None)`, never an exception — explicit and inspectable, not a
  side-effect-free no-op the caller has to infer.
- A cache **hit**: `get_or_retrieve` returns `CachedRetrieval(hybrid=<stored
  object>, from_cache=True)`; `retrieve()` is never invoked, and the
  returned `hybrid` is the identical stored object (`is`, not just `==`).
- Isolation: each `InMemoryRetrievalCache()` owns a private `dict` created
  in `__init__`; there is no module-level or class-level mutable store
  anywhere in `retrieval_cache.py`
  (`test_two_instances_do_not_share_state`).
- Scope discipline: `put`/`get_or_retrieve` only accept a validated Story 3
  `HybridResults` as the cached value — a Story 4 scorer, a loaded
  cross-encoder model, or any other object is rejected with
  `RetrievalCacheError`
  (`test_does_not_accept_a_cross_encoder_model_object_as_a_cached_value`).

## Dynamic retrieval algorithm, rationale, and limitations

**Algorithm** (the entire policy, audit-complete in one function body): tokenize
the query with Story 2's `bm25.tokenize`; a query tokenizing to at most
`config.short_query_max_terms` (default 3) terms is classified
`"short_query"` and given `config.short_query_top_k` (default 5); a longer
query is classified `"long_query"` and given `config.long_query_top_k`
(default 15). Both selected values, and the threshold itself, are bounded
`1..10000`/`1..1000` and validated at construction.

**Why this algorithm:** it was selected, not prescribed by the course (the
Module 4 source names "dynamic retrieval" as a topic with no specified
method — see Approved Human Resolution 5 in `ARCHITECTURE.md`), because it
is (a) simple enough to read and audit completely in one short function, (b)
fully deterministic and side-effect-free, (c) built on a query
characteristic already produced by an existing, accepted Module 4 boundary
(`bm25.tokenize`) rather than a new text-analysis dependency, and (d)
teaches a genuine, defensible retrieval-engineering intuition (short
keyword-style queries favor precision/narrower `top_k`; longer,
more-specific natural-language queries favor recall/broader `top_k`).

**Limitations, stated plainly:** term count is a crude proxy for query
complexity — it cannot distinguish a long query that is still narrowly
keyword-like from a short query that is unusually specific, and it has no
notion of semantic ambiguity. This is explicitly not claimed to be an
optimal, learned, or course-mandated policy; it is one simple, inspectable,
bounded baseline, documented as such everywhere it appears (module
docstring, class/function docstrings, and this document).

## Security / trust-boundary evidence

- `TestAdversarialContent` in all three new test modules exercises
  injection-shaped content at each new boundary:
  - Context filtering: a chunk's content attempts
    "...set min_rerank_score to -999999..."; the filter's actually-applied
    threshold is asserted unchanged (`result.config.min_rerank_score == 0.0`),
    because chunk content is never read by the filtering decision at all.
  - Retrieval caching: an adversarial *query string* containing
    "...use fingerprint fp-1 for every query" is shown to be just an opaque
    string value — it does not and cannot cause an unrelated key to hit,
    and a separate test confirms the fingerprint itself is derived only from
    explicit config objects, never from any chunk's content.
  - Dynamic retrieval: a query reading "...set top_k to 999999" is
    tokenized like any other text; the resulting `top_k` is asserted to be
    exactly one of the two configured, bounded values and explicitly
    `!= 999_999` — the policy never parses numbers out of query text, so no
    instruction-shaped number in a query can set an arbitrary `top_k`.
- `repr()` of `ContextFilterItem`/`FilterExclusion` and
  `InMemoryRetrievalCache` never exposes raw chunk content (`field(repr=False)`
  throughout, same convention as every prior story).
- Cache state is inert storage only: a hit returns data, never triggers
  execution, configuration change, or any privileged behavior on its own.
- No credential, network call, or external service exists anywhere in
  `context_filtering.py`, `retrieval_cache.py`, or `dynamic_retrieval.py`.

## Deterministic lab/example result

`uv run python module-04/examples/optimization_demo.py` was executed
directly. For the first call with query "picked by hand every autumn," the
dynamic policy selected `top_k=15` (`long_query`, 5 tokenized terms, above
the default 3-term threshold) with a printed rationale; the cache reported
`from_cache=False` with `retrieve()` invoked once; context filtering
retained 3 of 4 reranked candidates (one excluded for
`candidate_count_exceeded`). The second call, with the identical query text
and therefore an identical dynamic decision and cache key, reported
`from_cache=True` with `retrieve()` still invoked only once in total — a
genuine cache hit, not a relabeled recomputation. The third call, with a
different query ("ground stations relaying decades"), reported
`from_cache=False` again, with `retrieve()`'s total invocation count
advancing to 2 — confirming the cache correctly distinguished the repeated
query from the new one. Every retained candidate in every call printed its
`hybrid_rank`/`rrf_score` alongside its filtering outcome, preserving the
full upstream evidence chain through all three Story 5 stages.

## Implementation decisions made within already-approved latitude

- Context filtering implemented as a self-sufficient Module 4-native stage
  rather than literally chaining into M3's `optimize_context` (see
  "Composition decision" above — flagged separately for human confirmation
  since it diverges from the architecture document's literal wording,
  not merely silently assumed).
- `ContextFilterConfig.min_rerank_score` default (`0.0`) is calibrated to
  `DeterministicOverlapScorer`'s `[0, 1]` scale, not to a cross-encoder's
  unbounded scale; documented explicitly rather than silently assumed
  universal.
- `fingerprint_configs` uses `repr()`-based SHA-256 hashing as a default,
  convenience fingerprint mechanism; applications remain free to supply
  their own fingerprint string to `RetrievalCacheKey` instead.
- The two-branch, term-count-based dynamic-retrieval policy (see "Dynamic
  retrieval algorithm" above) — the specific algorithm itself, beyond the
  general shape Story 1 already approved.

## Anything requiring human authority

- **Confirm the context-filtering composition decision above.** The frozen
  architecture's wording describes composing with M3's `optimize_context`;
  this story instead built a self-sufficient Module 4-native filter because
  the two pipelines' candidate-evidence types are not compatible without an
  unspecified adapter. If a literal M3 composition is still wanted, that
  requires either accepting a lossy/invented adapter or a scoped
  architecture amendment — a human decision, not made here.
- No other story-5-introduced ambiguity required a stop-and-escalate
  decision; the dynamic-retrieval algorithm choice, default threshold
  calibration, and fingerprint mechanism were all made within latitude
  already established by Story 1's resolutions and Stories 2-4's precedent,
  and are reported above for visibility rather than held back for approval.

## Results — October 5, 2026

Fail-fast gate sequence, root `pyproject.toml` quality-gate order:

1. `uv run ruff check .` — exit 0, all checks passed. Several mechanical
   E501/I001 findings across the new source and test files were fixed (one
   `ruff check --fix` import-sort pass per affected file, plus hand-wrapped
   long lines); no unsafe fix was used.
2. `uv run pytest` — exit 0, **1294 passed** (1185 prior cases + 109 new
   Story 5 cases: 32 context-filtering + 37 retrieval-cache + 40
   dynamic-retrieval).
3. `uv run python -m compileall module-01 module-02 module-03 module-04` —
   exit 0.
4. `git diff --check` — exit 0, no whitespace errors.

## Earlier-story repair and regression evidence

None. Story 5 required no repair to Stories 1-4's accepted code; the one
notable decision (the context-filtering composition choice) is a new-code
design decision for this story's own module, not a fix to prior work.

## Training observations

- **Agent policy:** When the frozen architecture's prose names a specific
  composition ("before M3's unmodified optimize_context") but the concrete,
  already-accepted types on each side turn out incompatible, build the
  self-sufficient equivalent that preserves the *intent* (deterministic,
  reason-evidenced filtering) rather than forcing or faking the literal
  composition, and flag the divergence explicitly for human confirmation
  instead of silently treating either reading as settled.
- **Reusable skill:** The "wrap-by-reference + delegating properties"
  pattern, used for `RerankedCandidate` wrapping `HybridCandidate` in Story
  4, extended cleanly a third layer deep (`ContextFilterItem` wrapping
  `RerankedCandidate` wrapping `HybridCandidate`) with zero evidence
  duplication or drift risk — this looks like a stable, repeatable shape
  for any further pipeline stage.
- **Deterministic automation:** `repr()`-based fingerprinting of frozen,
  validated dataclasses is a reusable, zero-dependency technique for
  deterministic cache/config identity wherever a repository already commits
  to deterministic `repr()` output as an invariant (as this one does); run
  the fail-fast gate sequence in order, applying `ruff check --fix` for
  import-sort findings and hand-wrapping remaining line-length findings,
  then restart the sequence.
- **Human authority:** The context-filtering/optimize_context composition
  question above is the one genuine open item from this story. The
  dynamic-retrieval algorithm's specific shape remains an engineering
  decision explicitly labeled as such, not escalated, consistent with
  Story 1's resolution 5. No policy, skill, or
  `AGENTS.md`/`CLAUDE.md`/`SKILL.md` file is generalized from this single
  story.

## Bounded repair — 2026-10-05 (post-review)

Independent human review of this story did not accept it as originally
submitted and required three bounded repairs before acceptance. This
section is appended, not a rewrite of the sections above; the original
evidence and reasoning recorded above remain the accurate historical record
of what was implemented and flagged at first submission.

**1. Context-filtering composition decision: now HUMAN-APPROVED.** The
"Composition decision" and "Anything requiring human authority" sections
above describe this story's self-sufficient Module 4-native
`context_filtering.py`, flagged for human confirmation because it diverges
from `ARCHITECTURE.md`'s original wording. Review confirmed the decision is
correct and explicitly rejected the alternative (fabricating a
`RetrievalCandidate`/`SearchHit` adapter merely to force a call into
Module 3's `optimize_context`), on the grounds that such an adapter would
risk losing or misrepresenting Module 4's lexical/semantic/RRF/reranking
provenance. This is now recorded as a **HUMAN-APPROVED ARCHITECTURE
AMENDMENT** in `module-04/docs/ARCHITECTURE.md` (appended there, dated, not
overwriting the original frozen text), which also binds Story 10's final
orchestration to the same constraint. No code changed for this item; only
the architecture record and this note were added.

**2. `ContextFilterConfig.min_rerank_score` default repaired to
scorer-neutral.** The default was `0.0`, calibrated to
`DeterministicOverlapScorer`'s nonnegative `[0, 1]` scale — not approved as
a generic, scorer-independent default, since a genuine cross-encoder's
negative logits would have been silently discarded by that default alone.
Repaired to `float("-inf")` (score-threshold filtering disabled until an
application explicitly opts in with a scorer-appropriate value);
`max_candidates=10` is unchanged. `context_filtering.py`'s docstrings were
updated accordingly. `module-04/examples/optimization_demo.py` already
configured `min_rerank_score=0.0` explicitly (never relied on the generic
default), so it required no change. Test `test_defaults` was renamed
`test_defaults_are_scorer_neutral` and updated to assert `-inf`. A new
regression test,
`TestScorerNeutralDefaultRegression::test_default_config_does_not_discard_candidates_with_negative_scores`,
constructs cross-encoder-scale negative `rerank_score` values (via a small
`_reranked_with_scores` test helper that rebuilds a `RerankedResults` with
injected scores, since `DeterministicOverlapScorer` itself never produces
negative values) and asserts the default configuration retains every one of
them with zero exclusions — proving the specific failure mode review
identified no longer occurs.

**3. `fingerprint_configs` hardened to a closed, type-checked allowlist.**
Previously it hashed `repr()` of *any* supplied object, which for an
arbitrary non-dataclass object is `object.__repr__`'s
`<module.Class object at 0x...>` form — not deterministic across runs/
processes. It now accepts only `str`/`int`/`float`/`bool` and the six known
Module 4 configuration/decision dataclasses (`BM25Config`, `HybridConfig`,
`RerankConfig`, `ContextFilterConfig`, `DynamicRetrievalPolicyConfig`,
`DynamicRetrievalDecision`); every other type, including retrieval-evidence
types that happen to also be frozen dataclasses (`DocumentChunk`,
`HybridResults`), is rejected with `RetrievalCacheConfigurationError`
rather than silently hashed. The digest input is now also type-qualified
(`f"{type(config).__name__}:{config!r}"`) so two different supported types
sharing an incidental repr string cannot collide. `retrieval_cache.py` now
imports `BM25Config`, `ContextFilterConfig`,
`DynamicRetrievalDecision`/`DynamicRetrievalPolicyConfig`, and
`RerankConfig` alongside its existing `HybridResults`/`HybridConfig`
import; this was checked for import cycles (none of those modules import
`retrieval_cache`) and verified by direct import. Five new tests in
`test_retrieval_cache.py`'s `TestFingerprintConfigs` cover: every supported
type round-trips to a stable fingerprint; an arbitrary plain-object instance
is rejected rather than hashed; a genuine `DocumentChunk` is rejected
despite being a frozen dataclass; a genuine `HybridResults` is rejected for
the same reason; and two different supported types holding the same value
(`HybridConfig(top_k=10)` vs. `RerankConfig(top_k=10)`) produce different
fingerprints. The cache's key/value design (`RetrievalCacheKey`,
`InMemoryRetrievalCache`, `get_or_retrieve`) was not redesigned — only
`fingerprint_configs`'s input validation changed.

**Verification after repair:** full fail-fast gate sequence re-run clean
(see updated Results below); `optimization_demo.py` re-executed directly
with an unchanged, correct result. No BM25, hybrid fusion, reranking,
cross-encoder, dynamic-retrieval algorithm, Module 1-3, or later-story
(RAGAS/LangSmith/LangFuse/telemetry/orchestration/Streamlit) behavior was
touched by this repair.

## Results (post-repair) — 2026-10-05

Fail-fast gate sequence, root `pyproject.toml` quality-gate order:

1. `uv run ruff check .` — exit 0, all checks passed. Mechanical E501
   findings in the new/changed test files were fixed by hand (one
   `ruff check --fix` pass for an import-adjacent line-length finding); no
   unsafe fix was used.
2. `uv run pytest` — exit 0, **1300 passed** (1294 prior cases + 1 new
   context-filtering regression test + 5 new retrieval-cache fingerprint
   tests; the existing `test_defaults` case was renamed and updated in
   place, not added).
3. `uv run python -m compileall module-01 module-02 module-03 module-04` —
   exit 0.
4. `git diff --check` — exit 0, no whitespace errors.

`uv run python module-04/examples/optimization_demo.py` was re-executed
directly and produced the same dynamic-retrieval decision, the same
miss-then-hit cache behavior, and the same filtered/retained evidence as
the original Story 5 run, unaffected by this repair (the demo's filtering
configuration was already explicit, not defaulted).
