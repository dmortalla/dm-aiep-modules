# Story 3: Fixed, recursive, and semantic chunking

Implemented against accepted ingestion checkpoint `4416a23` and architecture
freeze `8957379`. Frozen source/architecture, Story 1 configuration, Story 2
contracts, Modules 1 and 2, and dependencies are unchanged.

## Structure and public contracts

`rag_engineering_foundations.chunking` provides `chunk_fixed`, `chunk_recursive`,
and `chunk_semantic`, returning immutable `ChunkingResult` objects. Application
configuration is explicit through `FixedConfig`, `RecursiveConfig`, and
`SemanticConfig`. All three reject raw documents or mismatched configuration
types; configuration construction rejects bool/coercion and invalid limits.

`DocumentChunk(document, index, start, end, strategy)` retains the accepted
`IngestedDocument` by reference without mutating it. Its `content` property is
exactly `document.content[start:end]`; it cannot accept independent content that
contradicts those offsets. The immutable `provenance` and `user_metadata`
properties retain Story 2's distinction between computed document evidence and
untrusted caller attributes. `chunk_id` is derived and cannot be supplied in the
constructor.

`ChunkingResult` validates complete source coverage, advancing start/end offsets,
zero-based contiguous indices, and the same parent object and strategy throughout.
Fixed results may overlap; recursive and semantic results must be exact partitions.
`SemanticEvidence(offset, similarity)` records each scored candidate boundary,
including candidates that do not cause a split. It validates bounded positive
offsets and finite scores; the result validates ordered evidence within its parent.
`SemanticSignal` is a callable protocol for adjacent-unit similarity.

`ChunkingError` and its `SemanticSignalError` subclass extend the existing errors
module at genuine chunk/configuration and callback failure boundaries.

## Provenance, offsets, and identity

All sizes and half-open `[start, end)` offsets count Python Unicode code points
in the original ingested text. They are not byte, grapheme, or token counts.
No strategy strips, normalizes, replaces, or synthesizes text. Separators and
whitespace remain in slices; whitespace-only chunks are valid when required to
preserve exact coverage. Repeated text is tracked with forward source offsets,
not by searching for a chunk's text in the original document.

Chunk identity is `chunk-v1-` plus SHA-256 of the UTF-8 sequence
`document_id`, NUL, strategy, NUL, decimal index, NUL, decimal start, NUL, decimal
end. Same parent identity, strategy, ordering, and spans reproduce the ID;
metadata does not affect it. A changed source/content changes the parent ID.
Different configurations/signals yielding identical slices under the same
strategy have the same IDs: identity describes the output, not a configuration
or callback version. Reproducible executions require the same application
configuration and deterministic signal, recorded by the caller when needed.
Hashes do not authenticate a source or confer authority.

## Fixed windows

`FixedConfig(size=1000, overlap=0)` validates integer `size` in 1..1048576 and
integer overlap in 0..size-1. Windows start at multiples of `size-overlap`.
Each end is bounded by the original content length. A final shorter chunk is
retained; processing stops when a window reaches document end, avoiding a
redundant tail made entirely of previously covered overlap.

For `abcdefghij`, size 4, overlap 2, offsets are `(0,4), (2,6), (4,8), (6,10)`.
For size 4 without overlap they are `(0,4), (4,8), (8,10)`.

## Recursive hierarchy

`RecursiveConfig(size=1000, separators=("\n\n", "\n", " "))` accepts one to
eight unique nonempty literal separators of at most 32 characters. Priority is
caller order, with paragraphs/lines/spaces as defaults. This is actual recursive
splitting, independent of the fixed strategy and any framework splitter.

A fitting span is kept whole. An oversized span is scanned using the current
separator; every delimiter belongs to the preceding piece. Adjacent fitting
pieces at that level merge greedily within the ceiling. An oversized piece
flushes the pending group and recursively descends to the next separator; it
does not merge its recursively produced fragments back across that level's
boundaries. Exhausting the hierarchy falls back to exact character windows
without overlap. With no matching separator, the entire span descends until this
fallback. The bounded hierarchy limits recursive depth to eight levels plus the
character fallback.

