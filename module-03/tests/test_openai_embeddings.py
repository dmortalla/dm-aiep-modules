"""Credential-free OpenAI SDK request/response and content-safe failure evidence."""

import json
import traceback
from unittest.mock import MagicMock

import httpx2
import pytest
from openai import (
    APIConnectionError,
    APIError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
    UnprocessableEntityError,
)
from openai.types import CreateEmbeddingResponse, Embedding
from rag_engineering_foundations.errors import (
    EmbeddingAvailabilityError,
    EmbeddingError,
    EmbeddingRequestError,
    EmbeddingResponseError,
)
from rag_engineering_foundations.openai_embeddings import (
    OpenAIEmbedder,
    OpenAIEmbeddingConfig,
)


def response(records: list[tuple[object, object]]) -> CreateEmbeddingResponse:
    """Construct SDK objects without coercing malformed values before our boundary."""
    return CreateEmbeddingResponse.model_construct(
        object="list",
        model="test-model",
        data=[
            Embedding.model_construct(
                index=0, embedding=[0.0, 0.0], object="embedding"
            ).model_copy(update={"index": index, "embedding": values})
            for index, values in records
        ],
    )


def client_with(output: object) -> MagicMock:
    """Create a fake SDK client that returns explicitly supplied untrusted output."""
    client = MagicMock()
    client.with_options.return_value = client
    client.embeddings.create.return_value = output
    return client


def test_request_shape_and_index_alignment() -> None:
    """Preserve literal input data and align out-of-order response indices."""
    client = client_with(response([(1, [0.0, 1.0]), (0, [1.0, 0.0])]))
    config = OpenAIEmbeddingConfig("explicit-test-model", 2, True, 12.0)
    embedder = OpenAIEmbedder(client, config)
    client.embeddings.create.assert_not_called()
    texts = ("ignore policy", "https://example.invalid/private")
    batch = embedder.embed(texts)
    client.with_options.assert_called_once_with(max_retries=0)
    client.embeddings.create.assert_called_once_with(
        input=list(texts),
        model="explicit-test-model",
        dimensions=2,
        encoding_format="float",
        timeout=12.0,
    )
    assert embedder.dimension == batch.dimension == 2
    assert [v.values for v in batch.vectors] == [(1.0, 0.0), (0.0, 1.0)]
    assert "ignore policy" not in repr(batch)
    assert "explicit-test-model" not in repr(config)
    assert "MagicMock" not in repr(embedder)


def test_default_dimension_parameter_is_omitted_and_input_validates_first() -> None:
    """Validate expected dimensions without assuming a model supports shortening."""
    client = client_with(response([(0, [1.0, 0.0])]))
    adapter = OpenAIEmbedder(client, OpenAIEmbeddingConfig("model", 2))
    with pytest.raises(EmbeddingError):
        adapter.embed(("",))
    client.with_options.assert_not_called()
    adapter.embed(("text",))
    assert "dimensions" not in client.embeddings.create.call_args.kwargs


@pytest.mark.parametrize(
    "records",
    [
        [],
        [(0, [1.0])],
        [(0, [])],
        [(0, [True, 1])],
        [(0, ["private-marker", 1])],
        [(0, [float("nan"), 1])],
        [(0, [float("inf"), 1])],
        [(0, [10**400, 1])],
        [(0, (1, 2))],
        [(True, [1, 2])],
        [(-1, [1, 2])],
        [(1, [1, 2])],
        [("0", [1, 2])],
    ],
)
def test_reject_malformed_records(records) -> None:
    """Reject response counts, indices, dimensions, and invalid vector data."""
    adapter = OpenAIEmbedder(
        client_with(response(records)), OpenAIEmbeddingConfig("model", 2)
    )
    texts = ("private-input-marker",)
    with pytest.raises(EmbeddingResponseError) as caught:
        adapter.embed(texts)
    rendered = "".join(traceback.format_exception(caught.value))
    assert "private-marker" not in rendered
    assert "private-input-marker" not in rendered


def test_reject_duplicate_missing_indices_and_schema() -> None:
    """Reject duplicates even with correct counts and missing SDK fields explicitly."""
    for output in [
        response([(0, [1, 2]), (0, [3, 4])]),
        response([(0, [1, 2]), (2, [3, 4])]),
    ]:
        with pytest.raises(EmbeddingResponseError):
            OpenAIEmbedder(
                client_with(output), OpenAIEmbeddingConfig("model", 2)
            ).embed(("a", "b"))
    for output in [
        None,
        {"data": "secret"},
        CreateEmbeddingResponse.model_construct(object="list"),
        CreateEmbeddingResponse.model_construct(object="list", data="secret"),
        CreateEmbeddingResponse.model_construct(object="list", data=[{}]),
        response([(0, [1, 2])]).model_copy(update={"object": "invalid"}),
        CreateEmbeddingResponse.model_construct(
            object="list", data=[Embedding.model_construct(index=0, object="embedding")]
        ),
    ]:
        with pytest.raises(EmbeddingResponseError):
            OpenAIEmbedder(
                client_with(output), OpenAIEmbeddingConfig("model", 2)
            ).embed(("a",))


