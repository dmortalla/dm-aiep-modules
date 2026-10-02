"""Executable bounded instructional techniques, never hidden model reasoning.

Provider proposals always traverse Story 5 and Story 2 validation. Generated
continuations/observations enter user content, never application policy. Scoring
and agreement are deterministic demonstration measures, not calibrated confidence.
"""

import json
from dataclasses import dataclass
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, ValidationError, model_validator

from ..contracts import StrictContract, ValidationLimits
from ..errors import StructuredOutputError, TechniqueError
from ..integrations.generation import EvidenceMode, GenerationProvider
from ..safety.tools import ToolResult, ToolSession
from ..structured.schemas import schema_for_model
from ..workflows import generate_structured
from .construction import ApplicationInstructions, PromptSpecification

type ShortText = Annotated[str, Field(min_length=1, max_length=1_024)]


class TechniqueLimits(StrictContract):
    """Bounded sequential session configuration; no wall-clock guarantees.

    Attributes:
        calls: Total provider attempts across this session, 1..64; default 32.
        steps: Decomposition/ReAct steps, 1..8; default four.
        branches: Candidates per retained tree parent, 1..4; default two.
        depth: Tree levels, 1..4; default two.
        keep: Retained tree paths per level, 1..4; default one.
        samples: Self-consistency attempts, 1..8; default three.
        minimum_valid: Required valid samples, 1..8; default two.

    Raises:
        ValidationError: For invalid direct construction; session errors are safe.
    """

    model_config = ConfigDict(frozen=True)
    calls: int = Field(default=32, ge=1, le=64)
    steps: int = Field(default=4, ge=1, le=8)
    branches: int = Field(default=2, ge=1, le=4)
    depth: int = Field(default=2, ge=1, le=4)
    keep: int = Field(default=1, ge=1, le=4)
    samples: int = Field(default=3, ge=1, le=8)
    minimum_valid: int = Field(default=2, ge=1, le=8)

    @model_validator(mode="after")
    def feasible_samples(self) -> Self:
        """Validate sample feasibility.

        Returns:
            This bounded configuration.

        Raises:
            ValueError: If the valid-sample requirement exceeds attempts.
        """
        if self.minimum_valid > self.samples:
            raise ValueError("Minimum valid samples cannot exceed attempts.")
        return self


class ConciseAnswer(StrictContract):
    """Observable solution summary, not private chain-of-thought.

    Attributes:
        answer: Nonblank summary, at most 1,024 characters.

    Raises:
        ValidationError: For invalid direct construction.
    """

    answer: ShortText

    @model_validator(mode="after")
    def nonblank(self) -> Self:
        """Reject blank summaries.

        Returns:
            Validated summary.

        Raises:
            ValueError: If summary contains only whitespace.
        """
        if not self.answer.strip():
            raise ValueError("Summary must be nonblank.")
        return self


class DecompositionPlan(StrictContract):
    """Explicit requested subproblems, not hidden reasoning.

    Attributes:
        steps: One to eight nonempty subproblem descriptions of at most 1,024 chars.
    """

    steps: list[ShortText] = Field(min_length=1, max_length=8)


class ReActStep(StrictContract):
    """Validated proposal whose shape never grants tool permission.

    Attributes:
        kind: Action or completion marker.
        tool: Proposed identifier for an action; bounded to 128 characters.
        arguments: At most two integer/text values used by existing local tools;
            independently checked by ToolSession for exact names/types/bounds.
        answer: Completion summary, at most 1,024 characters.

    Raises:
        ValidationError: For invalid fields or inconsistent action/completion shape.
    """

    kind: Literal["action", "complete"]
    tool: str | None = Field(default=None, min_length=1, max_length=128)
    arguments: dict[str, int | str] = Field(default_factory=dict, max_length=2)
    answer: str | None = Field(default=None, min_length=1, max_length=1_024)

    @model_validator(mode="after")
    def consistent_step(self) -> Self:
        """Reject ambiguous or forged step shapes.

        Returns:
            This validated proposal without authorization.

        Raises:
            ValueError: For action/completion field conflicts or blank completion.
        """
        if self.kind == "action":
            if self.tool is None or self.answer is not None:
                raise ValueError("Action requires a tool and no completion answer.")
        elif self.tool is not None or self.arguments or not (self.answer or "").strip():
            raise ValueError("Completion requires only a nonblank answer.")
        return self


