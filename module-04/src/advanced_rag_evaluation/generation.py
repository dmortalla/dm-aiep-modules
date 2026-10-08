"""Module 4-owned grounded answer generation over ``FilteredContext`` (Story 10).

Generation consumes Story 5's ``context_filtering.FilteredContext`` directly:
the retained ``ContextFilterItem`` objects are the only passages a generator
sees and the only passages an answer may cite. No earlier-module contract is
constructed or imported (Rule 44), and no intermediate context type is
fabricated, so every citation resolves by identity to the retained item and,
through it, to the complete Story 2-5 evidence chain (lexical/semantic leg
rank and score, RRF score, rerank rank and score, filter order, and chunk
provenance).

The Module 4 source names no generation model or provider, so this story adds
no provider adapter. ``AnswerGenerator`` is the integration boundary, and
``ExtractiveAnswerGenerator`` is its deterministic, offline, credential-free
implementation: it quotes the most query-relevant sentence of each leading
retained passage with a numbered citation marker. It is not a language model
and makes no claim of abstractive answer quality.

Retrieved content and generator output are untrusted data. Passage text is
quoted as inert text, never executed or interpreted as instructions; generator
output is bounded and validated before it is accepted, can only cite passages
that were actually retained, and never selects configuration, models,
credentials, or control flow. Generator failures become ``GenerationError``
with fixed messages and no chained cause, so generator payloads or
credentials cannot leak through error text or tracebacks.
"""

import re
from dataclasses import dataclass, field
from typing import Literal, Protocol

from .bm25 import tokenize
from .context_filtering import ContextFilterItem, FilteredContext
from .errors import GenerationError
from .telemetry.cost import TokenUsage

type GenerationEvidenceKind = Literal["deterministic_offline", "injected"]
MAX_QUERY_BYTES = 32_768
MAX_ANSWER_BYTES = 32_768
MAX_CONTEXT_ITEMS = 64
MAX_CONTEXT_BYTES = 524_288
MAX_ID_BYTES = 256
EXTRACTIVE_GENERATOR_ID = "module-4-extractive:v1"
ABSTENTION_TEXT = "No retained context supports an answer to this query."
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def _bounded_text(value: str, label: str, limit: int) -> None:
    """Validate a nonblank, valid-Unicode string within a UTF-8 byte budget."""
    if type(value) is not str or not value.strip():
        raise GenerationError(f"Supply a nonblank {label} string.")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError:
        raise GenerationError(f"Supply valid Unicode {label}.") from None
    if size > limit:
        raise GenerationError(f"Limit {label} to {limit} UTF-8 bytes.")


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """One bounded generation request over Story 5 filtered context.

    Args:
        query: Nonblank user query, at most 32768 UTF-8 bytes; hidden from repr.
        context: The validated Story 5 FilteredContext, consumed directly and
            retained by identity; at most 64 retained items whose combined
            content is at most 524288 UTF-8 bytes. Zero retained items is a
            valid request that ``generate_answer`` answers by abstaining.

    Raises:
        GenerationError: For a malformed query or context outside the bounds.
    """

    query: str = field(repr=False)
    context: FilteredContext = field(repr=False)

    def __post_init__(self) -> None:
        """Validate query and context bounds before any generator is called."""
        _bounded_text(self.query, "query", MAX_QUERY_BYTES)
        if type(self.context) is not FilteredContext:
            raise GenerationError("Supply a validated Story 5 FilteredContext.")
        if len(self.context.items) > MAX_CONTEXT_ITEMS:
            raise GenerationError(
                f"Limit generation context to {MAX_CONTEXT_ITEMS} retained items."
            )
        size = sum(len(i.chunk.content.encode("utf-8")) for i in self.context.items)
        if size > MAX_CONTEXT_BYTES:
            raise GenerationError(
                f"Limit combined generation context to {MAX_CONTEXT_BYTES} bytes."
            )

    @property
    def passages(self) -> tuple[ContextFilterItem, ...]:
        """Return the retained Story 5 items, in filter order, by identity."""
        return self.context.items


@dataclass(frozen=True, slots=True)
class GeneratorOutput:
    """Untrusted generator output, shape-validated on construction.

    Args:
        text: Nonblank answer text, at most 32768 UTF-8 bytes; hidden from repr.
        cited_chunk_ids: Ordered tuple of 1..64 unique chunk identifiers the
            answer relies on; marker ``[n]`` in ``text`` refers to the n-th
            identifier. Membership in the retained context is checked by
            ``generate_answer``, not here.
        usage: Genuine provider-reported TokenUsage, or None when the
            generator has no provider usage to report.

    Raises:
        GenerationError: For malformed text, citations, or usage.
    """

    text: str = field(repr=False)
    cited_chunk_ids: tuple[str, ...]
    usage: TokenUsage | None = None

    def __post_init__(self) -> None:
        """Validate bounded text, citation identifiers, and usage type."""
        _bounded_text(self.text, "answer text", MAX_ANSWER_BYTES)
        if (
            type(self.cited_chunk_ids) is not tuple
            or not 1 <= len(self.cited_chunk_ids) <= MAX_CONTEXT_ITEMS
        ):
            raise GenerationError(
                f"Cite 1..{MAX_CONTEXT_ITEMS} retained chunk identifiers."
            )
        for chunk_id in self.cited_chunk_ids:
            _bounded_text(chunk_id, "cited chunk_id", MAX_ID_BYTES)
        if len(set(self.cited_chunk_ids)) != len(self.cited_chunk_ids):
            raise GenerationError("Deduplicate cited chunk identifiers.")
        if self.usage is not None and type(self.usage) is not TokenUsage:
            raise GenerationError("Report usage as a validated TokenUsage or None.")


