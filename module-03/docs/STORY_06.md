# Story 6: ChromaDB and Pinecone retrieval boundaries

Implemented from the verified clean `feature/module-03` baseline `3271925`.
Stories 1–5 contracts, FAISS implementation, frozen architecture/requirements,
Modules 1–2, and dependency declarations remain unchanged. Requirement statuses
remain Pending for Story 10 reconciliation.

## APIs and architecture

`ChromaIndexConfig(dimension, metric="cosine", ef_search=100)` and
`ChromaVectorIndex(records, config)` construct a fresh ephemeral local collection.
`search(query)` implements the existing structural `VectorIndex` protocol;
`close()` deletes only the owned collection and is idempotent.

`PineconeIndexConfig(dimension, metric="cosine", index_name="story6",
namespace="story6", timeout_seconds=30)` and
`PineconeVectorIndex(records, config, client)` use an application-owned synchronous
SDK client through `PineconeClientBoundary` / `PineconeIndexBoundary` protocols.
These are narrow provider seams, not replacements for Story 5's VectorIndex.
Neither constructor loads credentials. Pinecone construction with a real client
would read an existing index and upsert vectors; it never creates/deletes indexes.
No live client was used in this story.

Both adapters reuse `IndexedChunk`, `SearchQuery`, `SearchHit`, `SearchResults`,
`Vector`, and the chunk/document/provenance contracts. Embeddings remain application
work, including `LocalHashEmbedder` and `to_indexed_chunks` in the examples.
No provider objects leak into retrieval results. The private `_store_validation.py`
shares small validation/conversion helpers only between the new adapters; it does
not refactor FAISS or change public provider-neutral contracts.

## Executable provider boundaries

ChromaDB 1.5.9: a genuine `EphemeralClient` with telemetry disabled creates a unique
collection with `embedding_function=None`. Calls to `add` supply vectors and stable
chunk IDs explicitly, batching by the SDK's maximum batch size. Queries use
`query_embeddings` and request distances only. The collection stores derived
`document_id` metadata, never source text or arbitrary user metadata. Source chunks
remain in the application registry. Examples/tests close their collections.
UUID collection names isolate tests; they do not enter application identity/ranking.

Pinecone 10.0.0: the injected client calls `describe_index`, validates a ready index
with a single dense field and matching dimension/metric, selects `Index(name)`, and
upserts genuine SDK `Vector` objects. It uses v10 `IndexModel.schema` rather than
assuming legacy dimension/metric attributes. Conservative dimension-dependent
batching keeps float JSON payloads below the 2 MB upsert limit. Each response must
be a genuine `UpsertResponse` acknowledging exactly the submitted count.

Queries carry only an explicit vector, capped top_k, the configured namespace,
metadata/values disabled, and timeout. Genuine `QueryResponse` / `ScoredVector`
objects are validated before ID lookup. SDK model constructors are not assumed to
validate arbitrary assignments: tests deliberately exercise malformed fields.
The fixture implements actual call shapes and uses real SDK value types; it is
not a simulator of Pinecone's ANN algorithm or a transport/service verification.

Use a dedicated namespace for the application corpus. Construction is a bounded
snapshot, not incremental mutation. Pinecone upsert replaces existing identical
remote IDs; duplicates inside the application batch are rejected. Remote stale
or foreign records are never adopted: unknown returned IDs fail safely. A multi-
batch failure can leave partial writes remotely. Retry the same stable IDs or
reconcile the namespace explicitly; the adapter promises no cloud transaction.
The local `size` property reports the application registry, not remote statistics.
Remote eventual consistency can cause fewer matches; a nonempty bounded subset is
accepted, while an empty result raises a domain error because the established
SearchResults contract requires at least one hit. No contract was changed.

## Metric semantics

| Backend | Provider cosine value | Application cosine | Provider Euclidean value | Application Euclidean |
| --- | --- | --- | --- | --- |
| FAISS (Story 5) | normalized inner product | similarity, higher better | squared L2 | square root, lower better |
| Chroma | distance = 1 − cosine similarity | 1 − distance, higher better | squared L2 (`space="l2"`) | square root, lower better |
| Pinecone | cosine similarity | unchanged, higher better | squared Euclidean score | square root, lower better |

