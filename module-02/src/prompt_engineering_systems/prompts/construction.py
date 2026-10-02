"""Build inspectable role-bearing prompts without promoting content into policy.

Only trusted ApplicationInstructions create system components. User-selected
role framing, context, examples, and requests produce user components even when
their text resembles system instructions. Keep this structure when integrating
a provider later; flattening it into one string discards this authority boundary.
This is a structural foundation, not universal prompt-injection prevention.
"""

import json
from typing import Literal, Self

from pydantic import ConfigDict, Field, ValidationError, model_validator

from ..contracts import StrictContract
from ..errors import PromptConstructionError
from ..integrations.langchain_templates import render_template
from .context import ContextRecord, ContextSelection, select_context
from .templates import role_framing


class ApplicationInstructions(StrictContract):
    """Trusted configuration supplied by application code, never external input.

    Type validation cannot establish trust: a later UI must not populate this
    object from user/context/model data. Author these fields in application code.

    Attributes:
        policy: Application policy text, 1..4,096 characters.
        task: Application task description, 1..4,096 characters.
        output_contract: Trusted output instructions, 1..8,192 characters.

    Raises:
        ValidationError: If direct construction violates strict fields or bounds.
    """

    model_config = ConfigDict(frozen=True)
    policy: str = Field(min_length=1, max_length=4_096)
    task: str = Field(min_length=1, max_length=4_096)
    output_contract: str = Field(min_length=1, max_length=8_192)


class FewShotExample(StrictContract):
    """A bounded input/output pair presented entirely as lower-trust content.

    Attributes:
        example_id: Nonempty identity, at most 128 characters.
        provenance: Nonempty source label, at most 256 characters.
        input: Literal example input, 1..1,024 characters.
        output: Literal example output, 1..1,024 characters.

    Raises:
        ValidationError: If direct construction violates strict fields or bounds.
    """

    model_config = ConfigDict(frozen=True)
    example_id: str = Field(min_length=1, max_length=128)
    provenance: str = Field(min_length=1, max_length=256)
    input: str = Field(min_length=1, max_length=1_024)
    output: str = Field(min_length=1, max_length=1_024)


class PromptLimits(StrictContract):
    """Character budgets for an instructional prompt, not exact token counts.

    Attributes:
        context_characters: Selected raw context content ceiling; default 8,192,
            range 0..32,768. Oversized whole records are skipped.
        example_characters: Sum of raw example input/output lengths; default
            4,096, range 0..16,384. Excess examples fail without truncation.
        prompt_characters: All rendered component content plus identity/provenance
            text; default 32,768, range 1..65,536. This excludes transport framing
            and role/kind labels; excess prompts fail without partial output.

    Raises:
        ValidationError: If direct construction violates strict fields or bounds.
    """

    model_config = ConfigDict(frozen=True)
    context_characters: int = Field(default=8_192, ge=0, le=32_768)
    example_characters: int = Field(default=4_096, ge=0, le=16_384)
    prompt_characters: int = Field(default=32_768, ge=1, le=65_536)


class PromptSpecification(StrictContract):
    """External content and approved role selection, without policy or role fields.

    Tuples and frozen nested models avoid mutable-container surprises. The builder
    revalidates instances, including Pydantic model_copy/model_construct results.

    Attributes:
        user_request: Literal user request, 1..8,192 characters.
        role_id: Selection identifier, 1..128 characters; catalog checked by builder.
        context: At most 64 context records; identities must be unique.
        examples: At most eight examples with unique identities, in supplied order.
            Empty by default, yielding zero-shot construction.
        limits: Explicit aggregate character ceilings.

    Raises:
        ValidationError: If direct construction violates strict fields or bounds,
            or example identities repeat. Catalog/context identity validation
            occurs at the construction/selection boundary.
    """

    model_config = ConfigDict(frozen=True)
    user_request: str = Field(min_length=1, max_length=8_192)
    role_id: str = Field(default="teacher", min_length=1, max_length=128)
    context: tuple[ContextRecord, ...] = Field(default=(), max_length=64)
    examples: tuple[FewShotExample, ...] = Field(default=(), max_length=8)
    limits: PromptLimits = Field(default_factory=PromptLimits)

    @model_validator(mode="after")
    def unique_examples(self) -> Self:
        """Reject repeated example identities without reporting supplied content.

        Returns:
            This specification in its original example order.

        Raises:
            ValueError: If example identities repeat.
        """
        identifiers = [example.example_id for example in self.examples]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Example identities must be unique.")
        return self


