"""Local UI-independent evaluation, using injected credential-free fixture output.

There is no live-provider construction or transport here. Application-owned local
executors can reuse accepted workflows/techniques; do not inject remote executors.
Unexpected programming defects propagate rather than becoming fixture failures.
"""

from typing import Literal, Protocol, Self

from pydantic import ConfigDict, Field, ValidationError, model_validator

from ..contracts import StrictContract, ValidationLimits
from ..errors import (
    EvaluationError,
    PromptConstructionError,
    ProviderError,
    SafetyError,
    SchemaDefinitionError,
    StructuredOutputError,
    TechniqueError,
)
from ..integrations.generation import ProviderOutput
from ..prompts.construction import ApplicationInstructions, ConstructedPrompt
from ..prompts.techniques import ConciseAnswer
from ..workflows import generate_structured
from .cases import CaseSuite, EvaluationCase, Identifier, validate_suite
from .evidence import EvaluationReport, fingerprint
from .metrics import CaseResult, LocalMode, Status, aggregate


class RunConfiguration(StrictContract):
    """Application-owned bounded reproducibility metadata, never fixture authority.

    executor_id/version identify the local implementation. Settings digest hashes
    actual executor configuration; the runner supplies it from the executor.
    """

    model_config = ConfigDict(frozen=True)
    executor_id: Identifier
    version: int = Field(ge=1, le=1000)
    mode: LocalMode
    max_cases: int = Field(default=32, ge=0, le=32)
    settings_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class LocalOutcome(StrictContract):
    """Transient bounded local execution evidence; answer never enters export."""

    model_config = ConfigDict(frozen=True)
    mode: LocalMode
    answer: str | None = Field(default=None, min_length=1, max_length=1024, repr=False)
    structured_valid: bool = False
    proposal_valid: bool | None = None
    detected: bool | None = None
    authorization: Literal["allowed", "denied"] | None = None
    tool_executions: int = Field(default=0, ge=0, le=16)

    @model_validator(mode="after")
    def consistent(self) -> Self:
        """Reject contradictory transient outcomes before scoring."""
        if self.structured_valid != (self.answer is not None):
            raise ValueError("Validated answers and structured validity must agree.")
        if self.authorization != "allowed" and self.tool_executions:
            raise ValueError("Only allowed actions can have executions.")
        return self


class LocalExecutor(Protocol):
    """Trusted local execution boundary; fixtures cannot select its implementation."""

    configuration: RunConfiguration

    def execute(self, case: EvaluationCase) -> LocalOutcome:
        """Execute one case using bounded accepted local workflows."""


class FixtureResponse(StrictContract):
    """Explicit untrusted raw fixture output for one case, at most 16 KiB chars."""

    model_config = ConfigDict(frozen=True)
    case_id: Identifier
    text: str = Field(max_length=16384, repr=False)


class _FixtureSettings(StrictContract):
    model_config = ConfigDict(frozen=True)
    application: ApplicationInstructions
    mode: LocalMode
    responses: tuple[FixtureResponse, ...] = Field(max_length=32)


class _FixtureProvider:
    """Single fixed offline/mocked output; no I/O or live client creation."""

    def __init__(self, output: ProviderOutput) -> None:
        self.output = output

    def generate(self, prompt: ConstructedPrompt) -> ProviderOutput:
        return self.output