class AnswerGenerator(Protocol):
    """Provider-neutral generation boundary over a GenerationRequest."""

    @property
    def generator_id(self) -> str:
        """Return the application-selected generator identifier."""
        ...

    def generate(self, request: GenerationRequest) -> GeneratorOutput:
        """Return untrusted output for one validated, nonempty request.

        Args:
            request: Validated request with at least one retained passage.

        Returns:
            GeneratorOutput citing only retained chunk identifiers.

        Raises:
            Exception: Implementation-specific failures, translated to a
                sanitized GenerationError by ``generate_answer``.
        """
        ...


@dataclass(frozen=True, slots=True)
class ExtractiveAnswerGenerator:
    """Deterministic, offline, credential-free extractive generator.

    For each of the first ``max_passages`` retained items, in Story 5 filter
    order, it selects the sentence sharing the most query terms (Story 2
    tokenizer; ties go to the earliest sentence), truncates it to
    ``max_sentence_chars`` characters, and appends citation marker ``[n]``.
    Every quoted sentence is inert retrieved text. This is not a language
    model; it exists so the end-to-end workflow is reproducible offline.

    Args:
        max_passages: Retained passages to quote, 1..8; default 3.
        max_sentence_chars: Character cap per quoted sentence, 1..1000;
            default 400. Together these keep output under 32768 UTF-8 bytes.

    Raises:
        GenerationError: For out-of-range settings.
    """

    max_passages: int = 3
    max_sentence_chars: int = 400

    def __post_init__(self) -> None:
        """Validate bounded extraction settings."""
        if type(self.max_passages) is not int or not 1 <= self.max_passages <= 8:
            raise GenerationError("Use an integer max_passages from 1 to 8.")
        if (
            type(self.max_sentence_chars) is not int
            or not 1 <= self.max_sentence_chars <= 1_000
        ):
            raise GenerationError("Use an integer max_sentence_chars from 1 to 1000.")

    @property
    def generator_id(self) -> str:
        """Return the fixed, versioned identifier of this extractive method."""
        return EXTRACTIVE_GENERATOR_ID

    def _best_sentence(self, content: str, query_terms: frozenset[str]) -> str:
        """Return the bounded sentence with the greatest query-term overlap."""
        sentences = [s.strip() for s in _SENTENCE_BOUNDARY.split(content) if s.strip()]
        best = max(
            enumerate(sentences),
            key=lambda pair: (len(query_terms & set(tokenize(pair[1]))), -pair[0]),
        )[1]
        best = " ".join(best.split())
        if len(best) > self.max_sentence_chars:
            best = best[: self.max_sentence_chars].rstrip() + "..."
        return best

    def generate(self, request: GenerationRequest) -> GeneratorOutput:
        """Quote and cite the leading retained passages.

        Args:
            request: Validated request with at least one retained passage.

        Returns:
            GeneratorOutput with ``[n]`` markers matching ``cited_chunk_ids``
            and no usage, since no provider is called.

        Raises:
            GenerationError: For a request with no retained passages.
        """
        if type(request) is not GenerationRequest or not request.passages:
            raise GenerationError("Supply a request with retained passages.")
        query_terms = frozenset(tokenize(request.query))
        parts: list[str] = []
        cited: list[str] = []
        for marker, item in enumerate(request.passages[: self.max_passages], 1):
            sentence = self._best_sentence(item.chunk.content, query_terms)
            parts.append(f"{sentence} [{marker}]")
            cited.append(item.chunk_id)
        return GeneratorOutput(" ".join(parts), tuple(cited))


@dataclass(frozen=True, slots=True)
class Citation:
    """One cited retained passage, holding its Story 5 item by identity.

    Args:
        marker: One-based citation number, matching ``[marker]`` in the answer.
        item: The retained ContextFilterItem; all retrieval evidence and
            provenance stay reachable through it. Hidden from repr.

    Raises:
        GenerationError: For a malformed marker or item.
    """

    marker: int
    item: ContextFilterItem = field(repr=False)

    def __post_init__(self) -> None:
        """Validate the marker and the retained-item type."""
        if type(self.marker) is not int or self.marker < 1:
            raise GenerationError("Use a positive integer citation marker.")
        if type(self.item) is not ContextFilterItem:
            raise GenerationError("Cite a validated Story 5 ContextFilterItem.")

    @property
    def chunk_id(self) -> str:
        """Return the cited chunk's stable identifier."""
        return self.item.chunk_id

    @property
    def document_id(self) -> str:
        """Return the cited chunk's parent document identifier."""
        return self.item.document_id

    @property
    def source_id(self) -> str:
        """Return the cited chunk's application source key."""
        return self.item.chunk.provenance.source_id


