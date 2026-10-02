"""Explicit OpenAI Chat Completions JSON Mode; no client or network on import.

Application code supplies an already-configured SDK client. Credentials stay
inside that client; this adapter neither accepts nor reads keys/environment data.
JSON formatting is distinct from the workflow's mandatory local validation.
"""

from typing import Literal

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)
from openai.types.chat import ChatCompletionMessageParam
from pydantic import ConfigDict, Field, ValidationError

from ..contracts import StrictContract
from ..errors import (
    ProviderAvailabilityError,
    ProviderRequestError,
    ProviderResponseError,
)
from ..prompts.construction import ConstructedPrompt
from .generation import ProviderOutput


class OpenAIConfiguration(StrictContract):
    """Bounded application configuration without credential-bearing fields.

    Attributes:
        model: Explicit application-selected model identifier, 1..128 characters.
        max_completion_tokens: Completion allowance, 1..4,096; default 1,024.
        timeout_seconds: SDK request timeout, 1..120 seconds; default 30. This is
            an SDK timeout, not an end-to-end measured wall-clock guarantee.

    Raises:
        ValidationError: If direct construction violates strict types/bounds.
    """

    model_config = ConfigDict(frozen=True)
    model: str = Field(min_length=1, max_length=128)
    max_completion_tokens: int = Field(default=1_024, ge=1, le=4_096)
    timeout_seconds: float = Field(default=30.0, ge=1, le=120)


class OpenAIJSONModeProvider:
    """Generate bounded untrusted text using an injected application SDK client.

    Evidence mode must be explicitly declared by application/test code. Supplying
    a mock client is not live verification. No raw client appears in module repr.
    """

    def __init__(
        self,
        client: OpenAI,
        configuration: OpenAIConfiguration,
        *,
        mode: Literal["mocked", "live"],
    ) -> None:
        """Capture trusted configuration and a client without making a request.

        Args:
            client: Application-owned real OpenAI client or injected test mock.
            configuration: Bounded application model and request settings.
            mode: Explicit mocked/live origin; no credential/environment inference.

        Raises:
            ProviderRequestError: For invalid configuration or evidence mode.
        """
        if mode not in ("mocked", "live"):
            raise ProviderRequestError("Select mocked or live provider evidence mode.")
        try:
            self._configuration = OpenAIConfiguration.model_validate(configuration)
        except ValidationError:
            raise ProviderRequestError(
                "Correct bounded OpenAI configuration fields."
            ) from None
        self._client = client
        self._mode = mode

    def generate(self, prompt: ConstructedPrompt) -> ProviderOutput:
        """Preserve message roles and reject unsuccessful completion conditions.

        SDK retries are disabled for this operation. Public messages omit unsafe
        SDK causes, including their request headers, payloads, and credentials.

        Args:
            prompt: Trusted builder output; content keeps its existing role.

        Returns:
            Bounded untrusted content with explicit evidence origin, no SDK object.

        Raises:
            ProviderRequestError: For authentication, permission, or bad requests.
            ProviderAvailabilityError: For timeout, rate, connection, or API failure.
            ProviderResponseError: For refusal, truncation, missing/empty content,
                unexpected finish condition, tool proposals, or excessive content.
                Unexpected programming/library defects propagate unchanged.
        """
        messages: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": "Return exactly one JSON object. Return JSON only.",
            }
        ]
        for component in prompt.components:
            if component.role == "system":
                messages.append({"role": "system", "content": component.content})
            else:
                messages.append({"role": "user", "content": component.content})
        config = self._configuration
        try:
            completion = self._client.with_options(
                max_retries=0
            ).chat.completions.create(
                model=config.model,
                messages=messages,
                response_format={"type": "json_object"},
                max_completion_tokens=config.max_completion_tokens,
                timeout=config.timeout_seconds,
                n=1,
                stream=False,
            )
        except AuthenticationError:
            raise ProviderRequestError(
                "OpenAI authentication failed; correct client credentials."
            ) from None
        except PermissionDeniedError:
            raise ProviderRequestError(
                "OpenAI access denied; check application model permissions."
            ) from None
        except BadRequestError:
            raise ProviderRequestError(
                "OpenAI rejected JSON Mode settings; check model compatibility."
            ) from None
        except RateLimitError:
            raise ProviderAvailabilityError(
                "OpenAI rate limit reached; retry later."
            ) from None
        except APITimeoutError:
            raise ProviderAvailabilityError(
                "OpenAI request timed out; retry or reduce output."
            ) from None
        except APIConnectionError:
            raise ProviderAvailabilityError(
                "OpenAI connection failed; check connectivity later."
            ) from None
        except (APIStatusError, APIError):
            raise ProviderAvailabilityError(
                "OpenAI API failed; retry later or inspect provider health."
            ) from None
        if len(completion.choices) != 1:
            raise ProviderResponseError(
                "Expected exactly one OpenAI completion choice."
            )
        choice = completion.choices[0]
        if choice.message.refusal is not None:
            raise ProviderResponseError(
                "OpenAI refused this request; revise the application task."
            )
        if choice.finish_reason == "length":
            raise ProviderResponseError(
                "OpenAI completion truncated; reduce requested output."
            )
        if choice.finish_reason != "stop" or choice.message.tool_calls:
            raise ProviderResponseError(
                "OpenAI completion is incomplete or unsupported; reject output."
            )
        content = choice.message.content
        if content is None or not content.strip():
            raise ProviderResponseError(
                "OpenAI returned no content; revise the request."
            )
        if len(content) > 65_536:
            raise ProviderResponseError(
                "OpenAI response exceeds the supported character limit."
            )
        return ProviderOutput(mode=self._mode, text=content)
