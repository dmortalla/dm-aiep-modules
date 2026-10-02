"""Provider-independent asynchronous LLM interaction service."""

import asyncio
import logging
from collections.abc import AsyncIterator, Mapping

from .base import AsyncLLMProvider
from .models import LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


class UnknownProviderError(ValueError):
    """Represent a request for an unregistered LLM provider."""


class LLMServiceError(RuntimeError):
    """Represent a provider failure at the service boundary."""


class LLMService:
    """Coordinate provider-independent asynchronous LLM interactions."""

    def __init__(
        self,
        providers: Mapping[str, AsyncLLMProvider] | None = None,
    ) -> None:
        """Initialize the service with optional named providers.

        Args:
            providers: Mapping of provider names to provider implementations.
        """
        self._providers: dict[str, AsyncLLMProvider] = dict(providers or {})

    @property
    def provider_names(self) -> tuple[str, ...]:
        """Return registered provider names in deterministic order."""

        return tuple(sorted(self._providers))

    def register_provider(
        self,
        name: str,
        provider: AsyncLLMProvider,
    ) -> None:
        """Register or replace a named LLM provider."""

        normalized_name = name.strip().lower()

        if not normalized_name:
            raise ValueError("provider name cannot be empty")

        self._providers[normalized_name] = provider

        logger.info(
            "Registered LLM provider: %s",
            normalized_name,
        )

    def get_provider(self, name: str) -> AsyncLLMProvider:
        """Return a registered provider or raise a clear error."""

        normalized_name = name.strip().lower()

        try:
            return self._providers[normalized_name]
        except KeyError as exc:
            available = ", ".join(self.provider_names) or "none"
            raise UnknownProviderError(
                f"Unknown provider '{name}'. Available providers: {available}."
            ) from exc

    async def generate(
        self,
        provider_name: str,
        request: LLMRequest,
    ) -> LLMResponse:
        """Generate one response through the selected provider."""

        provider = self.get_provider(provider_name)
        normalized_name = provider_name.strip().lower()

        logger.info(
            "Starting LLM generation provider=%s model=%s",
            normalized_name,
            request.model,
        )

        try:
            response = await provider.generate(request)
        except Exception as exc:
            logger.exception(
                "LLM generation failed provider=%s model=%s",
                normalized_name,
                request.model,
            )
            raise LLMServiceError(
                f"LLM generation failed for provider '{normalized_name}'."
            ) from exc

        logger.info(
            "Completed LLM generation provider=%s model=%s",
            normalized_name,
            request.model,
        )

        return response

    async def stream(
        self,
        provider_name: str,
        request: LLMRequest,
    ) -> AsyncIterator[str]:
        """Stream one response through the selected provider."""

        provider = self.get_provider(provider_name)
        normalized_name = provider_name.strip().lower()

        logger.info(
            "Starting LLM stream provider=%s model=%s",
            normalized_name,
            request.model,
        )

        try:
            async for chunk in provider.stream(request):
                yield chunk
        except Exception as exc:
            logger.exception(
                "LLM streaming failed provider=%s model=%s",
                normalized_name,
                request.model,
            )
            raise LLMServiceError(
                f"LLM streaming failed for provider '{normalized_name}'."
            ) from exc

        logger.info(
            "Completed LLM stream provider=%s model=%s",
            normalized_name,
            request.model,
        )

    async def generate_many(
        self,
        requests: list[tuple[str, LLMRequest]],
    ) -> list[LLMResponse]:
        """Generate multiple independent responses concurrently."""

        tasks = [
            self.generate(provider_name, request)
            for provider_name, request in requests
        ]

        return list(await asyncio.gather(*tasks))
