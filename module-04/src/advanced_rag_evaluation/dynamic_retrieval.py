"""Deterministic dynamic-retrieval policy (M4-OPT-05).

The Module 4 source names "dynamic retrieval" as a topic but prescribes no
algorithm. The policy implemented here -- selecting a retrieval breadth
(``top_k``) from the query's own tokenized term count -- is explicitly an
**engineering implementation decision**, approved during Story 1 planning
(Approved Human Resolution 5, see ``module-04/docs/ARCHITECTURE.md``), not a
course-mandated method. It was chosen because it is simple enough to teach
and audit in one function, fully deterministic, and uses only a query
characteristic already produced by an accepted Module 4 boundary (Story 2's
``bm25.tokenize``), rather than inventing a new text-analysis dependency.

The policy consults only the query text itself -- never retrieved content,
model output, or any other external instruction -- and every value it can
select is bounded by explicit, validated configuration limits. A query
containing instruction-shaped or numeric-looking text (for example, text
that asks for a specific ``top_k``) is tokenized like any other text and can
only ever shift which of the two configured, bounded ``top_k`` values is
selected; it can never inject an arbitrary value of its own.
"""

from dataclasses import dataclass

from .bm25 import tokenize
from .errors import DynamicRetrievalConfigurationError, DynamicRetrievalError

MAX_TOP_K = 10_000
_BRANCHES = ("short_query", "long_query")


@dataclass(frozen=True, slots=True)
class DynamicRetrievalPolicyConfig:
    """Application-owned bounds for the short/long query-breadth policy.

    Args:
        short_query_max_terms: A query tokenizing to at most this many terms
            is classified "short", 1..1000. Default 3.
        short_query_top_k: Retrieval breadth selected for a short query,
            1..10000. Default 5.
        long_query_top_k: Retrieval breadth selected for a longer query,
            1..10000. Default 15.

    Raises:
        DynamicRetrievalConfigurationError: For invalid or inconsistent bounds.
    """

    short_query_max_terms: int = 3
    short_query_top_k: int = 5
    long_query_top_k: int = 15

    def __post_init__(self) -> None:
        """Validate bounded policy settings before any query is considered."""
        if (
            type(self.short_query_max_terms) is not int
            or type(self.short_query_max_terms) is bool
            or not 1 <= self.short_query_max_terms <= 1_000
        ):
            raise DynamicRetrievalConfigurationError(
                "Use an integer short_query_max_terms from 1 to 1000."
            )
        for name, value in (
            ("short_query_top_k", self.short_query_top_k),
            ("long_query_top_k", self.long_query_top_k),
        ):
            if (
                type(value) is not int
                or type(value) is bool
                or not 1 <= value <= MAX_TOP_K
            ):
                raise DynamicRetrievalConfigurationError(
                    f"Use an integer {name} from 1 to 10000."
                )


_DEFAULT_CONFIG = DynamicRetrievalPolicyConfig()


@dataclass(frozen=True, slots=True)
class DynamicRetrievalDecision:
    """An inspectable dynamic-retrieval decision: a value, and why it was chosen.

    Args:
        top_k: The selected, bounded retrieval breadth.
        term_count: The query's own tokenized term count that drove this
            decision.
        branch: Which configured rule fired: "short_query" or "long_query".
        rationale: A human-readable explanation naming the exact branch,
            term count, and configured threshold that produced this
            decision -- never only a bare number.

    Raises:
        DynamicRetrievalError: For malformed fields or an unknown branch.
    """

    top_k: int
    term_count: int
    branch: str
    rationale: str

    def __post_init__(self) -> None:
        """Validate decision shape; this never re-derives the decision itself."""
        if (
            type(self.top_k) is not int
            or type(self.top_k) is bool
            or not 1 <= self.top_k <= MAX_TOP_K
        ):
            raise DynamicRetrievalError("Use an integer top_k from 1 to 10000.")
        if type(self.term_count) is not int or self.term_count < 0:
            raise DynamicRetrievalError("Use a nonnegative integer term_count.")
        if type(self.branch) is not str or self.branch not in _BRANCHES:
            raise DynamicRetrievalError("Use branch short_query or long_query.")
        if type(self.rationale) is not str or not self.rationale.strip():
            raise DynamicRetrievalError("Supply a nonblank rationale string.")


def decide_retrieval(
    query: str, config: DynamicRetrievalPolicyConfig = _DEFAULT_CONFIG
) -> DynamicRetrievalDecision:
    """Deterministically select a bounded retrieval breadth for one query.

    A query tokenizing (via Story 2's ``tokenize``) to at most
    ``config.short_query_max_terms`` terms is treated as a short, likely
    keyword-style query and given a narrower, precision-favoring
    ``top_k``; a longer query is given a broader, recall-favoring
    ``top_k``. This two-branch rule is the entire policy: it is
    deliberately simple enough to audit in full from this function body.

    Args:
        query: Nonblank query text, treated as data; only its tokenized
            term count influences the decision.
        config: Validated bounded policy configuration.

    Returns:
        A DynamicRetrievalDecision carrying the selected top_k together
        with the term count and rationale that produced it.

    Raises:
        DynamicRetrievalConfigurationError: For a blank/non-string query or
            an invalid config.
    """
    if type(query) is not str or not query.strip():
        raise DynamicRetrievalConfigurationError("Supply a nonblank query string.")
    if type(config) is not DynamicRetrievalPolicyConfig:
        raise DynamicRetrievalConfigurationError(
            "Supply a validated DynamicRetrievalPolicyConfig."
        )

    term_count = len(tokenize(query))
    if term_count <= config.short_query_max_terms:
        branch = "short_query"
        top_k = config.short_query_top_k
        rationale = (
            f"Query tokenized to {term_count} term(s), at or below the "
            f"configured short-query threshold of "
            f"{config.short_query_max_terms}; selected top_k={top_k} to "
            f"favor precision for a short, likely keyword-style query."
        )
    else:
        branch = "long_query"
        top_k = config.long_query_top_k
        rationale = (
            f"Query tokenized to {term_count} term(s), above the configured "
            f"short-query threshold of {config.short_query_max_terms}; "
            f"selected top_k={top_k} to favor broader recall for a longer, "
            f"more specific query."
        )
    return DynamicRetrievalDecision(top_k, term_count, branch, rationale)
