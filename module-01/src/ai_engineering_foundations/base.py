"""Abstract contract for asynchronous LLM providers."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from .models import LLMRequest, LLMResponse


class AsyncLLMProvider(ABC):
    """Define the common interface implemented by LLM providers."""

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate one complete LLM response."""

    @abstractmethod
    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream text chunks from an LLM response."""
        if False:
            yield ""