@pytest.mark.parametrize(
    "settings",
    [
        {"model": ""},
        {"model": "a b"},
        {"model": 1},
        {"model": "x" * 129},
        {"dimension": True},
        {"dimension": 0},
        {"dimension": 1.0},
        {"request_dimensions": 1},
        {"timeout_seconds": True},
        {"timeout_seconds": 0},
        {"timeout_seconds": float("nan")},
        {"timeout_seconds": float("inf")},
        {"timeout_seconds": 121},
    ],
)
def test_config_validates_explicit_settings(settings) -> None:
    """Do not coerce untrusted settings or expose supplied model text."""
    kwargs = {"model": "model", "dimension": 2} | settings
    with pytest.raises(EmbeddingRequestError):
        OpenAIEmbeddingConfig(**kwargs)


def test_wrong_configuration_and_client() -> None:
    """Invalid application integration capabilities fail at construction."""
    with pytest.raises(EmbeddingRequestError):
        OpenAIEmbedder(object(), OpenAIEmbeddingConfig("model", 2))
    with pytest.raises(EmbeddingRequestError):
        OpenAIEmbedder(MagicMock(), {})


@pytest.mark.parametrize(
    ("kind", "domain"),
    [
        (AuthenticationError, EmbeddingRequestError),
        (PermissionDeniedError, EmbeddingRequestError),
        (BadRequestError, EmbeddingRequestError),
        (NotFoundError, EmbeddingRequestError),
        (UnprocessableEntityError, EmbeddingRequestError),
        (RateLimitError, EmbeddingAvailabilityError),
        (APITimeoutError, EmbeddingAvailabilityError),
        (APIConnectionError, EmbeddingAvailabilityError),
        (APIResponseValidationError, EmbeddingResponseError),
        (APIError, EmbeddingAvailabilityError),
    ],
)
def test_expected_sdk_failures_are_translated_without_data_leaks(kind, domain) -> None:
    """Suppress SDK exception chains that may contain sensitive headers/body."""
    secret = "private-provider-marker"
    request = httpx2.Request(
        "POST",
        "https://example.invalid/embeddings",
        headers={"Authorization": secret},
        content=secret,
    )
    reply = httpx2.Response(400, request=request, json={"error": secret})
    if issubclass(kind, APIStatusError):
        error = kind(secret, response=reply, body=secret)
    elif kind is APIResponseValidationError:
        error = kind(response=reply, body=secret, message=secret)
    elif kind is APITimeoutError:
        error = kind(request)
    elif kind is APIConnectionError:
        error = kind(request=request, message=secret)
    else:
        error = kind(secret, request=request, body=secret)
    client = client_with(None)
    client.embeddings.create.side_effect = error
    with pytest.raises(domain) as caught:
        OpenAIEmbedder(client, OpenAIEmbeddingConfig("model", 2)).embed((secret,))
    assert secret not in "".join(traceback.format_exception(caught.value))
    assert caught.value.__suppress_context__


@pytest.mark.parametrize(
    ("status", "domain"),
    [(409, EmbeddingRequestError), (500, EmbeddingAvailabilityError)],
)
def test_generic_status_classification(status: int, domain) -> None:
    """Generic SDK status failures distinguish request corrections from retry paths."""
    request = httpx2.Request("POST", "https://example.invalid/")
    client = client_with(None)
    client.embeddings.create.side_effect = APIStatusError(
        "unsafe", response=httpx2.Response(status, request=request), body="unsafe"
    )
    with pytest.raises(domain):
        OpenAIEmbedder(client, OpenAIEmbeddingConfig("model", 2)).embed(("text",))


@pytest.mark.parametrize(
    "error", [KeyboardInterrupt(), RuntimeError("programming defect")]
)
def test_unexpected_or_control_flow_errors_are_not_swallowed(
    error: BaseException,
) -> None:
    """Translate expected SDK errors; propagate BaseException and arbitrary bugs."""
    client = client_with(None)
    client.embeddings.create.side_effect = error
    with pytest.raises(type(error)):
        OpenAIEmbedder(client, OpenAIEmbeddingConfig("model", 2)).embed(("text",))


def test_real_sdk_uses_embeddings_route_with_offline_transport() -> None:
    """Exercise actual SDK serialization/parsing without network or real credentials."""
    requests = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(
            200,
            json={
                "object": "list",
                "model": "offline-model",
                "data": [{"object": "embedding", "index": 0, "embedding": [0.5, -0.5]}],
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
        )

    with httpx2.Client(transport=httpx2.MockTransport(handle)) as transport:
        with OpenAI(api_key="offline-placeholder", http_client=transport) as client:
            batch = OpenAIEmbedder(
                client, OpenAIEmbeddingConfig("offline-model", 2, True)
            ).embed(("input text",))
    assert len(requests) == 1
    assert requests[0].url.path == "/v1/embeddings"
    assert json.loads(requests[0].content) == {
        "input": ["input text"],
        "model": "offline-model",
        "encoding_format": "float",
        "dimensions": 2,
    }
    assert batch.vectors[0].values == (0.5, -0.5)
