"""Provider-neutral model boundary: one method, typed request and reply.

This is an interface only. No adapter, HTTP client, SDK call or credential
lookup exists in this module, and nothing here can reach a model. The gateway
does not authorize runs or decide budgets; the application does both before a
gateway is ever constructed and passes each call its bounds explicitly.
"""

from typing import Annotated, Literal, Protocol, runtime_checkable

from pydantic import Field

from .contracts import GraphRole
from .live_contracts import (
    MAX_DEADLINE_MS,
    MAX_OUTPUT_TOKENS,
    MAX_REPLY_BYTES,
    LiveContract,
    ModelSelection,
    ModelUsage,
)
from .live_errors import LiveExecutionError, LiveFailureCategory

MAX_PROMPT_CHARS = 8192


class ModelRequest(LiveContract):
    """One application-authored completion request; carries no credential.

    There is no tool, capability, fallback model or retry field, so a request
    cannot ask an adapter for anything beyond one bounded completion from the
    one selected model.
    """

    selection: ModelSelection
    role: Literal[GraphRole.RESEARCHER, GraphRole.ANALYST, GraphRole.CRITIC]
    prompt: Annotated[
        str, Field(strict=True, min_length=1, max_length=MAX_PROMPT_CHARS)
    ] = Field(repr=False)
    max_output_tokens: Annotated[int, Field(strict=True, ge=1, le=MAX_OUTPUT_TOKENS)]
    max_reply_bytes: Annotated[int, Field(strict=True, ge=1, le=MAX_REPLY_BYTES)]
    timeout_ms: Annotated[int, Field(strict=True, ge=1, le=MAX_DEADLINE_MS)]


class ModelReply(LiveContract):
    """Untrusted candidate reply; text is data until application validation."""

    selection: ModelSelection
    text: Annotated[str, Field(strict=True, max_length=MAX_REPLY_BYTES)] = Field(
        repr=False
    )
    usage: ModelUsage = Field(default_factory=ModelUsage)


@runtime_checkable
class ModelGateway(Protocol):
    """Trusted adapter code returning an untrusted reply for one request."""

    async def complete(self, request: ModelRequest) -> ModelReply:
        """Make exactly one attempt against the request's selected model.

        An implementation must not retry, substitute another provider or model,
        read authorization or budget from anywhere but the request, or raise
        anything carrying provider text or a credential.

        Args:
            request: Validated application request with explicit bounds.

        Returns:
            Candidate reply requiring ``checked_reply`` and role validation.

        Raises:
            LiveExecutionError: A closed, sanitized failure category.
        """
        ...


def checked_reply(request: ModelRequest, raw: object) -> ModelReply:
    """Revalidate a gateway reply against the request the application made.

    Args:
        request: The request the application sent.
        raw: Untrusted adapter output, including constructed objects.

    Returns:
        A fresh reply known to come from the selected model within its bound.

    Raises:
        LiveExecutionError: ``unexpected_provider_failure`` when the reply is
            not an owned, valid ``ModelReply`` or names a different provider or
            model than was selected; ``output_too_large`` when its text exceeds
            the request's byte bound.
    """
    reply_valid = False
    try:
        if type(raw) is not ModelReply or set(raw.__dict__) != set(
            ModelReply.model_fields
        ):
            raise ValueError("Not an owned gateway reply.")
        reply = ModelReply.model_validate(raw.model_dump(warnings="error"))
        size = len(reply.text.encode("utf-8"))
        reply_valid = True
    except (ValueError, TypeError, AttributeError):
        pass
    if not reply_valid:
        raise LiveExecutionError(
            LiveFailureCategory.UNEXPECTED_PROVIDER_FAILURE
        ) from None
    if reply.selection != request.selection:
        # A different model answering is a silent substitution, never success.
        raise LiveExecutionError(LiveFailureCategory.UNEXPECTED_PROVIDER_FAILURE)
    if size > request.max_reply_bytes:
        raise LiveExecutionError(LiveFailureCategory.OUTPUT_TOO_LARGE)
    return reply
