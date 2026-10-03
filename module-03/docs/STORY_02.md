# Story 2: Document ingestion and metadata/provenance contracts

Implemented against accepted foundation `fd3c77e` and architecture freeze
`8957379`. Frozen source and architecture files are unchanged.

## Scope and public API

`rag_engineering_foundations.ingestion` accepts literal in-memory text through
`ingest_text(content, *, source_key, metadata=())` and UTF-8 bytes through
`ingest_bytes(content, *, source_key, media_type="text/plain", metadata=())`.
These functions return `IngestedDocument`. No filesystem or network access,
provider calls, chunking, retrieval, orchestration, or UI is introduced.
No dependencies or shared project configuration change.

The typed immutable contracts are:

- `MetadataEntry(key, value)`: untrusted text attributes, validated on construction.
- `IngestedDocument(content, source_key, user_metadata=())`: validates the input
  and derives its own provenance even when constructed directly.
- `DocumentProvenance`: structurally validated hashes, identity, media type,
  UTF-8 byte count, Unicode character count, and splitlines count. Evidence is
  separate from policy and is never authorization.

The `errors` module exposes `IngestionError` and its `UnsupportedInputError`
subclass. Errors describe the corrective action without interpolating raw input.

## Design and determinism

Plain text is the smallest useful supported surface. Content is preserved exactly;
there is no stripping, Unicode normalization, newline conversion, encoding
guessing, replacement decoding, or BOM removal. Whitespace-only input, invalid
Unicode/UTF-8, and C0 controls other than tab/CR/LF are rejected.

Content is limited to 1 MiB of UTF-8, source references to 1,024 UTF-8 bytes, and
metadata to 32 entries with unique keys. Keys allow 128 bytes and values 2,048
bytes; fields must be nonblank strings. Limits bound instructional ingestion
inputs rather than claim support for arbitrarily large corpora. Metadata accepts
text values only, not nested objects or parser ecosystems.

`source_id` is the SHA-256 digest of the exact declared source key.
`content_sha256` is the digest of exact encoded content. `document_id` is
`doc-v1-` followed by SHA-256 of the ASCII sequence
`text/plain`, NUL, source digest, NUL, content digest. Metadata changes do not
change identity. Content revisions preserve source identity but change document
identity; identical text from different declared sources has distinct document
identities. Content/source hashes are reproducibility evidence, not anonymization
or origin authentication.

Source keys are construction-only inputs and are not retained. A caller can
recompute their digest to correlate a document with its declared origin. No raw
local paths, URL query strings, credentials, or source references are copied into
provenance. The module never interprets a source key as a path, nor verifies its
ownership or existence. Callers must manage source references as application data.

## Trust boundary

Caller metadata remains in `user_metadata`, with no merge into provenance or
application configuration. Keys such as `authority`, `source_id`, and
`document_id` are ordinary untrusted attributes. Application-derived enrichment
uses content rather than caller claims. No content or metadata is executed or
interpreted as instructions. Validation establishes structural suitability only;
content and metadata still require the later stages' untrusted-data treatment.

Frozen dataclasses and tuple metadata prevent ordinary post-validation mutation;
they are not a sandbox against malicious Python code. Document content, metadata
values, and the metadata collection are excluded from document representations.
Decoder/encoder exceptions are suppressed in rendered chains because native
causes retain raw input. Internal exception context may still retain rejected
data and must not be serialized or logged. This follows Module 2's content-safe
error boundary convention rather than adding blanket exception handling.

## Requirement evidence and deferred work

| Requirement | Story 2 evidence | Remaining evidence |
| --- | --- | --- |
| M3-LAB-01 | Runnable text/bytes ingestion, validated document contracts, offline tests | UI demonstration in Story 9; remains partial |
| M3-CTX-04 | Caller metadata retention and derived identity, integrity, format, and size enrichment, with tests | Later workflow integration and human source-faithfulness review |

Both frozen requirement statuses remain Pending. Story 2 provides implementation
and test evidence for metadata enrichment without claiming whole-module
completion. No TRACEABILITY or VERIFICATION release artifacts are created.

PDF, DOCX, HTML, web crawling, file-backed readers, additional encodings, MIME
sniffing, credential scanning, and source registries are deferred. Unknown media
types fail explicitly. A text/plain declaration is not proof that bytes originated
from a text file. Chunk contracts and algorithms remain Story 3 work; exact text
and provenance give that story the inputs needed for offset/source tracking.

## Tests and quality gates

`test_ingestion.py` adds 41 offline cases covering exact Unicode/newline retention,
enrichment, deterministic identity and revisions, metadata/provenance separation,
immutability, invalid types and content, resource limits, unsupported declarations,
UTF-8 failures, safe displayed errors, and direct-construction validation.
Existing Story 1 packaging/dependency checks remain in place.

On October 3, 2026, the restarted fail-fast sequence passed on Python 3.12.14:

1. `uv run ruff check .` — exit 0, all checks passed.
2. `uv run pytest` — exit 0, **505 passed in 18.57 seconds**, comprising the
   accepted 464 cases and 41 new ingestion cases.
3. `uv run python -m compileall module-01/src module-01/tests module-01/app.py
   module-02/src module-02/tests module-02/app.py module-03/src module-03/tests`
   — exit 0.
4. `git diff --check` — exit 0. New untracked files are also checked explicitly
   against an empty file using `git diff --no-index --check`.
   These supplementary comparisons returned 1 because the files differ from
   empty, with no whitespace diagnostics (only Git's LF-to-CRLF notices).

The final working tree contains only four untracked Story 2 files: this record,
`ingestion.py`, `errors.py`, and `test_ingestion.py`. HEAD remains `fd3c77e`.

## Repair history

The first Ruff gate reported I001 (one import-order violation) and E501 (three
90-character test lines exceeding 88). These are deterministic formatting issues.
`ruff check ... --fix` applied the safe import fix; `ruff format` wrapped the long
lines. The failed Ruff gate was rerun successfully, then the full fail-fast
sequence restarted. No unsafe fixes or changes to quality rules were used.

## Training observations

- **Agent policy:** Preserve the separation between structural validation and
  authority; exclude data-bearing parser causes from displayed domain failures;
  do not treat passing tests as complete source evidence.
- **Reusable provider-neutral skill:** Preserve literal content; distinguish
  declared source identity, content revisions, untrusted metadata, and computed
  evidence. Test public helpers and direct contract construction at the same
  boundary. These are reusable questions, not yet a universal schema.
- **Deterministic automation:** Import sorting, formatting, fail-fast gate order,
  and repeating the sequence after repair can be automated without semantic
  changes. Identity stability and malformed-input checks are deterministic.
- **Human authority:** Supported format expansion, trust-policy changes, frozen
  source/architecture deviations, and final acceptance require human judgment.
  The exact source-key semantics and resource limits are documented design choices
  within this story, not proposed universal policy.

No AGENTS.md, CLAUDE.md, or SKILL.md is created. No commit is made.