For `aa bb\n\ncc dd\n\nee ff`, size 10 produces three chunks ending at paragraph
boundaries. For `aa bb cc\n\nDD`, size 4, recursive descent produces
`aa `, `bb `, `cc\n`, `\n`, `DD`; the final newline remains a separate strong-level
piece rather than being repacked with a descended fragment. A weaker delimiter
or hard-size fallback can split the characters of a stronger delimiter when
necessary. Exactness and the ceiling remain invariants; full-sized chunks are
not promised.

## Semantic grouping without Story 4

`chunk_semantic(document, signal, SemanticConfig(size=1000, threshold=0.5))`
requires application-selected semantic code. There is no default scoring model,
OpenAI adapter, embedding production, or general vector-distance API.

Candidate units end after ASCII `.`, `!`, or `?` followed by whitespace/end, or
a blank LF line. Following whitespace belongs to the left unit. The boundary
specification remains equivalent to the original pattern
`(?:[.!?]+(?=\s|$)|\n[ \t]*\n)\s*`, but detection uses a forward-only linear
character scanner rather than regex backtracking. Punctuation runs and spaces
after LF are consumed once even when they do not form a boundary. Successful
boundaries consume trailing Unicode whitespace. Any final remainder is retained. This
simple segmentation is not multilingual sentence analysis: abbreviations can
produce extra candidates, and CRLF paragraph-only boundaries are not separately
recognized. CRLF and all Unicode source text are nevertheless preserved exactly.

The injected signal receives each pair of original adjacent units once, in
source order, and must return a finite int/float similarity in [0,1] (bool is
rejected). A score below threshold starts a new group; equality joins. Related
units join only while the combined group fits the character ceiling. An
oversized individual unit is split into hard character windows, explicitly a
size fallback, not a semantic claim. There is no overlap. All adjacent scores
and offsets remain available for inspection even when a size limit forces a cut.
A single unit requires no callback call and cannot exhibit a semantic boundary.

The protocol permits later embedding/similarity capability to supply the signal
without changing chunk-domain contracts. Determinism depends on that
implementation; the chunker validates shape/range, not the truth of meaning
claims. A constant callback is useful for threshold/size tests but is not
semantic-completeness evidence.

## Runnable comparison evidence

Run offline with no credentials:

```powershell
uv run python module-03/examples/chunking_comparison.py
```

The example prints all three strategies' exact slices, offsets, IDs, and semantic
scores. Its small application-authored ontology maps apples/pears/orchards/fruit
to a fruit topic and rockets/satellites/orbit/space to a space topic. It scores
shared known topics at 0.9, different known topics at 0.1, and unknown cases at
0.5. This controlled meaning signal can relate disjoint vocabulary and is not
paragraph splitting under another name or a general-purpose semantic model.

For `Apples ripen. Pears grow. Rockets launch. Satellites orbit.`, semantic size
100 groups the two fruit sentences together and the two space sentences
together, using candidate similarities 0.9, 0.1, 0.9 at offsets 14, 26, 42.
Fixed and recursive size 100 each keep that entire small document as one chunk.
The executable example additionally compares all strategies with size 70 on a
slightly longer corpus. Its subprocess test proves installed imports work
outside repository/pytest source-path injection.

## Security and resource boundaries

Content/metadata never select a strategy, callback, configuration, file, URL,
process, or tool. Source-like strings remain data; tests include a command-shaped
document with an output marker that is never created. Derived provenance remains
separate from metadata such as `authority`, `chunk_id`, or `signal`.

Chunk reprs hide the parent document, so result reprs do not copy source content
or metadata. Domain errors never interpolate rejected fields, scores, or text.
The explicit callback boundary translates ordinary callback exceptions to
`SemanticSignalError` with a corrective message and `from None`; this prevents
data-bearing callback failures from leaking through displayed exception chains.
Failures are not swallowed or replaced with fabricated successful scores.
KeyboardInterrupt and other BaseException control-flow failures propagate.
Internal error context may retain raw data and must not be serialized/logged.

