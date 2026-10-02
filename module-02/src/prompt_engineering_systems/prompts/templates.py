"""Application-owned framing and f-string templates; external text is never a template.

These catalogs are trusted code/configuration. Role framing is emitted as user
content, independently of application policy. No generation or observation
protocol is needed for this local rendering boundary.
"""

from types import MappingProxyType

from ..errors import PromptConstructionError

APPROVED_ROLES = MappingProxyType(
    {
        "teacher": "Explain the task clearly with concrete teaching examples.",
        "reviewer": "Review the task critically and identify supported limitations.",
    }
)

TEMPLATE_TEXTS = MappingProxyType(
    {
        "policy": "Application policy:\n{instructions}",
        "task": "Application task:\n{task}",
        "output_contract": "Output contract:\n{instructions}",
        "role": "Selected task framing:\n{framing}",
        "request": "User request (content):\n{request}",
        "context": "Context (content):\n{content}",
        # json.dumps supplies the two values; the outer braces are trusted syntax.
        "example": 'Example (content):\n{{"input": {input}, "output": {output}}}',
    }
)


def role_framing(role_id: str) -> str:
    """Resolve only application-approved role identifiers without echoing input.

    Args:
        role_id: User selection from the application catalog.

    Returns:
        Application-authored task framing, never replacement system policy.

    Raises:
        PromptConstructionError: If the identifier is unknown or has wrong type.
    """
    if type(role_id) is not str or role_id not in APPROVED_ROLES:
        raise PromptConstructionError("Select an approved role: teacher or reviewer.")
    return APPROVED_ROLES[role_id]