@dataclass(frozen=True, slots=True)
class GeneratedAnswer:
    """Validated answer with citations resolved against the filtered context.

    Args:
        text: Accepted answer text, untrusted data; hidden from repr.
        citations: Ordered Citation tuple with contiguous markers from 1;
            empty only for an abstention.
        request: The exact GenerationRequest answered; hidden from repr.
        generator_id: Identifier of the configured generator.
        evidence_kind: "deterministic_offline" for the extractive generator
            or an abstention; "injected" for any other generator.
        abstained: True when no retained context existed, so no generator
            was called and the fixed abstention text was returned.
        usage: Generator-reported TokenUsage, or None.

    Raises:
        GenerationError: For inconsistent text, citation, or abstention evidence.
    """

    text: str = field(repr=False)
    citations: tuple[Citation, ...]
    request: GenerationRequest = field(repr=False)
    generator_id: str
    evidence_kind: GenerationEvidenceKind
    abstained: bool
    usage: TokenUsage | None = None

    def __post_init__(self) -> None:
        """Re-validate that every citation is a retained item of the request."""
        _bounded_text(self.text, "answer text", MAX_ANSWER_BYTES)
        _bounded_text(self.generator_id, "generator_id", MAX_ID_BYTES)
        if type(self.request) is not GenerationRequest:
            raise GenerationError("Retain the validated GenerationRequest.")
        if self.evidence_kind not in ("deterministic_offline", "injected"):
            raise GenerationError("Use evidence_kind deterministic_offline/injected.")
        if type(self.abstained) is not bool:
            raise GenerationError("Use bool for abstained.")
        if self.usage is not None and type(self.usage) is not TokenUsage:
            raise GenerationError("Retain usage as a validated TokenUsage or None.")
        if type(self.citations) is not tuple or any(
            type(c) is not Citation for c in self.citations
        ):
            raise GenerationError("Supply a tuple of validated Citation objects.")
        if self.abstained != (not self.request.passages):
            raise GenerationError("Abstain exactly when no context was retained.")
        if self.abstained and (self.citations or self.text != ABSTENTION_TEXT):
            raise GenerationError("An abstention carries fixed text and no citations.")
        if not self.abstained and not self.citations:
            raise GenerationError("A generated answer must cite retained context.")
        retained = {id(item) for item in self.request.passages}
        for marker, citation in enumerate(self.citations, 1):
            if citation.marker != marker:
                raise GenerationError("Keep citation markers contiguous from 1.")
            if id(citation.item) not in retained:
                raise GenerationError("Cite only items retained by the request.")
        if len({c.chunk_id for c in self.citations}) != len(self.citations):
            raise GenerationError("Deduplicate cited chunks.")


def generate_answer(
    request: GenerationRequest, generator: AnswerGenerator
) -> GeneratedAnswer:
    """Generate a grounded, cited answer from a validated request.

    An empty retained context is answered by a fixed abstention without
    calling the generator, so no answer is produced without grounding.
    Otherwise the generator is called once; its output must be an exact
    GeneratorOutput whose citations all name retained chunks.

    Args:
        request: Validated GenerationRequest over a Story 5 FilteredContext.
        generator: Application-selected AnswerGenerator.

    Returns:
        GeneratedAnswer with citations resolved to retained items by identity.

    Raises:
        GenerationError: For an invalid request or generator, a generator
            failure, malformed output, or a citation outside the context.
            Messages are fixed and no generator exception is chained.
    """
    if type(request) is not GenerationRequest:
        raise GenerationError("Supply a validated GenerationRequest.")
    try:
        generator_id = generator.generator_id
    except Exception:
        raise GenerationError("Configure an AnswerGenerator with an id.") from None
    _bounded_text(generator_id, "generator_id", MAX_ID_BYTES)
    if not callable(getattr(generator, "generate", None)):
        raise GenerationError("Configure an AnswerGenerator with generate().")
    deterministic = type(generator) is ExtractiveAnswerGenerator
    if not request.passages:
        return GeneratedAnswer(
            ABSTENTION_TEXT, (), request, generator_id, "deterministic_offline", True
        )
    try:
        output = generator.generate(request)
    except Exception:
        raise GenerationError(
            "The answer generator failed; repair the generator or its configuration."
        ) from None
    if type(output) is not GeneratorOutput:
        raise GenerationError("The answer generator returned malformed output.")
    by_id = {item.chunk_id: item for item in request.passages}
    if any(chunk_id not in by_id for chunk_id in output.cited_chunk_ids):
        raise GenerationError(
            "The answer generator cited a chunk outside the filtered context."
        )
    citations = tuple(
        Citation(marker, by_id[chunk_id])
        for marker, chunk_id in enumerate(output.cited_chunk_ids, 1)
    )
    return GeneratedAnswer(
        output.text,
        citations,
        request,
        generator_id,
        "deterministic_offline" if deterministic else "injected",
        False,
        output.usage,
    )
