"""Render fixed application templates with the real LangChain f-string formatter.

Input mistakes have safe domain errors. Invalid application template definitions
and unexpected library defects propagate: they are programmer faults, not
rejected user content. No arbitrary template text or format-engine argument is
accepted, and values are never recursively interpreted as templates.
"""

from collections.abc import Mapping

from langchain_core.prompts import PromptTemplate

from ..errors import TemplateRenderingError
from ..prompts.templates import TEMPLATE_TEXTS


def render_template(template_id: str, variables: Mapping[str, str]) -> str:
    """Render one approved template with exactly its required text variables.

    Each value is limited to 16,384 Python characters, enough for bounded JSON
    example encoding. At most four values are allowed. These local rendering
    bounds supplement the prompt builder's aggregate character budget.

    Args:
        template_id: Identifier of an application-owned f-string template.
        variables: Literal text values; keys must exactly match required names.

    Returns:
        Formatted text without message-role authority.

    Raises:
        TemplateRenderingError: For unapproved templates, missing/unexpected
            variables, or incorrectly typed/oversized values. Values and unknown
            keys are omitted from diagnostics.
    """
    if type(template_id) is not str or template_id not in TEMPLATE_TEXTS:
        raise TemplateRenderingError("Select an application-owned template identifier.")
    if not isinstance(variables, Mapping) or len(variables) > 4:
        raise TemplateRenderingError("Supply a mapping of at most four text variables.")
    template = PromptTemplate.from_template(
        TEMPLATE_TEXTS[template_id], template_format="f-string"
    )
    required = set(template.input_variables)
    supplied = set(variables)
    if required - supplied:
        raise TemplateRenderingError("Supply all required template variables.")
    if supplied - required:
        raise TemplateRenderingError("Remove unexpected template variables.")
    if any(
        type(value) is not str or len(value) > 16_384 for value in variables.values()
    ):
        raise TemplateRenderingError(
            "Template values must be text within 16384 characters."
        )
    # Missing/extra/type failures were handled above. Formatter failures with
    # this trusted template and complete text values are unexpected defects.
    return template.format(**variables)
