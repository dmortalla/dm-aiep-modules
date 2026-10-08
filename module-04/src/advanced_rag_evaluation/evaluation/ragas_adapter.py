"""Genuine RAGAS evaluation with explicit models and retained source evidence.

This module loads the integration lazily. ReplayJudge supplies fixed model
responses, not metric scores; RAGAS owns all three metric computations.
Non-replay models require explicit opt-in. Evaluation data never selects models,
credentials, configuration, destinations, or executable behavior.
"""

import math
from dataclasses import dataclass, field
from typing import Literal, Protocol

from ..context_filtering import FilteredContext
from ..corpus import CorpusChunk
from ..errors import (
    EvaluationInputError,
    EvaluationIntegrationError,
    EvaluationResultError,
)
from ..semantic_retrieval import Embedder, HashEmbedder

type EvidenceKind = Literal["deterministic_offline", "provider_backed"]
METRIC_NAMES = ("faithfulness", "context_precision", "response_relevancy")
MAX_TEXT_BYTES = 32_768


def _score(value: float, name: str) -> None:
    """Validate the metric's actual domain without clipping numerical evidence."""
    minimum = -1 if name == "response_relevancy" else 0
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not minimum - 1e-12 <= value <= 1 + 1e-12
    ):
        raise EvaluationResultError(f"Require a finite valid {name} score.")


