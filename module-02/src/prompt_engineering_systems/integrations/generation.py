"""Minimal raw generation boundary shared by offline and OpenAI providers."""

from typing import Literal, Protocol

from pydantic import ConfigDict, Field

from ..contracts import StrictContract
from ..prompts.construction import ConstructedPrompt

type EvidenceMode = Literal["offline", "mocked", "live"]


class ProviderOutput(StrictContract):
    """Bounded untrusted provider text, never an accepted application answer.

    Attributes:
        mode: Evidence origin; mock/offline output is not live verification.
        text: Raw content, at most 65,536 characters; omitted from model repr.
            Story 2 additionally enforces UTF-8 byte and document limits.

    Raises:
        ValidationError: If direct construction violates strict fields or limits.
    """

    model_config = ConfigDict(frozen=True)
    mode: EvidenceMode
    text: str = Field(max_length=65_536, repr=False)


class GenerationProvider(Protocol):
    """One generation operation; no tools, observers, or provider orchestration."""

    def generate(self, prompt: ConstructedPrompt) -> ProviderOutput:
        """Return untrusted bounded text for subsequent local validation.

        Args:
            prompt: Application-constructed prompt preserving structural roles.

        Returns:
            Raw generation content and explicit evidence mode.
        """
        ...
