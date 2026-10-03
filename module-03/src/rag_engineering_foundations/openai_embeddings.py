"""Isolated OpenAI Embeddings SDK adapter; no client, key lookup, or call on import.

Application code supplies its configured SDK client. Expected SDK exceptions may
retain request text/headers internally; rendered chains suppress those causes.
Never serialize exception context or the raw client/response for public output.
"""

import math
import re
from dataclasses import dataclass, field

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

from .embeddings import EmbeddingBatch, validate_texts
from .errors import (
    EmbeddingAvailabilityError,
    EmbeddingRequestError,
    EmbeddingResponseError,
    VectorError,
)
from .vectors import Vector, _dimension


@dataclass(frozen=True, slots=True)
class OpenAIEmbeddingConfig:
    """Explicit application-owned model/dimension and bounded request settings.

    Args:
        model: Nonblank bounded ASCII model identifier; hidden in repr.
        dimension: Expected returned dimension, 1..16384; always validated.
        request_dimensions: Send a dimensions parameter only when explicitly true;
            application must choose a model supporting shortening. Default false.
        timeout_seconds: Finite SDK timeout in 0.1..120 seconds; default 30.

    Raises:
        EmbeddingRequestError: For malformed application settings.
    """

    model: str = field(repr=False)
    dimension: int
    request_dimensions: bool = False
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        """Validate settings without consulting credentials or model services."""
        if (
            type(self.model) is not str
            or not 1 <= len(self.model) <= 128
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*", self.model) is None
        ):
            raise EmbeddingRequestError(
                "Supply an explicit bounded ASCII embedding model ID."
            )
        try:
            _dimension(self.dimension)
        except VectorError as exc:
            raise EmbeddingRequestError(
                "Use an expected embedding dimension from 1 to 16384."
            ) from exc
        if type(self.request_dimensions) is not bool:
            raise EmbeddingRequestError(
                "Use bool to explicitly enable dimension shortening."
            )
        if (
            type(self.timeout_seconds) not in (int, float)
            or not 0.1 <= self.timeout_seconds <= 120
            or not math.isfinite(self.timeout_seconds)
        ):
            raise EmbeddingRequestError(
                "Use a finite SDK timeout from 0.1 to 120 seconds."
            )


class OpenAIEmbedder:
    """Generate validated embeddings through a supplied sync OpenAI SDK client.

    No automatic credential loading, client construction, retries, or model
    selection occurs. Injected clients remain trusted application capabilities.
    Mocked SDK verification is not evidence of remote-service behavior.
    """

    def __init__(self, client: OpenAI, config: OpenAIEmbeddingConfig) -> None:
        """Capture trusted SDK capability and immutable explicit configuration.

        Args:
            client: Application-owned OpenAI client or compatible offline test fake.
            config: Explicit model, expected dimensions, and request settings.

        Raises:
            EmbeddingRequestError: If config or the client interface is invalid.
        """
        if type(config) is not OpenAIEmbeddingConfig or not callable(
            getattr(client, "with_options", None)
        ):
            raise EmbeddingRequestError(
                "Supply OpenAIEmbeddingConfig and an SDK client."
            )
        self._client = client
        self._config = config

    @property
    def dimension(self) -> int:
        """Return the expected embedding coordinate count."""
        return self._config.dimension

    def embed(self, texts: tuple[str, ...]) -> EmbeddingBatch:
        """Call the genuine SDK embeddings endpoint and align validated indices.

        Args:
            texts: Bounded tuple of nonblank untrusted texts, kept as input data.

        Returns:
            Vectors ordered by provider index to match the original input tuple.

        Raises:
            EmbeddingError: For invalid text batches.
            EmbeddingRequestError: For authentication, access, model, or request errors.
            EmbeddingAvailabilityError: For timeout, connection, rate, or API failure.
            EmbeddingResponseError: For malformed SDK responses, indices, or vectors.
                Unexpected programming defects and BaseException propagate.
        """
        validate_texts(texts)
        config = self._config
        dimensions = (
            {"dimensions": config.dimension} if config.request_dimensions else {}
        )
        try:
            response = self._client.with_options(max_retries=0).embeddings.create(
                input=list(texts),
                model=config.model,
                encoding_format="float",
                timeout=config.timeout_seconds,
                **dimensions,
            )
        except (AuthenticationError, PermissionDeniedError):
            raise EmbeddingRequestError(
                "OpenAI embedding access failed; check client credentials "
                "and permissions."
            ) from None
        except (BadRequestError, NotFoundError, UnprocessableEntityError):
            raise EmbeddingRequestError(
                "OpenAI rejected embeddings; check model, dimensions, "
                "and input token limits."
            ) from None
        except APIResponseValidationError:
            raise EmbeddingResponseError(
                "Reject invalid OpenAI embedding response schema."
            ) from None
        except (RateLimitError, APITimeoutError, APIConnectionError):
            raise EmbeddingAvailabilityError(
                "OpenAI embeddings unavailable; retry later or check "
                "connectivity/rate limits."
            ) from None
        except APIStatusError as exc:
            if 400 <= exc.status_code < 500:
                raise EmbeddingRequestError(
                    "OpenAI rejected embeddings; check application request settings."
                ) from None
            raise EmbeddingAvailabilityError(
                "OpenAI embeddings failed; retry later."
            ) from None
        except APIError:
            raise EmbeddingAvailabilityError(
                "OpenAI embeddings failed; retry later."
            ) from None
        if (
            not isinstance(response, CreateEmbeddingResponse)
            or getattr(response, "object", None) != "list"
        ):
            raise EmbeddingResponseError("Expected an OpenAI embeddings list response.")
        data = getattr(response, "data", None)
        if type(data) is not list or len(data) != len(texts):
            raise EmbeddingResponseError(
                "Require exactly one embedding per input text."
            )
        ordered: dict[int, Vector] = {}
        for record in data:
            if (
                not isinstance(record, Embedding)
                or getattr(record, "object", None) != "embedding"
            ):
                raise EmbeddingResponseError("Require valid OpenAI embedding records.")
            index = getattr(record, "index", None)
            if (
                type(index) is not int
                or not 0 <= index < len(texts)
                or index in ordered
            ):
                raise EmbeddingResponseError(
                    "Require unique embedding indices covering the input batch."
                )
            values = getattr(record, "embedding", None)
            if type(values) is not list or len(values) != config.dimension:
                raise EmbeddingResponseError(
                    "Require embedding vectors with the configured dimension."
                )
            try:
                ordered[index] = Vector(tuple(values))
            except VectorError as exc:
                # Our VectorError diagnostics contain no supplied numeric payload.
                raise EmbeddingResponseError(
                    "Reject malformed or nonfinite embedding coordinates."
                ) from exc
        return EmbeddingBatch(
            tuple(ordered[i] for i in range(len(texts))), config.dimension
        )
