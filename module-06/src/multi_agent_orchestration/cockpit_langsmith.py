"""Bounded read-only LangSmith evidence inspection for the reviewer cockpit (S4).

This application-layer boundary performs an explicit, reviewer-requested,
single-shot, read-only service inspection of exactly one allowlisted,
already-accepted recorded trace — never a write, never a model execution,
never the delivery of a new trace, and never an arbitrary lookup.

Architecture, all encoded here and therefore testable:

- importing, constructing, rendering or re-rendering this module or its
  contracts performs zero LangSmith calls and zero network requests;
- there is no credential, token or environment field of any kind; a
  credential is connectivity and never authority, and this module never
  looks one up — a trusted caller (a compatible operator/deployment runtime,
  not a public visitor) must EXPLICITLY supply an injected read capability
  implementing ``TraceReadProvider``; without one the honest result is
  ``not_available``;
- targets are allowlisted accepted recorded traces only, sourced from the
  accepted curated repository records: reviewer-supplied trace/run
  identifiers, project names, URLs and filters are never accepted, so there
  is no IDOR-style lookup surface and no SSRF surface;
- the module performs no HTTP itself: it validates the provider's reply
  against the accepted read contract (identifier/trace/project correlation
  and bounded shapes) and reports a typed current observation;
- responses are untrusted: unsupported shapes fail closed to truthful
  ``unavailable`` facts with sanitized handling; raw bodies, tokens and
  headers have no path into any observation error;
- a positive read means exactly "a current service observation of a
  recorded trace"; it never claims model execution, a freshly generated
  trace, or the recorded historical classifications of the source records,
  and it can never mutate them.

Accepted delivery semantics stay verbatim: ``service_read`` (the service
returned the recorded root run) and the live-family ``unverified_write``
(the write was accepted without a programmatic read-back) remain distinct;
S4 never performs the separately-authorized real read that a future story
would need to verify the recorded live model trace, and therefore never
upgrades it.
"""

import time
from typing import Annotated, Literal, Protocol

from pydantic import Field

from .cockpit_view import CURATED_LANGSMITH_DELIVERY, CURATED_RUN_5
from .contracts import Contract
from .langsmith_delivery import PROJECT


class TraceReadProvider(Protocol):
    """Read-only evidence capability injected by a trusted runtime.

    This is a trusted-caller seam, never reviewer or visitor input: the page
    offers no widget, URL or session value that can supply or replace it.

    Implementations must be read-only, bounded and application-owned; the
    cockpit never supplies network traffic, credentials, endpoints or write
    operations through this protocol, and this contract has no credential,
    token or environment field of any kind.
    """

    def __call__(self, trace_id: str) -> object:
        """Read one allowlisted recorded trace's bounded service facts.

        Args:
            trace_id: One allowlisted accepted recorded trace identifier.

        Returns:
            Untrusted reply data; only a dict whose ``trace_id`` and
            ``project`` match the request counts as a service read.

        Raises:
            OSError: The service could not be reached or read.
            ValueError: The reply could not be decoded.
        """


class LangSmithObservation(Contract):
    """One fresh, bounded, read-only LangSmith service observation.

    Attributes:
        read_state: ``result`` when the trusted provider returned a
            validated observation; ``unavailable`` when no compatible
            capability exists or the read failed; ``not_activated`` never
            appears in a fresh observation (it is the pre-action state).
        target_trace_id: The inspected allowlisted recorded trace, as inert
            bounded text.
        service_read: True only when the service returned the requested
            recorded evidence under the accepted read contract. It never
            claims model execution, a freshly generated trace, production
            readiness, or any authority.
        service_read_contract: The exact committed confirmation-vocabulary
            fact for what was read; never strengthened.
    """

    read_state: Literal["result", "unavailable"]
    target_trace_id: Annotated[
        str, Field(strict=True, min_length=1, max_length=64)
    ]
    service_read: bool | None = None
    service_read_contract: str | None = None


class StoredLangSmithObservation(Contract):
    """Presentation-scoped result of one explicit inspection; session-safe.

    Attributes:
        happened_ns: Wall-clock freshness marker of the inspection, in
            nanoseconds.
        observation: The validated current observation, or ``None``.
    """

    happened_ns: int
    observation: LangSmithObservation | None


def allowlisted_targets() -> tuple[tuple[str, str], ...]:
    """The accepted recorded traces, keyed by trace id to their source.

    Returns:
        Tuples of (trace id, accepted classification) drawn verbatim from
        the accepted curated records; no other target is ever inspectable.
    """
    return (
        (
            CURATED_LANGSMITH_DELIVERY.reference_id,
            CURATED_LANGSMITH_DELIVERY.accepted_classification,
        ),
        (
            CURATED_RUN_5.reference_id,
            CURATED_RUN_5.accepted_classification,
        ),
    )


def inspect_recorded_trace(
    trace_id: str | None,
    provider: TraceReadProvider | None,
) -> LangSmithObservation:
    """Read exactly one allowlisted recorded trace via a trusted capability.

    Args:
        trace_id: Exactly one accepted recorded trace identifier; anything
            else, including ``None``, is refused without calling the
            provider.
        provider: The trusted runtime's read capability; ``None`` means no
            compatible capability exists in the current posture and the
            honest result is ``unavailable`` — no credential lookup, no
            network call and no fabricated fact occurs.

    Returns:
        A validated current observation of a recorded trace; it never
        claims execution, delivery or authority, and it never mutates the
        recorded historical classifications or their delivery semantics.
        Expected read failures (``OSError``, ``ValueError``, ``TypeError``,
        ``KeyError``, ``AttributeError``) and mismatched replies are the
        truthful ``unavailable`` state.

    Raises:
        Exception: Only an unexpected provider failure outside the expected
            read failures propagates; the console boundary converts it into
            a sanitized ``ConsoleFaultError``.
    """
    allowed = dict(allowlisted_targets())
    if type(trace_id) is not str or trace_id not in allowed:
        return LangSmithObservation(
            read_state="unavailable",
            target_trace_id="not-allowlisted",
        )
    if provider is None:
        return LangSmithObservation(
            read_state="unavailable",
            target_trace_id=trace_id,
        )
    result = None
    found = None
    try:
        result = provider(trace_id)
        if type(result) is dict and result.get("trace_id") == trace_id and (
            result.get("project") == PROJECT
        ):
            found = True
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        found = False
    return LangSmithObservation(
        read_state=(
            "result" if found is True else "unavailable"
        ),
        target_trace_id=trace_id,
        service_read=(True if found is True else None),
        service_read_contract=(
            "service_read" if found is True else None
        ),
    )


def record_inspection(
    observation: LangSmithObservation,
) -> StoredLangSmithObservation:
    """Wrap one observation with its acquisition time for presentation.

    Args:
        observation: A validated current observation.

    Returns:
        The revalidated presentation-scoped record, timestamped now.
    """
    fresh = StoredLangSmithObservation.model_validate(
        {
            "happened_ns": time.time_ns(),
            "observation": observation,
        }
    )
    return fresh
