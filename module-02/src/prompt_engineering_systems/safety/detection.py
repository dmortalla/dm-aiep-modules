"""Bounded explainable lexical indicators; findings never authorize execution.

Case-folded phrase matching deliberately does not decode encodings or handle all
obfuscation. Matches can be benign quotations, and missed attacks remain possible.
No payload excerpts enter findings. Story 3 roles/provenance remain untouched.
"""

from pydantic import ConfigDict

from ..contracts import StrictContract
from ..errors import SafetyInputError


class DetectionFinding(StrictContract):
    """One application-authored explanation, without attacker payload excerpts.

    Attributes:
        indicator_id: Stable rule identifier in catalog order.
        category: Instruction injection or jailbreak indicator category.
        explanation: Fixed explanation of the matched rule, not intent certainty.

    Raises:
        ValidationError: If direct construction violates strict field types.
    """

    model_config = ConfigDict(frozen=True)
    indicator_id: str
    category: str
    explanation: str


_RULES = (
    (
        "instruction_override",
        "injection",
        "Attempts to override instruction hierarchy.",
        ("ignore previous instructions", "ignore prior instructions"),
    ),
    (
        "role_impersonation",
        "injection",
        "Contains privileged-role impersonation syntax.",
        ("system:", "developer:", "<|im_start|>system", "<system>"),
    ),
    (
        "protected_extraction",
        "injection",
        "Requests protected instructions or secrets.",
        ("reveal system prompt", "reveal secrets", "print environment variables"),
    ),
    (
        "restriction_bypass",
        "jailbreak",
        "Requests disabling application restrictions.",
        ("bypass restrictions", "disable safety", "unrestricted mode"),
    ),
    (
        "unauthorized_execution",
        "jailbreak",
        "Requests external execution capabilities.",
        ("execute shell", "run arbitrary code", "use unauthorized tool"),
    ),
)


def detect_indicators(content: str) -> tuple[DetectionFinding, ...]:
    """Inspect bounded text using fixed phrases, without modifying authority.

    Apply separately to selected prompt components to preserve Story 3 structure.
    Only strings are consumed; no role/provenance fields are reconstructed.

    Args:
        content: Literal text, at most 16,384 Python characters; empty is allowed.

    Returns:
        Matched rule explanations in catalog order, each at most once. An empty
        tuple means no rule matched, not that content is safe or authorized.

    Raises:
        SafetyInputError: For non-text or excessive input; nothing is truncated.
    """
    if type(content) is not str or len(content) > 16_384:
        raise SafetyInputError(
            "Inspect text within the 16384-character detector limit."
        )
    normalized = content.casefold()
    return tuple(
        DetectionFinding(
            indicator_id=identity, category=category, explanation=explanation
        )
        for identity, category, explanation, phrases in _RULES
        if any(phrase in normalized for phrase in phrases)
    )