The callback is trusted application code, not a sandbox: callers choose its
capabilities and must preserve untrusted-text treatment. The supplied example
and all normal tests remain offline. Frozen contracts prevent ordinary mutation,
not deliberate bypass using malicious Python code.

There is a 4096-chunk result ceiling. Fixed output count is checked before
construction; recursive/semantic output is bounded as spans are appended.
Semantic input is limited to 4096 candidate units, checked before any callback
invocation. Limits fail explicitly without dropping text or truncating evidence.
Increase size/reduce overlap or supply smaller documents when appropriate.

## Requirement coverage

| Requirement | Story 3 evidence | Still pending |
| --- | --- | --- |
| M3-CTX-01 | Genuine fixed windows, overlap, exact provenance, implementation/tests and offline demonstration | Final UI/workflow integration, traceability and review |
| M3-CTX-02 | Recursive separator hierarchy and character fallback, implementation/tests and offline demonstration | Final UI/workflow integration, traceability and review |
| M3-CTX-03 | Injected semantic scoring materially changes boundaries; controlled meaning signal, implementation/tests and offline demonstration | Production embedding-backed signal, UI/workflow integration, traceability and review |
| M3-LAB-03 | Three runnable strategies and executable/tested comparison evidence | Portfolio presentation, final traceability and human acceptance |

Frozen statuses remain Pending; no whole-module or final source-completeness
claim is made. No final TRACEABILITY or VERIFICATION artifacts are created.

## Tests and verification

`test_chunking.py` adds 84 offline cases, including four review-repair cases.
They cover fixed boundaries, partial
tails, overlap, Unicode, recursive priority/custom hierarchy/fallback, repeated
text, whitespace, semantic topic changes, signal-dependent grouping, threshold
equality, exact callback inputs, forced sizes, malformed fields/scores/evidence,
immutable contracts, source linkage and stable identities, gaps/ordering,
resource limits, content-safe callback failures, interrupt propagation, inert
command/metadata content, installed example execution, and SDK-independent imports.
The accepted 505 repository cases remain intact.

Before the independent-review repair, the complete restarted sequence passed on
October 3, 2026, on Python 3.12.14:

1. `uv run ruff check .` — exit 0, all checks passed.
2. `uv run pytest` — exit 0, **585 passed in 14.24 seconds** (505 accepted
   cases plus 80 new Story 3 cases).
3. `uv run python -m compileall module-01/src module-01/tests module-01/app.py
   module-02/src module-02/tests module-02/app.py module-03/src module-03/tests
   module-03/examples` — exit 0.
4. `git diff --check` — exit 0. All four new untracked files additionally passed
   whitespace inspection using `git diff --no-index --check -- /dev/null <path>`.
   Supplementary comparisons returned 1 for differences from empty, with no
   whitespace diagnostics; output contained only Git LF-to-CRLF notices.

Final status: `errors.py` modified; `chunking.py`, `test_chunking.py`,
`examples/chunking_comparison.py`, and this record untracked. HEAD remains
`4416a23`. No files are staged or committed.

## Repair history

Before formal gates, safe import sorting corrected two I001 diagnostics and Ruff
formatting normalized the three new Python files.

The first formal Ruff gate reported three B008 defaults that called config
constructors, B905 for unspecified zip strictness, and E501 for a 90-character
error string. Bounded repairs used immutable module-level defaults, `pairwise`
for intentional adjacent pairing, and a shorter corrective error. The failed
gate passed on rerun, then the complete sequence restarted.

