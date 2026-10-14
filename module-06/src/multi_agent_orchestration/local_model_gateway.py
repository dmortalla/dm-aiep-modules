"""One-attempt Ollama chat translation; runtime policy belongs to the parent.

Imports and construction perform no I/O. The application must authorize and
supervise execution before injecting this gateway. Protocol compatibility is
provisional until a separately authorized real-service probe.
"""

import asyncio
import json
from typing import NoReturn

import httpx

from .live_contracts import MAX_TOKEN_COUNT, ModelUsage
from .live_errors import LiveExecutionError, LiveFailureCategory
from .model_gateway import ModelReply, ModelRequest, checked_reply

LOCAL_CHAT_ENDPOINT = "http://127.0.0.1:11434/api/chat"
# JSON can escape each content byte into six bytes; envelope gets 4 KiB.
ENVELOPE_BYTES = 4096
_RESPONSE_FIELDS = frozenset(
    {
        "model",
        "created_at",
        "message",
        "done",
        "done_reason",
        "total_duration",
        "load_duration",
        "prompt_eval_count",
        "prompt_eval_duration",
        "eval_count",
        "eval_duration",
    }
)


def _fail(category: LiveFailureCategory) -> NoReturn:
    """Raise a closed failure without retaining a caller's raw exception."""
    try:
        raise LiveExecutionError(category) from None
    except LiveExecutionError as error:
        error.__context__ = None
        error.__cause__ = None
        error.__suppress_context__ = True
        raise


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field.")
        result[key] = value
    return result


def _invalid_constant(value: str) -> object:
    raise ValueError("Non-JSON number.")


def _usage_count(value: object) -> int | None:
    return value if type(value) is int and 0 <= value <= MAX_TOKEN_COUNT else None


def _translate(request: ModelRequest, body: bytes) -> ModelReply:
    """Validate the untrusted envelope; never interpret the role-output text."""
    raw = json.loads(
        body.decode("utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=_invalid_constant,
    )
    if (
        type(raw) is not dict
        or not set(raw) <= _RESPONSE_FIELDS
        or raw.get("model") != request.selection.model
        or raw.get("done") is not True
        or type(raw.get("message")) is not dict
    ):
        raise ValueError("Invalid provider envelope.")
    message = raw["message"]
    if (
        set(message) != {"role", "content"}
        or message["role"] != "assistant"
        or type(message["content"]) is not str
        or not message["content"].strip()
    ):
        raise ValueError("Invalid provider message.")
    # Bound UTF-8 before constructing ModelReply (including invalid surrogates).
    if len(message["content"].encode("utf-8")) > request.max_reply_bytes:
        raise LiveExecutionError(LiveFailureCategory.OUTPUT_TOO_LARGE)
    return checked_reply(
        request,
        ModelReply(
            selection=request.selection,
            text=message["content"],
            usage=ModelUsage(
                input_tokens=_usage_count(raw.get("prompt_eval_count")),
                output_tokens=_usage_count(raw.get("eval_count")),
            ),
        ),
    )


class LocalModelGateway:
    """Fixed-loopback, nonstreaming Ollama ``POST /api/chat`` adapter.

    Args:
        endpoint: Must exactly equal the application-owned numeric endpoint.
            No URL normalization, DNS, userinfo, other port/path or override.
        transport: Optional trusted test-owned HTTPX transport, constructed in
            the child factory. Never obtained from ModelRequest or model output.
            Production uses AsyncHTTPTransport with zero retries/no proxy.

    Raises:
        LiveExecutionError: Sanitized unexpected-provider failure for a refused
            endpoint. Construction never contacts a service.
    """

    def __init__(
        self,
        *,
        endpoint: str = LOCAL_CHAT_ENDPOINT,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if type(endpoint) is not str or endpoint != LOCAL_CHAT_ENDPOINT:
            _fail(LiveFailureCategory.UNEXPECTED_PROVIDER_FAILURE)
        self._transport = transport

    async def complete(self, request: ModelRequest) -> ModelReply:
        """Translate one validated request, with no retry/fallback/role repair.

        Socket timeouts and a total async timeout use the supplied call bound;
        the accepted parent process supervisor remains the deadline authority.
        Raw transport/JSON failures never cross this public boundary.

        Raises:
            LiveExecutionError: Closed transport, size or envelope failure.
        """
        category = LiveFailureCategory.UNEXPECTED_PROVIDER_FAILURE
        try:
            # Revalidate unchecked copies; refuse undeclared request state.
            if type(request) is not ModelRequest or set(request.__dict__) != set(
                ModelRequest.model_fields
            ):
                raise ValueError("Invalid request.")
            request = ModelRequest.model_validate(request.model_dump(warnings="error"))
            if request.selection.provider != "ollama":
                raise ValueError("Wrong provider.")
            timeout = request.timeout_ms / 1000
            transport = self._transport
            if transport is None:
                transport = httpx.AsyncHTTPTransport(retries=0, trust_env=False)
            async with asyncio.timeout(timeout):
                async with httpx.AsyncClient(
                    transport=transport,
                    trust_env=False,
                    follow_redirects=False,
                    timeout=httpx.Timeout(timeout),
                    headers={"Accept-Encoding": "identity"},
                ) as client:
                    async with client.stream(
                        "POST",
                        LOCAL_CHAT_ENDPOINT,
                        json={
                            "model": request.selection.model,
                            "messages": [{"role": "user", "content": request.prompt}],
                            "stream": False,
                            "options": {"num_predict": request.max_output_tokens},
                        },
                    ) as response:
                        if response.status_code != 200:
                            categories = {
                                401: LiveFailureCategory.PROVIDER_AUTHENTICATION_FAILED,
                                403: LiveFailureCategory.PROVIDER_AUTHORIZATION_FAILED,
                                429: LiveFailureCategory.RATE_LIMITED,
                            }
                            category = categories.get(response.status_code, category)
                            if 500 <= response.status_code <= 599:
                                category = LiveFailureCategory.PROVIDER_SERVICE_FAILED
                            raise LiveExecutionError(category)
                        if (
                            response.headers.get("content-encoding", "identity")
                            != "identity"
                            or response.headers.get("content-type", "")
                            .split(";", 1)[0]
                            .strip()
                            .lower()
                            != "application/json"
                        ):
                            raise ValueError("Unexpected representation.")
                        bound = request.max_reply_bytes * 6 + ENVELOPE_BYTES
                        body = bytearray()
                        async for chunk in response.aiter_raw():
                            if len(chunk) > bound - len(body):
                                raise LiveExecutionError(
                                    LiveFailureCategory.OUTPUT_TOO_LARGE
                                )
                            body.extend(chunk)
                        return _translate(request, bytes(body))
        except LiveExecutionError as error:
            category = error.category
        except (TimeoutError, httpx.TimeoutException):
            category = LiveFailureCategory.TIMED_OUT
        except (httpx.NetworkError, httpx.RemoteProtocolError):
            category = LiveFailureCategory.CONNECTION_FAILED
        except Exception:
            # Last-resort translation at the provider boundary: transport and
            # response decoding can raise library-specific exceptions. They
            # become a closed failure, never success or a retry. Cancellation
            # (BaseException) is deliberately not intercepted.
            category = LiveFailureCategory.UNEXPECTED_PROVIDER_FAILURE
        # Outside handlers: no raw exception retained as cause or context.
        _fail(category)
