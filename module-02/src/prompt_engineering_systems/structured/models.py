"""Application-owned typed answer contracts for later generation workflows."""

from typing import Self

from pydantic import Field, model_validator

from ..contracts import StrictContract


class SourceReference(StrictContract):
    """A bounded source identifier and excerpt, without executable authority.

    Identifier/excerpt limits keep citations suitable for a small answer lab.

    Attributes:
        source_id: Nonempty opaque identifier, at most 128 characters.
        excerpt: Nonempty supporting text, at most 2,048 characters. It remains
            content rather than an executable instruction or authority claim.

    Raises:
        ValidationError: If direct construction violates strict fields or bounds.
    """

    source_id: str = Field(min_length=1, max_length=128)
    excerpt: str = Field(min_length=1, max_length=2_048)


class StructuredAnswer(StrictContract):
    """A nonblank answer with at most 32 uniquely identified source references.

    Field-level bounds keep individual records inspectable. Aggregate UTF-8
    and document budgets independently restrict the total accepted output.

    Attributes:
        answer: Nonblank text, at most 8,192 characters.
        sources: At most 32 typed references with unique identifiers; defaults
            to an independent empty list. Containers remain mutable after validation.

    Raises:
        ValidationError: If direct construction violates fields or invariants.
    """

    answer: str = Field(min_length=1, max_length=8_192)
    sources: list[SourceReference] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def check_answer_invariants(self) -> Self:
        """Reject blank answers and ambiguous repeated source identifiers.

        Returns:
            This validated answer without altering its content.

        Raises:
            ValueError: If the answer is blank or source identifiers repeat.
        """
        if not self.answer.strip():
            raise ValueError("Answer must contain non-whitespace text.")
        identifiers = [source.source_id for source in self.sources]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Source identifiers must be unique within an answer.")
        return self