The first full pytest run reported two failed new expectations (583 passed):
`test_recursive_fallback_exactness[aa bb cc\n\nDD-4-expected0]` and
`test_semantic_meaning_materially_changes_boundaries`. The former expected
`cc\n\n` but the documented recursive descent emits `cc\n` and a separate `\n`.
The latter hand-counted offsets as 13/25/41 rather than 14/26/42. Classification:
incorrect new test oracles, not accepted behavior regressions. Expected literals
were corrected against exact source lengths and the stated recursive rules.
No tests were deleted, and exact-content/coverage/maximum-size checks remain.
The failed pytest gate passed on rerun: 585 passed in 14.28 seconds. The full
fail-fast sequence was then restarted. No unsafe fixes, rule changes, frozen
document changes, or accepted behavior changes were made.

## Training observations

- **Agent policy:** Distinct source requirements need distinct behavior evidence;
  preserve exact source coverage and trust boundaries; keep future provider work
  behind an injected signal rather than leaking later-story implementation.
- **Reusable provider-neutral skill:** Represent transformations with original
  offsets and inherited evidence; use controlled meaning signals to verify
  provider-independent orchestration. Separate output identity from configuration
  versioning and explicit hard-size fallback from semantic claims.
- **Deterministic automation:** Safe formatting, fail-fast gate restart, exact
  coverage assertions, installed-import checks, and whitespace checking of new
  files can be automated. Test oracles need independent reasoning: a failure
  alone does not justify changing either an algorithm or an expected value.
- **Human authority:** Source/architecture deviations, incompatible provenance
  changes, and final acceptance require human guidance. Separator/threshold/unit
  choices here are documented within authorized scope, not universal policy.

## Independent-review repair

The reviewer identified quadratic scanning on valid input `"!" * n + "a"`.
The punctuation quantifier repeatedly backtracked and retried from successive
positions after its whitespace/end assertion failed. The 4096-unit limit could
not protect the scan because it was checked only after a boundary match.

The repair replaces regex detection with `_semantic_units`, a monotonically
advancing character scanner. Failed punctuation runs are skipped as complete
runs; blank-LF-line detection likewise consumes horizontal spaces once. Original
boundary semantics, exact source slices, source offsets, unit ceilings, callback
inputs/order, grouping, identities, and displayed failure behavior are preserved.
No dependency, frozen document, or Story 4+ capability changes.

Three parametrized adversarial regressions use 2,000, 8,000, and 1,048,575
punctuation characters followed by `a`. A counted string enforces at most four
indexed character reads per input character rather than measuring wall-clock
time. Each case also exercises full public semantic chunking, verifies exact
coverage/provenance, and proves a single unmatched unit invokes no callback.
A fourth test exhaustively compares all 11,111 strings of length zero through
four over a ten-character punctuation/whitespace/Unicode alphabet against the
original regex specification. That reference is restricted to short test inputs;
production chunking has no regex dependency. All previous tests remain intact.

Safe import sorting corrected one new I001 diagnostic before the repair gates;
formatting normalized the appended tests. No repair gate failed. On October 3,
2026, the requested full fail-fast repair sequence passed on Python 3.12.14:

1. `uv run ruff check .` — exit 0, all checks passed.
2. `uv run pytest` — exit 0, **589 passed in 14.78 seconds** (all previous
   585 cases plus four review-repair cases).
3. `uv run python -m compileall module-01 module-02 module-03` — exit 0.
4. `git diff --check` — exit 0, no whitespace errors. Supplementary no-index
   checks covered all four new untracked files; no whitespace diagnostics.

`uv run python module-03/examples/chunking_comparison.py` also passed (exit 0).
Example offsets remain fixed `(0,70), (70,112)`, recursive `(0,68), (68,112)`,
and semantic `(0,53), (53,112)`. Semantic evidence remains 0.9/0.1/0.9 at
offsets 26/53/80. Observable normal-input chunking behavior is unchanged.

Only `chunking.py`, `test_chunking.py`, and this record were edited for the
review repair. Git status still contains the original modified `errors.py` and
four untracked Story 3 files; nothing is staged or committed.

No AGENTS.md, CLAUDE.md, or SKILL.md is created. No commit is made.
