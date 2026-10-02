"""UI-independent generation and schema labs composing existing validation.

Provider success grants no tool authority. Neither service executes proposed
actions, repairs malformed output, or depends on Streamlit.
"""

from dataclasses import dataclass

from .contracts import JSONValue, StrictContract, ValidationLimits
from .integrations.generation import EvidenceMode, GenerationProvider, ProviderOutput
from .prompts.construction import (
    ApplicationInstructions,
    PromptSpecification,
    build_prompt,
)
from .structured.schemas import Schema, validate_against_schema
from .structured.validation import parse_json_text, validate_typed_output


@dataclass(frozen=True)
class GenerationResult[Contract: StrictContract]:
    """Accepted application object without raw provider payload or SDK objects.

    Attributes:
        mode: Offline, mocked, or live origin; does not assert factual correctness.
        answer: Strictly validated application contract returned by the workflow.
    """

    mode: EvidenceMode
    answer: Contract


def generate_structured[Contract: StrictContract](
    application: ApplicationInstructions,
    specification: PromptSpecification,
    provider: GenerationProvider,
    contract: type[Contract],
    *,
    schema: Schema | None = None,
    limits: ValidationLimits | None = None,
) -> GenerationResult[Contract]:
    """Build a prompt and release a result only after Story 2 validation.

    Args:
        application: Trusted application-owned instructions.
        specification: Lower-trust request/context/examples and approved framing.
        provider: Explicitly chosen application provider, never a model callable.
        contract: Trusted strict model class defining accepted fields/invariants.
        schema: Optional bounded schema; defaults to the model-derived schema.
        limits: Optional Story 2 resource budgets.

    Returns:
        Typed validated answer with its evidence origin, without raw text.

    Raises:
        PromptConstructionError: For invalid prompt specifications.
        StructuredOutputError: For parsing/schema/typed validation failures.
        ValidationError: If a provider violates its raw-output contract.
            Unexpected provider or programmer faults propagate unchanged.
    """
    prompt = build_prompt(application, specification)
    output = ProviderOutput.model_validate(provider.generate(prompt))
    answer = validate_typed_output(output.text, contract, schema=schema, limits=limits)
    return GenerationResult(mode=output.mode, answer=answer)


def validate_schema_lab(
    text: str, schema: Schema, *, limits: ValidationLimits | None = None
) -> JSONValue:
    """Validate a schema-lab document using the existing bounded Story 2 policy.

    Args:
        text: Untrusted JSON document; no prose, coercion, or automatic repair.
        schema: Bounded Draft 2020-12 schema with supported local references only.
        limits: Optional existing document/schema resource ceilings.

    Returns:
        Parsed schema-matching JSON data, without granting execution authority.
        Unlike generation, the lab accepts the top-level types allowed by schema.

    Raises:
        StructuredOutputError: For invalid JSON, schema, constraints, or budgets.
    """
    value = parse_json_text(text, limits=limits)
    validate_against_schema(value, schema, limits=limits)
    return value