class PromptComponent(StrictContract):
    """One inspectable component whose role is assigned by the builder.

    Attributes:
        kind: Anatomy label, independent of literal content.
        role: Structural system or user message role.
        content: Rendered text; never parsed for role delimiters.
        record_id: Optional context/example identity, retained as content metadata.
        provenance: Optional context/example source, never an authority claim.

    Raises:
        ValidationError: If direct construction violates strict fields or labels.
    """

    model_config = ConfigDict(frozen=True)
    kind: Literal[
        "policy", "task", "output_contract", "role", "example", "context", "request"
    ]
    role: Literal["system", "user"]
    content: str
    record_id: str | None = None
    provenance: str | None = None


class ConstructedPrompt(StrictContract):
    """Inspect the completed prompt and its bounded selection decisions.

    This output type is a representation, not an authorization capability. Only
    build_prompt establishes the documented construction contract.

    Attributes:
        components: Ordered messages: trusted components, role framing, examples,
            selected context, then request. Example pairs remain one user message.
        context_selection: Selected records and raw content character accounting.
        character_count: Rendered content and identity/provenance character sum.

    Raises:
        ValidationError: If direct construction violates strict fields or types.
    """

    model_config = ConfigDict(frozen=True)
    components: tuple[PromptComponent, ...]
    context_selection: ContextSelection
    character_count: int


def build_prompt(
    application: ApplicationInstructions, specification: PromptSpecification
) -> ConstructedPrompt:
    """Construct a complete structured prompt using real LangChain rendering.

    No content is scanned for instructions or promoted to privileged roles. The
    approved role influences user framing only. Example JSON encoding preserves
    literal input/output boundaries; it is not a hostile-word sanitizer.

    Args:
        application: Trusted application-authored policy, task, and output contract.
        specification: User content, role selection, provenance, examples, limits.

    Returns:
        Inspectable deterministic components with structural roles and provenance.

    Raises:
        PromptConstructionError: For invalid strict inputs, unknown roles,
            ambiguous identities, or exceeded example/prompt character budgets.
        TemplateRenderingError: For invalid inputs at the template boundary.
            Unexpected library/programmer failures propagate unchanged.
    """
    try:
        trusted = ApplicationInstructions.model_validate(application)
        data = PromptSpecification.model_validate(specification)
    except ValidationError:
        raise PromptConstructionError(
            "Supply valid strict application instructions and prompt specification."
        ) from None
    framing = role_framing(data.role_id)
    if sum(len(item.input) + len(item.output) for item in data.examples) > (
        data.limits.example_characters
    ):
        raise PromptConstructionError(
            "Example character budget exceeded; reduce examples."
        )
    selection = select_context(
        f"{trusted.task} {data.user_request}",
        data.context,
        character_budget=data.limits.context_characters,
    )
    components = [
        PromptComponent(
            kind="policy",
            role="system",
            content=render_template("policy", {"instructions": trusted.policy}),
        ),
        PromptComponent(
            kind="task",
            role="system",
            content=render_template("task", {"task": trusted.task}),
        ),
        PromptComponent(
            kind="output_contract",
            role="system",
            content=render_template(
                "output_contract", {"instructions": trusted.output_contract}
            ),
        ),
        PromptComponent(
            kind="role",
            role="user",
            content=render_template("role", {"framing": framing}),
        ),
    ]
    for example in data.examples:
        components.append(
            PromptComponent(
                kind="example",
                role="user",
                content=render_template(
                    "example",
                    {
                        "input": json.dumps(example.input),
                        "output": json.dumps(example.output),
                    },
                ),
                record_id=example.example_id,
                provenance=example.provenance,
            )
        )
    for record in selection.records:
        components.append(
            PromptComponent(
                kind="context",
                role="user",
                content=render_template("context", {"content": record.content}),
                record_id=record.record_id,
                provenance=record.provenance,
            )
        )
    components.append(
        PromptComponent(
            kind="request",
            role="user",
            content=render_template("request", {"request": data.user_request}),
        )
    )
    character_count = sum(
        len(item.content) + len(item.record_id or "") + len(item.provenance or "")
        for item in components
    )
    if character_count > data.limits.prompt_characters:
        raise PromptConstructionError(
            "Prompt character budget exceeded; reduce content "
            "or select a larger budget."
        )
    return ConstructedPrompt(
        components=tuple(components),
        context_selection=selection,
        character_count=character_count,
    )