class StructuredFixtureExecutor:
    """Run injected raw fixtures through the actual Story 3/5/2 workflow."""

    def __init__(
        self,
        application: ApplicationInstructions,
        responses: tuple[FixtureResponse, ...],
        *,
        mode: LocalMode = "offline",
    ) -> None:
        """Capture bounded response fixtures and validated trusted configuration.

        Args:
            application: Application-authored instructions, never case content.
            responses: Injected synthetic responses with unique case identifiers.
            mode: Actual local origin, offline or mocked; live is unsupported.

        Raises:
            EvaluationError: For invalid, duplicate or excessive fixture settings.
        """
        try:
            settings = _FixtureSettings(
                application=application, mode=mode, responses=responses
            )
            if len({item.case_id for item in settings.responses}) != len(
                settings.responses
            ):
                raise ValueError("Duplicate response fixtures.")
        except (ValidationError, ValueError):
            raise EvaluationError(
                "Correct bounded unique local fixture settings."
            ) from None
        self._settings = settings
        self.configuration = RunConfiguration(
            executor_id="structured-fixtures",
            version=1,
            mode=mode,
            settings_digest=fingerprint(settings),
        )

    def execute(self, case: EvaluationCase) -> LocalOutcome:
        """Validate one raw fixture response using the shared generation workflow.

        Args:
            case: Revalidated versioned evaluation case.

        Returns:
            Locally validated summary, with explicit offline/mocked origin.

        Raises:
            EvaluationError: For missing fixture responses (configuration defect).
            StructuredOutputError: For malformed raw output.
            PromptConstructionError: For prompt limit/construction failures.
        """
        response = next(
            (item for item in self._settings.responses if item.case_id == case.case_id),
            None,
        )
        if response is None:
            raise EvaluationError("Supply a response fixture for every evaluated case.")
        result = generate_structured(
            self._settings.application,
            case.specification(),
            _FixtureProvider(
                ProviderOutput(mode=self._settings.mode, text=response.text)
            ),
            ConciseAnswer,
            limits=ValidationLimits(max_text_bytes=16384, max_nodes=128, max_depth=8),
        )
        return LocalOutcome(
            mode=result.mode, answer=result.answer.answer, structured_valid=True
        )


def run_evaluation(suite: CaseSuite, executor: LocalExecutor) -> EvaluationReport:
    """Execute each case once in identifier order; retain expected domain failures.

    Args:
        suite: Bounded versioned cases with deterministic criteria.
        executor: Trusted injected local executor with actual configuration identity.

    Returns:
        Content-free inspectable evidence and deterministic aggregate metrics.

    Raises:
        EvaluationError: For invalid configuration/outcomes or exceeded case budget.
        SchemaDefinitionError: For programmer-owned schema defects.
        Exception: Unexpected execution defects propagate unchanged.
    """
    checked = validate_suite(suite)
    try:
        configuration = RunConfiguration.model_validate(executor.configuration)
    except ValidationError:
        raise EvaluationError("Correct local evaluation configuration.") from None
    if len(checked.cases) > configuration.max_cases:
        raise EvaluationError("Evaluation case budget exceeded; reduce suite.")
    results = []
    for case in sorted(checked.cases, key=lambda item: item.case_id):
        status: Status = "completed"
        outcome = None
        try:
            outcome = executor.execute(case)
        except SchemaDefinitionError:
            raise
        except StructuredOutputError:
            status = "validation_failure"
        except ProviderError:
            status = "provider_failure"
        except SafetyError:
            status = "safety_failure"
        except PromptConstructionError:
            status = "prompt_failure"
        except TechniqueError:
            status = "technique_failure"
        # Validate outside the execution catch: malformed executor results are defects.
        try:
            if outcome is not None:
                outcome = LocalOutcome.model_validate(outcome)
                if outcome.mode != configuration.mode:
                    raise ValueError("Origin mismatch.")
            elif status == "completed":
                raise ValueError("Executor returned no outcome.")
            valid = outcome.structured_valid if outcome else False
            results.append(
                CaseResult(
                    case_id=case.case_id,
                    version=case.version,
                    provenance=case.provenance,
                    category=case.category,
                    case_digest=fingerprint(case),
                    mode=configuration.mode,
                    status=status,
                    structured_valid=valid,
                    correct=None
                    if case.expected_answer is None
                    else bool(
                        outcome and valid and outcome.answer == case.expected_answer
                    ),
                    safety_met=None
                    if case.expected_authorization is None
                    else bool(
                        outcome and outcome.authorization == case.expected_authorization
                    ),
                    detected=outcome.detected if outcome else None,
                    proposal_valid=outcome.proposal_valid if outcome else None,
                    authorization=outcome.authorization if outcome else None,
                    tool_executions=outcome.tool_executions if outcome else None,
                )
            )
        except ValidationError:
            raise EvaluationError(
                "Correct consistent typed local executor outcomes."
            ) from None
        except ValueError:
            raise EvaluationError(
                "Correct local executor origin and completion state."
            ) from None
    ordered = tuple(results)
    return EvaluationReport(
        configuration_digest=fingerprint(configuration),
        results=ordered,
        metrics=aggregate(ordered),
    )
