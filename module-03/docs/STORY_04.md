# Story 4: Embedding generation and vector metrics

Implemented against accepted Story 3 checkpoint `09f6a27`. Frozen requirements,
architecture, Stories 1–3 behavior/tests, Modules 1–2, and dependencies are
unchanged. Requirement statuses remain Pending until Story 10 reconciliation.

## Contracts and bounded inputs

`vectors.Vector(values)` is a frozen value object containing a nonempty tuple
of finite floats, with a derived `dimension`. It accepts Python int/float values,
converts integers, and rejects bool, coercion, NaN, infinity, and unrepresentable
integers. Dimensions are bounded to 1..16384. Values are hidden in repr.

`embeddings.Embedder` defines `dimension` and
`embed(texts: tuple[str, ...]) -> EmbeddingBatch`. The frozen batch contains
1..64 vectors of its explicitly declared shared dimension, in input order.
`validate_texts` accepts only tuples of nonblank exact strings: at most 32768
UTF-8 bytes per text and 1048576 combined bytes. Invalid Unicode is rejected.
These application resource bounds are not model token limits. Whitespace-only
Story 3 chunks require an application decision before embedding; this story
does not modify chunking or silently strip embedding input.

No text, source offsets, document identity, or metadata is rewritten or retained
in embedding results. Later stories must retain their own association between
the ordered vectors and source chunks. Embeddings do not confer source authority.

## Deterministic local implementation

`LocalHashEmbedder(dimension=64)` produces vectors for arbitrary accepted input;
it has no fixture lookup. Unicode words are case-folded, counted into SHA-256
selected feature buckets, and normalized to unit length. Text with no word
features uses its exact text as one feature. SHA-256 avoids Python hash-seed
variation. Repeated input/configuration reproduces vectors and batch ordering.

This is an offline lexical engineering tool, not a trained production semantic
embedding model. Collisions, lost word order, and absent learned meaning limit
quality. Case-folding affects features only; input source text is not mutated.
The local module imports no provider, store, framework, or UI SDK and requires
no credentials or network.

## OpenAI Embeddings boundary

`openai_embeddings.OpenAIEmbeddingConfig(model, dimension,
request_dimensions=False, timeout_seconds=30)` is immutable application
configuration. Model identifiers are explicit and bounded; dimension is always
validated. Enabling `request_dimensions` sends shortening only by explicit
application choice; the application must select a compatible model.

`OpenAIEmbedder(client, config)` receives an application-owned synchronous
OpenAI SDK client. Import/construction makes no request and loads no credential.
Embedding calls use the genuine `client.with_options(max_retries=0).embeddings
.create` endpoint with literal input strings, configured model, float encoding,
explicit timeout, and optional dimensions. No chat/text generation is present.

Response list and record objects, count, unique integer indices covering the
batch, configured dimensions, and finite coordinates are checked. Records may
arrive out of order; validated indices restore input order. All output uses the
same Vector/EmbeddingBatch contract. Validation sees SDK-decoded values; the
SDK may normalize JSON numeric representations before this boundary.

The request contract was checked against the installed SDK and the official
[OpenAI Python embeddings reference](https://developers.openai.com/api/reference/python/resources/embeddings/methods/create).
Tests include both injected SDK objects and a real SDK client over an offline
`httpx2.MockTransport`. They establish serialization, parsing, and boundary
behavior, not remote model availability or semantic quality. No live request
was performed. An application can separately supply a credentialed client for
optional live verification; it must observe model token limits and data policy.

## Metrics and numeric behavior

All three metrics require two validated Vectors of equal nonzero dimension.
They use the standard library, with no vector-store dependency:

- `dot_product`: sum of coordinate products, affected by magnitude; overflow
  of a product or sum raises VectorError. Ordinary float rounding/underflow applies.
- `cosine_similarity`: normalized dot product in [-1,1]. Zero vectors raise
  VectorError because their direction is undefined. Scaled normalization handles
  very large and subnormal finite coordinates; final rounding is clamped.
- `euclidean_distance`: geometric L2 distance, zero for identical vectors;
  stable `math.dist` arithmetic, with unrepresentable distance rejected.

All are symmetric and deterministic for identical floating-point inputs.
Unit-normalized local vectors make cosine and dot product coincide; the API
also accepts unnormalized vectors, where the two metrics differ.

## Errors and trust boundaries

VectorError and EmbeddingError provide fixed actionable diagnostics. Provider
authentication/access and rejected requests translate to EmbeddingRequestError;
connection, timeout, rate, and API failures to EmbeddingAvailabilityError;
malformed output to EmbeddingResponseError. Expected SDK exception chains are
suppressed with `from None` because they can contain keys, request text, and
response bodies. Safe locally generated VectorError causes are retained.
Unexpected programming defects and BaseException propagate; failures are not
silently swallowed. Python still retains internal exception context: callers
must not serialize exception internals or raw clients/responses for public use.

Reprs hide vector coordinates, input text, and configured model IDs. Text is
untrusted data passed in the SDK input field; it cannot select model, dimensions,
timeouts, client capability, or credentials. No logging of payloads is added.

## Tests, demonstration, and evidence

New tests exercise immutability, strict numeric and dimensional validation,
bounded text/Unicode failures, local determinism and ordering, punctuation-only
input, metric examples/symmetry/zero/overflow/subnormal cases, isolated offline
imports, and a runnable example. Provider tests cover explicit request shape,
index reordering, malformed records/counts/indices/dimensions/numbers, expected
SDK failure classes, content-safe rendered exception chains, unexpected failure
propagation, and real SDK offline transport serialization/parsing.

Run `uv run python module-03/examples/embedding_metrics.py`. It prints three
64-dimensional vectors, repeatability, metric definitions, and pair comparisons.
The shared-fruit pair has cosine/dot 0.816497 and distance 0.605811; identical
vectors have 1/1/0. Hash collisions can produce overlap for unrelated text.

Requirements evidenced: M3-RET-01 (generation), M3-RET-02 (metrics), and
M3-TOOL-05 (genuine OpenAI SDK boundary plus offline integration tests).

Quality gate: Ruff, all 682 repository tests (93 new), compileall for Modules
1–3, tracked diff whitespace check, and untracked-file whitespace checks pass.
Offline example passes. Initial Ruff diagnostics received safe import cleanup
and line wrapping. New privacy tests were corrected to avoid source-line literals
in tracebacks; malformed SDK fixtures use nonvalidating updates so SDK coercion
does not mask invalid coordinates. No existing tests or rules were weakened.

## Explicit exclusions

No FAISS indexing, ChromaDB collections, Pinecone indexes, ANN algorithm,
semantic retrieval, query transformation, context optimization, RAG orchestration,
LangChain chain, Streamlit UI, or Story 3 semantic-signal adapter is implemented.
Those remain later-story work. No files are staged or committed.