These conversions follow the official
[Chroma collection configuration](https://docs.trychroma.com/docs/collections/configure)
and [Pinecone similarity metrics](https://docs.pinecone.io/guides/index-data/create-an-index#similarity-metrics).
Cosine vectors are normalized explicitly using overflow-safe maximum scaling,
then L2 norm, on insertion and query. Zero vectors are rejected. Euclidean vectors
remain unnormalized, preserving magnitude. Providers operate with reduced numeric
precision; application finite values exceeding float32 range are rejected before
SDK calls. Finite Python vectors alone cannot guarantee provider arithmetic will
remain finite; nonfinite output is rejected. Cosine roundoff within 1e-6 is clamped
to [-1,1]; larger violations and negative squared distances are rejected.
Only cosine and Euclidean are supported; dotproduct/ip are not silently aliased.

## Determinism and validation

Rank is metric order, then ascending chunk_id, with contiguous zero-based ranks.
Sorting is deterministic for a fixed returned candidate set. ANN candidate
membership, including which equal-distance candidate crosses a top-k boundary,
is provider-controlled and is not promised reproducible. Sorting returned ties
does not make ANN exact or recover missing candidates. top_k is capped to local
registry size; requests larger than the corpus work without sentinels.

Before SDK calls: strict config/query/record types, dimension bounds/matches,
nonempty tuple corpus up to 10000, unique IDs, finite Vector coordinates,
nonzero cosine vectors, supported metric, and bounded namespace/index/deadline.
External results: container/row shapes, paired lengths, bounded nonempty counts,
unique known IDs, finite strictly numeric scores (no bool/coercion), metric ranges,
Pinecone namespace, and exposed returned vector shape/dimension/finiteness.
An unrecognized ID is checked before dereferencing any application record.

## Trust and failures

Provider metadata is never used to reconstruct or overwrite source/provenance.
Results retain the exact IndexedChunk objects by reference. Retrieved instruction-
like text remains inert data. No execution, tool selection, or authority transfer
is based on source text or metadata. Neither adapter requests provider embedding.

`ChromaOperationError` and `PineconeOperationError` are additive RetrievalError
subclasses with fixed actionable diagnostics. Chroma catches ChromaError plus
ValueError/RuntimeError at SDK calls; Pinecone catches its genuine PineconeException
hierarchy. No blanket Exception or BaseException catch exists. SDK chains are
suppressed with `from None` so rendered public exceptions omit raw provider text.
Python retains internal context; consumers must not serialize exception internals,
clients, payloads, or raw SDK models into public logs. Unexpected programming
exceptions propagate. Config repr hides Pinecone index and namespace; the adapter
uses default object repr, without payload rendering.

## Indexing and ANN concepts: demonstrated versus documented

Executable: Story 5 FAISS IndexFlat exact retrieval; real Chroma local collection
insertion/query; Chroma HNSW `space` and `ef_search` configuration (including a
150-record test beyond the default small insertion buffer); Pinecone SDK request/
response translation, index compatibility checks, namespaces, batching, and ID
mapping. Configured HNSW is not an independent recall benchmark.

Conceptual: exact search compares every vector (O(n*d)); ANN graph/partition
indexes seek fewer candidates, trading potential recall loss for latency and
resource use. HNSW graph construction consumes time and memory. Increasing search
breadth generally favors recall at added query cost; construction breadth and
neighbor count influence build cost, graph quality, and memory. This story
exposes only Chroma ef_search, not a custom ANN algorithm. No performance or
recall guarantee follows from the tiny known-vector tests.

Local Chroma collections group vectors and isolate identity/configuration;
ephemeral storage is process-local and not durable. Persistent Chroma would require
storage lifecycle/backup decisions; distributed deployment adds service operations.
Pinecone is managed: namespace/index deployment, network latency, readiness,
consistency, limits, cost, and credentials require application operations. Its
backend implementation is not exposed or reproduced by this seam.

Metadata filtering can restrict candidate sets by structured attributes before
ranking, affecting selectivity and recall. Neither adapter exposes filters in
this story; arbitrary metadata cannot select query policy. Collection/namespace
separation is logical grouping, not by itself user authorization. Persistence,
distributed retrieval, live consistency, and cloud performance are discussed,
not verified by offline tests.

## Offline demonstrations

Run `uv run python module-03/examples/chroma_search.py`:

- Exact document slices → deterministic 64-dimensional embeddings → real Chroma
  collection → application query vector → ranked source-linked SearchResults.
- Orchard score 1.000000; rocket score 0.000000; chunk/document IDs and original
  slices are printed. The owned collection is deleted in finally.

Run `uv run python module-03/examples/pinecone_offline.py`:

- Validated source records → real SDK Vector upsert payload → deterministic SDK
  response fixture → application results.
- Calls: describe, index, upsert, query. Two fixture scores 0.500000, sorted by
  ascending chunk ID. These are fixtures, not measured semantic scores.
- Clearly labeled OFFLINE. No credentials, network, or live Pinecone verification.

There is no optional live verification script and none was run.

## Tests, gates, and repairs

`test_story6_stores.py` adds 98 tests covering real local Chroma configuration,
known-vector metric conversions, identity/reference linkage, deterministic returned
ties, top-k, collection isolation/cleanup, malformed results, batch/query rejection,
SDK failure sanitization, dimensions, finite values, configuration bounds, Pinecone
request payloads, remote compatibility, acknowledgement validation, unexpected
exception propagation, payload budgets, and both runnable examples. An autouse
fixture blocks socket connect/connect_ex/create_connection for every Story 6 test,
including example execution. No cloud client or credential is constructed.

Mechanical pre-gate repairs: safe Ruff import fixes, formatter/line wrapping,
and binding a test closure variable. Semantic inspection repair: dimension-aware
Pinecone batching replaced a fixed batch assumption; JSON payload size is tested.
No existing test or quality rule was weakened.

Environment repair: default uv cache initialization failed; UV_CACHE_DIR points
to workspace `.uv-cache`. Initial full pytest: 813 passed, 22 setup errors, all
from denied default pytest temporary-directory access. Redirected pytest basetemp
and cache_dir into writable `.uv-cache` through PYTEST_ADDOPTS, preserving tests
and repository settings. The failed gate and full sequence are rerun separately.
Chroma configuration inspection emits SDK deprecation warnings; no behavior is
patched or warning suppressed.

Final fail-fast results: Ruff passed; all 835 repository tests passed
(98 new Story 6 tests); compileall for Modules 1�3 passed; git diff --check
passed. Both offline examples passed separately and under network-blocking tests.
Three Chroma SDK deprecation warnings remain; no verification was substituted.

## Requirements and exclusions

Evidence: M3-VS-02, M3-VS-03, M3-TOOL-02, M3-TOOL-03.
Advanced: M3-RET-04 indexing/ANN concepts and M3-DEL-02 vector retrieval system.
Frozen requirement statuses are unchanged; this is not Story 10 reconciliation.

Story 7+ absent: no query transformation, context optimisation, generation/RAG
orchestration, LangChain chain, Streamlit UI, or new embedding behavior. No FAISS
rewrite or source/architecture change. Nothing is staged or committed.
