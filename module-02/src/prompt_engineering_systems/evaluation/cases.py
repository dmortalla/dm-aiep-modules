"""Versioned synthetic cases; fixture content never supplies application policy."""

import re
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, ConfigDict, Field, ValidationError, model_validator

from ..contracts import StrictContract, ValidationLimits
from ..errors import (
    EvaluationError,
    JSONParsingError,
    SchemaDefinitionError,
    StructuredOutputError,
    ValidationLimitError,
)
from ..prompts.construction import PromptSpecification
from ..prompts.context import ContextRecord
from ..prompts.techniques import ReActStep
from ..structured._bounds import inspect_json
from ..structured.validation import validate_typed_output


def _identifier(value: str) -> str:
    if re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", value) is None:
        raise ValueError("Use a restricted stable identifier.")
    return value


type Identifier = Annotated[
    str, Field(min_length=1, max_length=64), AfterValidator(_identifier)
]
type AttackClass = Literal[
    "direct",
    "context",
    "role_spoof",
    "jailbreak",
    "unauthorized_action",
    "policy_override",
]


class EvaluationCase(StrictContract):
    """Bounded case identity, content and deterministic expected criteria.

    Attributes:
        case_id: Stable restricted identifier, never a payload excerpt.
        version: Positive fixture revision.
        provenance: Synthetic source marker; currently only authored fixtures.
        category: Normal, control or attack.
        request: Literal lower-trust request.
        context: Optional lower-trust synthetic context.
        expected_answer: Optional exact answer criterion (no semantic quality claim).
        expected_authorization: Optional independent tool-authorization criterion.
        attack_class: Representative class for an attack/control pair.
        control_id: Control reference for attacks only.
        proposal: Optional synthetic action shape; never authorization.
    """

    model_config = ConfigDict(frozen=True)
    case_id: Identifier
    version: int = Field(ge=1, le=1000)
    provenance: Literal["synthetic-v1"] = "synthetic-v1"
    category: Literal["normal", "control", "attack"] = "normal"
    request: str = Field(min_length=1, max_length=4096, repr=False)
    context: str | None = Field(default=None, min_length=1, max_length=4096, repr=False)
    expected_answer: str | None = Field(
        default=None, min_length=1, max_length=1024, repr=False
    )
    expected_authorization: Literal["allowed", "denied"] | None = None
    attack_class: AttackClass | None = None
    control_id: Identifier | None = None
    proposal: ReActStep | None = Field(default=None, repr=False)

    @model_validator(mode="after")
    def unambiguous(self) -> Self:
        """Reject conflicting case/pair/criterion shapes."""
        if not self.request.strip():
            raise ValueError("Case request must be nonblank.")
        if self.category == "normal":
            if self.attack_class is not None or self.control_id is not None:
                raise ValueError("Normal cases cannot carry attack pairing.")
        elif self.attack_class is None or (
            (self.category == "attack") != (self.control_id is not None)
        ):
            raise ValueError("Attack/control definitions need consistent pairing.")
        if self.expected_answer is None and self.expected_authorization is None:
            raise ValueError("Supply a deterministic expected criterion.")
        if self.proposal is not None and self.proposal.kind != "action":
            raise ValueError("Simulation proposals must be actions.")
        if (self.expected_authorization is not None) != (self.proposal is not None):
            raise ValueError("Authorization criteria require a proposed action.")
        if self.proposal is not None:
            try:
                inspect_json(
                    self.proposal.model_dump(),
                    ValidationLimits(max_text_bytes=16384, max_nodes=16, max_depth=4),
                )
            except (JSONParsingError, ValidationLimitError):
                raise ValueError(
                    "Keep synthetic proposals within local action bounds."
                ) from None
        return self

    def specification(self) -> PromptSpecification:
        """Return Story 3 lower-trust content with explicit synthetic provenance."""
        context = (
            ()
            if self.context is None
            else (
                ContextRecord(
                    record_id=self.case_id,
                    provenance=self.provenance,
                    content=self.context,
                ),
            )
        )
        return PromptSpecification(user_request=self.request, context=context)


class CaseSuite(StrictContract):
    """At most 32 unique cases with supported format and valid control references."""

    model_config = ConfigDict(frozen=True)
    format_version: Literal[1] = 1
    cases: tuple[EvaluationCase, ...] = Field(max_length=32)

    @model_validator(mode="after")
    def identities(self) -> Self:
        """Reject duplicate identifiers and missing/mismatched controls."""
        lookup = {case.case_id: case for case in self.cases}
        if len(lookup) != len(self.cases):
            raise ValueError("Case identifiers must be unique across versions.")
        for case in self.cases:
            if case.category == "attack":
                control = lookup.get(case.control_id)
                if (
                    control is None
                    or control.category != "control"
                    or control.attack_class != case.attack_class
                    or control.version != case.version
                ):
                    raise ValueError("Attack requires a matching versioned control.")
        return self


def validate_suite(suite: CaseSuite) -> CaseSuite:
    """Revalidate even forged/copied models, translating content-bearing errors.

    Args:
        suite: Application-supplied typed suite.

    Returns:
        Revalidated suite.

    Raises:
        EvaluationError: For invalid definitions, without payload diagnostics.
    """
    try:
        return CaseSuite.model_validate(suite)
    except ValidationError:
        raise EvaluationError(
            "Correct bounded unique versioned evaluation cases."
        ) from None


class _CaseDocument(StrictContract):
    """JSON array wire shape; convert to immutable tuple only after validation."""

    format_version: Literal[1] = 1
    cases: list[EvaluationCase] = Field(max_length=32)


def load_cases(text: str) -> CaseSuite:
    """Load bounded JSON through the accepted Story 2 validation pipeline.

    Args:
        text: Synthetic JSON document, at most 128 KiB.

    Returns:
        Validated versioned cases, preserving supplied identity/provenance.

    Raises:
        EvaluationError: For malformed, unsupported or ambiguous definitions.
        SchemaDefinitionError: For defects in the application-owned wire schema.
    """
    try:
        document = validate_typed_output(
            text,
            _CaseDocument,
            # Nested case/action schema needs more depth than the flat answer schema.
            limits=ValidationLimits(
                max_text_bytes=131072, max_nodes=2048, max_depth=16
            ),
        )
        return CaseSuite(
            format_version=document.format_version, cases=tuple(document.cases)
        )
    except SchemaDefinitionError:
        raise
    except (StructuredOutputError, ValidationError):
        raise EvaluationError(
            "Correct bounded unique versioned evaluation JSON."
        ) from None