@dataclass(frozen=True)
class TechniqueResult:
    """Inspectable executed artifacts with explicit origin and termination.

    Attributes:
        technique: Executed technique identifier.
        answer: Selected/synthesized concise solution.
        paths: Decomposition steps or ranked surviving tree paths.
        scores: Word-overlap scores aligned with surviving tree paths.
        summaries: Validated summaries/samples, in attempt order.
        votes: Normalized answer/count pairs ordered by first valid appearance.
        agreement: Vote share among valid samples; never calibrated confidence.
        rejected: Number of invalid candidates/samples rejected without repair.
        observations: Authorized numerical local-tool observations in execution order.
        modes: Evidence origin for each successfully validated provider response.
        calls: Attempts charged to this execution, including invalid output.
    """

    technique: str
    answer: str
    paths: tuple[tuple[str, ...], ...] = ()
    scores: tuple[int, ...] = ()
    summaries: tuple[str, ...] = ()
    votes: tuple[tuple[str, int], ...] = ()
    agreement: float | None = None
    rejected: int = 0
    observations: tuple[ToolResult, ...] = ()
    modes: tuple[EvidenceMode, ...] = ()
    calls: int = 0


class TechniqueSession:
    """Trusted sequential orchestration with a cumulative provider-attempt budget.

    Use application-owned providers/configuration/session lifetimes. Creating a
    new session is trusted application code's decision, not model output authority.
    Methods return observable artifacts and never request private hidden reasoning.

    Attributes:
        used_calls: Read-only number of provider attempts across technique methods.
    """

    def __init__(
        self,
        application: ApplicationInstructions,
        specification: PromptSpecification,
        provider: GenerationProvider,
        limits: TechniqueLimits | None = None,
    ) -> None:
        """Capture validated bounded application configuration.

        Args:
            application: Trusted instructions, independent of provider content.
            specification: Lower-trust request, context, examples and role selection.
            provider: Existing Story 5 provider contract, chosen by application code.
            limits: Optional bounded technique session settings.

        Raises:
            TechniqueError: For invalid configuration or request fields.
        """
        try:
            self._application = ApplicationInstructions.model_validate(application)
            self._specification = PromptSpecification.model_validate(specification)
            self._limits = TechniqueLimits.model_validate(limits or TechniqueLimits())
        except ValidationError:
            raise TechniqueError(
                "Correct strict technique inputs and bounded limits."
            ) from None
        self._provider = provider
        self._calls = 0
        self._modes: list[EvidenceMode] = []

    @property
    def used_calls(self) -> int:
        """Return charged provider attempts.

        Returns:
            Attempts, including rejected model responses.
        """
        return self._calls

    def _ask[Contract: StrictContract](
        self,
        contract: type[Contract],
        instruction: str,
        continuation: str = "",
    ) -> Contract:
        """Route one bounded proposal through the existing prompt/validation stack."""
        if self._calls >= self._limits.calls:
            raise TechniqueError(
                "Technique provider-call budget exhausted; stop session."
            )
        schema_text = json.dumps(schema_for_model(contract))
        application = self._application.model_copy(
            update={
                "output_contract": (
                    self._application.output_contract
                    + f"\nInstructional stage: {instruction}"
                    + f"\nReturn JSON matching: {schema_text}"
                )
            }
        )
        specification = self._specification.model_copy(
            update={
                "user_request": self._specification.user_request
                + "\nContent continuation:\n"
                + continuation
            }
        )
        self._calls += 1
        result = generate_structured(
            application,
            specification,
            self._provider,
            contract,
            limits=ValidationLimits(max_text_bytes=16_384, max_nodes=128, max_depth=8),
        )
        self._modes.append(result.mode)
        return result.answer

    def decompose(self) -> TechniqueResult:
        """Request subproblems, solve each, then synthesize concise summaries.

        Returns:
            Explicit plan, subproblem summaries and final synthesis.

        Raises:
            TechniqueError: For step/call exhaustion or blank subproblems.
            StructuredOutputError: For any invalid proposal; no plan is repaired.
        """
        start, mode_start = self._calls, len(self._modes)
        plan = self._ask(DecompositionPlan, "List explicit bounded subproblems.")
        if len(plan.steps) > self._limits.steps or any(
            not step.strip() for step in plan.steps
        ):
            raise TechniqueError(
                "Decomposition step budget/validity exceeded; reduce plan."
            )
        summaries = tuple(
            self._ask(ConciseAnswer, "Summarize this subproblem.", step).answer
            for step in plan.steps
        )
        answer = self._ask(
            ConciseAnswer,
            "Synthesize concise solution summaries.",
            json.dumps(summaries),
        ).answer
        return TechniqueResult(
            "decomposition",
            answer,
            paths=(tuple(plan.steps),),
            summaries=summaries,
            modes=tuple(self._modes[mode_start:]),
            calls=self._calls - start,
        )

    def tree(self) -> TechniqueResult:
        """Expand, validate and prune candidate paths at every bounded depth.

        Scoring is total distinct case-folded word overlap with the original
        request. Higher scores survive; ties retain generation order. Duplicate
        valid paths remain candidates. No hidden reasoning or semantic confidence
        is inferred. Invalid candidates are counted and omitted, never repaired.

        Returns:
            Ranked surviving paths and the selected path's terminal summary.

        Raises:
            TechniqueError: For call exhaustion or a level with no valid branches.
        """
        start, mode_start = self._calls, len(self._modes)
        paths: list[tuple[str, ...]] = [()]
        rejected = 0
        words = set(self._specification.user_request.casefold().split())
        for _ in range(self._limits.depth):
            expanded = []
            for path in paths:
                for branch in range(self._limits.branches):
                    try:
                        candidate = self._ask(
                            ConciseAnswer,
                            f"Propose candidate continuation {branch + 1}.",
                            json.dumps(path),
                        )
                    except StructuredOutputError:
                        rejected += 1
                        continue
                    expanded.append((*path, candidate.answer))
            if not expanded:
                raise TechniqueError(
                    "Candidate tree exhausted; no valid branches at this level."
                )
            paths = sorted(
                expanded,
                key=lambda path: (
                    -len(words.intersection(" ".join(path).casefold().split()))
                ),
            )[: self._limits.keep]
        return TechniqueResult(
            "tree",
            paths[0][-1],
            paths=tuple(paths),
            scores=tuple(
                len(words.intersection(" ".join(path).casefold().split()))
                for path in paths
            ),
            rejected=rejected,
            modes=tuple(self._modes[mode_start:]),
            calls=self._calls - start,
        )

    def self_consistency(self) -> TechniqueResult:
        """Normalize validated samples and vote; first valid appearance breaks ties.

        Returns:
            Selected normalized answer, accepted samples, counts and vote share.

        Raises:
            TechniqueError: For call exhaustion or insufficient valid samples.
        """
        start, mode_start = self._calls, len(self._modes)
        counts: dict[str, int] = {}
        samples = []
        rejected = 0
        for index in range(self._limits.samples):
            try:
                sample = self._ask(
                    ConciseAnswer, f"Give concise solution sample {index + 1}."
                )
            except StructuredOutputError:
                rejected += 1
                continue
            normalized = " ".join(sample.answer.split()).casefold()
            samples.append(sample.answer)
            counts[normalized] = counts.get(normalized, 0) + 1
        if len(samples) < self._limits.minimum_valid:
            raise TechniqueError(
                "Insufficient valid samples; revise task or sample allowance."
            )
        selected = max(counts, key=counts.get)
        return TechniqueResult(
            "self_consistency",
            selected,
            summaries=tuple(samples),
            votes=tuple(counts.items()),
            agreement=counts[selected] / len(samples),
            rejected=rejected,
            modes=tuple(self._modes[mode_start:]),
            calls=self._calls - start,
        )

    def react(self, tools: ToolSession) -> TechniqueResult:
        """Iterate validated proposals and authorized observations until completion.

        Args:
            tools: Existing application-owned Story 4 session; never created or
                reset from model proposals. Tool authorization remains independent.

        Returns:
            Completion with numerical observations and charged attempt count.

        Raises:
            TechniqueError: For step/call exhaustion.
            StructuredOutputError: For invalid proposals.
            SafetyError: For unauthorized/invalid actions or tool-budget exhaustion.
        """
        start, mode_start = self._calls, len(self._modes)
        observations = []
        for _ in range(self._limits.steps):
            continuation = json.dumps([item.model_dump() for item in observations])
            step = self._ask(
                ReActStep, "Propose a local action or concise completion.", continuation
            )
            if step.kind == "complete":
                return TechniqueResult(
                    "react",
                    step.answer or "",
                    observations=tuple(observations),
                    modes=tuple(self._modes[mode_start:]),
                    calls=self._calls - start,
                )
            observations.append(
                tools.execute({"tool": step.tool, "arguments": step.arguments})
            )
        raise TechniqueError(
            "ReAct step budget exhausted before completion; stop session."
        )
