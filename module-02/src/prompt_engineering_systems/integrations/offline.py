"""Explicit credential-free deterministic output; never live OpenAI evidence."""

from ..prompts.construction import ConstructedPrompt
from .generation import ProviderOutput


class OfflineProvider:
    """Return a configured demonstration response without network or credentials.

    Invalid JSON examples deliberately remain invalid for workflow tests. This
    provider establishes only a bounded raw-text contract, not schema conformity.
    """

    def __init__(
        self, text: str = '{"answer":"Offline demonstration.","sources":[]}'
    ) -> None:
        """Configure one deterministic bounded demonstration response.

        Args:
            text: Application-authored example; may be invalid JSON intentionally.

        Raises:
            ValidationError: If text is not a bounded strict string.
        """
        self._output = ProviderOutput(mode="offline", text=text)

    def generate(self, prompt: ConstructedPrompt) -> ProviderOutput:
        """Return the same offline content without interpreting prompt instructions.

        Args:
            prompt: Structured application prompt; no instruction executes locally.

        Returns:
            Explicitly offline untrusted text for the shared validation pipeline.
        """
        return self._output