def _text(value: str, label: str, limit: int = MAX_TEXT_BYTES) -> None:
    """Validate bounded Unicode without rewriting or rendering untrusted text."""
    if type(value) is not str or not value.strip():
        raise EvaluationInputError(f"Supply a nonblank {label} string.")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise EvaluationInputError(f"Supply valid Unicode for {label}.") from exc
    if size > limit:
        raise EvaluationInputError(f"Limit {label} to {limit} UTF-8 bytes.")


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    """One ordered evaluation case, retaining original chunks by reference.

    Args:
        case_id: Application identifier, at most 256 UTF-8 bytes.
        question: User question, at most 32768 UTF-8 bytes.
        response: Generated answer, with the same bound; untrusted data.
        reference: Explicit reference answer for context precision.
        contexts: Ordered tuple of 1..64 unique Module 4 CorpusChunk objects.
        filtered_context: Optional original Story 5 evidence; its retained
            chunks must be the identical objects in the identical order.

    Raises:
        EvaluationInputError: For invalid or inconsistent evaluation data.
    """

    case_id: str
    question: str = field(repr=False)
    response: str = field(repr=False)
    reference: str = field(repr=False)
    contexts: tuple[CorpusChunk, ...] = field(repr=False)
    filtered_context: FilteredContext | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Validate text, chunk identity, ordering, and upstream evidence."""
        _text(self.case_id, "case_id", 256)
        for label in ("question", "response", "reference"):
            _text(getattr(self, label), label)
        if (
            type(self.contexts) is not tuple
            or not 1 <= len(self.contexts) <= 64
            or any(type(chunk) is not CorpusChunk for chunk in self.contexts)
        ):
            raise EvaluationInputError("Supply 1..64 validated context chunks.")
        for chunk in self.contexts:
            _text(chunk.content, "context content")
        if sum(len(c.content.encode("utf-8")) for c in self.contexts) > 524_288:
            raise EvaluationInputError("Limit combined contexts to 524288 UTF-8 bytes.")
        if len({c.chunk_id for c in self.contexts}) != len(self.contexts):
            raise EvaluationInputError("Keep evaluated chunk identifiers unique.")
        if self.filtered_context is not None:
            if type(self.filtered_context) is not FilteredContext:
                raise EvaluationInputError("Supply validated Story 5 context evidence.")
            original = tuple(item.chunk for item in self.filtered_context.items)
            if len(original) != len(self.contexts) or any(
                a is not b for a, b in zip(original, self.contexts, strict=True)
            ):
                raise EvaluationInputError("Preserve the filtered chunks and order.")


@dataclass(frozen=True, slots=True)
class EvaluationConfig:
    """Application-owned bounded metric execution settings.

    Args:
        strictness: RAGAS relevance question count, integer 1..5; default 3.
        timeout_seconds: Per-metric timeout, finite number 1..300; default 30.

    Raises:
        EvaluationInputError: For malformed settings, including bool values.
    """

    strictness: int = 3
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        """Validate settings before any model is invoked."""
        if type(self.strictness) is not int or not 1 <= self.strictness <= 5:
            raise EvaluationInputError("Use integer relevance strictness from 1 to 5.")
        if (
            type(self.timeout_seconds) not in (int, float)
            or not math.isfinite(self.timeout_seconds)
            or not 1 <= self.timeout_seconds <= 300
        ):
            raise EvaluationInputError("Use a finite metric timeout from 1 to 300.")


@dataclass(frozen=True, slots=True)
class EvaluationScores:
    """Unmodified RAGAS scores, with finite-domain validation.

    Relevance is cosine-based and can be negative. Its true domain is [-1, 1],
    unlike faithfulness/context precision [0, 1]. A 1e-12 numerical tolerance
    permits floating-point roundoff; scores are never clipped or rewritten.

    Args:
        faithfulness: Supported-statement proportion computed by RAGAS.
        context_precision: Reference-based average precision computed by RAGAS.
        response_relevancy: RAGAS mean generated-question cosine similarity,
            multiplied by its committal-answer indicator.

    Raises:
        EvaluationResultError: For nonfinite, wrong-type, or out-of-domain scores.
    """

    faithfulness: float
    context_precision: float
    response_relevancy: float

    def __post_init__(self) -> None:
        """Reject unusable scores without inventing defaults."""
        for name in METRIC_NAMES:
            _score(getattr(self, name), name)


_DEFAULT_CONFIG = EvaluationConfig()


class Judge(Protocol):
    """Application-selected asynchronous model boundary; prompt text is only data."""

    async def complete(self, prompt: str) -> str:
        """Return JSON model output for a RAGAS-generated prompt.

        Args:
            prompt: Untrusted evaluation text inside RAGAS's fixed prompt schema.

        Returns:
            A JSON string following that prompt's requested output schema.

        Raises:
            Exception: For a model/provider failure; wrapped by the adapter.
        """
        ...


@dataclass(frozen=True, slots=True)
class ReplayReply:
    """One exact prompt/JSON response fixture; both are inert, repr-hidden data.

    Args:
        prompt: Exact expected RAGAS prompt, at most 1048576 UTF-8 bytes.
        completion: Fixed JSON completion, at most 131072 UTF-8 bytes.

    Raises:
        EvaluationInputError: For blank or oversized fixture text.
    """

    prompt: str = field(repr=False)
    completion: str = field(repr=False)

    def __post_init__(self) -> None:
        """Validate fixture budgets without interpreting its response."""
        _text(self.prompt, "replay prompt", 1_048_576)
        _text(self.completion, "replay completion", 131_072)


@dataclass(frozen=True, slots=True)
class ReplayJudge:
    """Stateless exact-match deterministic judge double; computes no metrics.

    Args:
        replies: Nonempty tuple of unique exact prompt/response fixtures.

    Raises:
        EvaluationInputError: For invalid or duplicate fixtures.
    """

    replies: tuple[ReplayReply, ...] = field(repr=False)

    def __post_init__(self) -> None:
        """Reject ambiguous fixtures before genuine RAGAS execution."""
        if (
            type(self.replies) is not tuple
            or not 1 <= len(self.replies) <= 256
            or any(type(reply) is not ReplayReply for reply in self.replies)
            or len({reply.prompt for reply in self.replies}) != len(self.replies)
        ):
            raise EvaluationInputError("Supply 1..256 unique validated replay replies.")

    async def complete(self, prompt: str) -> str:
        """Return only a configured response for an exact expected prompt.

        Args:
            prompt: Prompt produced by the genuine RAGAS integration.

        Returns:
            The exact fixed JSON completion.

        Raises:
            EvaluationResultError: For a prompt absent from the replay plan.
        """
        for reply in self.replies:
            if prompt == reply.prompt:
                return reply.completion
        raise EvaluationResultError("Provide a replay fixture for this RAGAS prompt.")


@dataclass(frozen=True, slots=True)
class JudgeCall:
    """Retained raw model evidence; it never grants application authority.

    Args:
        metric: Fixed adapter metric name.
        prompt: Exact RAGAS prompt, hidden from default representations.
        completion: Schema-validated JSON completion, also repr-hidden.

    Raises:
        EvaluationResultError: For an unknown metric name.
    """

    metric: str
    prompt: str = field(repr=False)
    completion: str = field(repr=False)

    def __post_init__(self) -> None:
        """Keep the evidence category within the fixed metric vocabulary."""
        if self.metric not in METRIC_NAMES:
            raise EvaluationResultError("Use a supported evaluation metric name.")
        _text(self.prompt, "judge prompt", 1_048_576)
        _text(self.completion, "judge completion", 131_072)


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """All-or-error scores with case, configuration, and model evidence retained.

    Evidence classification identifies the selected model boundary. It is not
    independent proof that an injected provider contacted a remote service.

    Args:
        case: Exact original case and chunk/provenance objects.
        scores: Validated genuine RAGAS scores.
        config: Exact execution configuration.
        evidence_kind: Deterministic replay or explicitly opted-in provider path.
        judge_id: Application-selected model identifier.
        embedding_id: Application-selected embedding identifier.
        ragas_version: Actual installed RAGAS version.
        judge_calls: Ordered, immutable raw evaluation evidence.

    Raises:
        EvaluationResultError: For malformed or missing result evidence.
    """

    case: EvaluationCase = field(repr=False)
    scores: EvaluationScores
    config: EvaluationConfig
    evidence_kind: EvidenceKind
    judge_id: str
    embedding_id: str
    ragas_version: str
    judge_calls: tuple[JudgeCall, ...] = field(repr=False)

    def __post_init__(self) -> None:
        """Require truthful fixed labels and complete metric evidence."""
        if (
            type(self.case) is not EvaluationCase
            or type(self.scores) is not EvaluationScores
            or type(self.config) is not EvaluationConfig
            or self.evidence_kind not in ("deterministic_offline", "provider_backed")
            or type(self.judge_calls) is not tuple
            or any(type(call) is not JudgeCall for call in self.judge_calls)
            or {call.metric for call in self.judge_calls} != set(METRIC_NAMES)
        ):
            raise EvaluationResultError("Retain validated case, scores, and evidence.")
        for name in ("judge_id", "embedding_id", "ragas_version"):
            _text(getattr(self, name), name, 256)
        if self.evidence_kind == "deterministic_offline" and (
            self.judge_id != "exact-prompt-replay-v1"
            or not self.embedding_id.startswith("module-4-local-hash:")
        ):
            raise EvaluationResultError("Keep deterministic model evidence explicit.")


@dataclass(frozen=True, slots=True)
class RagasEvaluator:
    """Configured genuine integration; no model/provider is selected from content.

    Args:
        judge: Injected asynchronous Judge, selected by application code.
        embedder: Module 4 Embedder boundary, selected by application code.
        judge_id: Explicit model identifier; fixed for the replay path.
        embedding_id: Explicit embedding identifier; fixed for HashEmbedder.
        allow_provider_backed: Explicit opt-in required unless both models are
            exactly ReplayJudge and HashEmbedder. Defaults to False.

    Raises:
        EvaluationInputError: For invalid models, identifiers, or absent opt-in.
    """

    judge: Judge = field(repr=False)
    embedder: Embedder = field(repr=False)
    judge_id: str = "exact-prompt-replay-v1"
    embedding_id: str = "module-4-local-hash:64"
    allow_provider_backed: bool = False

    def __post_init__(self) -> None:
        """Enforce explicit model selection and offline-versus-provider authority."""
        if (
            not callable(getattr(self.judge, "complete", None))
            or not callable(getattr(self.embedder, "embed", None))
            or type(self.allow_provider_backed) is not bool
        ):
            raise EvaluationInputError("Supply configured judge and embedding models.")
        _text(self.judge_id, "judge_id", 256)
        _text(self.embedding_id, "embedding_id", 256)
        if type(self.judge) is ReplayJudge:
            if self.judge_id != "exact-prompt-replay-v1":
                raise EvaluationInputError("Identify the actual deterministic judge.")
        elif self.judge_id == "exact-prompt-replay-v1":
            raise EvaluationInputError("Identify the configured provider-path judge.")
        if type(self.embedder) is HashEmbedder:
            if self.embedding_id != self.embedder.embedding_id:
                raise EvaluationInputError("Identify the actual local embedding model.")
        elif self.embedding_id.startswith("module-4-local-hash:"):
            raise EvaluationInputError("Identify the configured embedding model.")
        if (
            self.evidence_kind != "deterministic_offline"
            and not self.allow_provider_backed
        ):
            raise EvaluationInputError("Explicitly opt in to provider-backed models.")

    @property
    def evidence_kind(self) -> EvidenceKind:
        """Classify the actual selected model types, never the evaluation text."""
        if type(self.judge) is ReplayJudge and type(self.embedder) is HashEmbedder:
            return "deterministic_offline"
        return "provider_backed"

    async def evaluate(
        self, case: EvaluationCase, config: EvaluationConfig = _DEFAULT_CONFIG
    ) -> EvaluationResult:
        """Run all three real RAGAS metrics and reject partial/invalid outcomes.

        Args:
            case: Validated question/answer/reference and ordered chunk evidence.
            config: Validated application-owned metric settings.

        Returns:
            Genuine scores and their original provenance/model evidence.

        Raises:
            EvaluationInputError: For invalid input or configuration.
            EvaluationIntegrationError: For dependency, provider, or timeout failures.
            EvaluationResultError: For malformed model responses or metric output.
        """
        if type(case) is not EvaluationCase or type(config) is not EvaluationConfig:
            raise EvaluationInputError("Supply validated evaluation case and config.")
        try:
            from ._ragas_runtime import score_case
        except ImportError as exc:
            raise EvaluationIntegrationError(
                "Synchronize the pinned RAGAS integration dependencies."
            ) from exc
        return await score_case(self, case, config)


def build_replay_judge(
    case: EvaluationCase,
    *,
    statements: tuple[str, ...],
    statement_verdicts: tuple[int, ...],
    context_verdicts: tuple[int, ...],
    generated_question: str,
    noncommittal: int = 0,
) -> ReplayJudge:
    """Build exact RAGAS prompt fixtures from explicit, fixed judge answers.

    No metric computation or automatic semantic judgment occurs here.

    Args:
        case: Exact evaluation case to replay.
        statements: Explicit decomposition of its response.
        statement_verdicts: One fixed binary support verdict per statement.
        context_verdicts: One fixed binary usefulness verdict per ordered context.
        generated_question: Fixed relevance question derived from the response.
        noncommittal: Fixed binary indicator for an evasive answer.

    Returns:
        Stateless deterministic ReplayJudge for this exact case.

    Raises:
        EvaluationInputError: For inconsistent fixture counts or nonbinary verdicts.
        EvaluationIntegrationError: If the pinned RAGAS runtime cannot load.
    """
    if (
        type(case) is not EvaluationCase
        or type(statements) is not tuple
        or type(statement_verdicts) is not tuple
        or type(context_verdicts) is not tuple
        or len(statements) != len(statement_verdicts)
        or len(context_verdicts) != len(case.contexts)
        or any(
            type(v) is not int or v not in (0, 1)
            for v in (*statement_verdicts, *context_verdicts, noncommittal)
        )
    ):
        raise EvaluationInputError("Supply aligned fixed binary replay judgments.")
    for statement in statements:
        _text(statement, "replay statement")
    _text(generated_question, "generated question")
    try:
        from ._ragas_runtime import replay_replies
    except ImportError as exc:
        raise EvaluationIntegrationError(
            "Synchronize RAGAS replay dependencies."
        ) from exc
    return ReplayJudge(
        replay_replies(
            case,
            statements,
            statement_verdicts,
            context_verdicts,
            generated_question,
            noncommittal,
        )
    )
