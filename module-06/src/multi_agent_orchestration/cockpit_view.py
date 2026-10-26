"""Presentation-layer cockpit evidence, view and state contracts (S1).

Immutable reviewer-facing view state and static guidance for the unified
cockpit. This layer transforms already-validated application objects and
curated recorded/historical facts into labelled view state; it is never an
orchestration, provider, policy or live-execution authority, never telemetry
storage or an evidence backend, and never a LangSmith, Prometheus or Grafana
client. It holds no credential material and performs no network, model,
delivery, telemetry or container action on import, construction, rendering or
any state transition; the explicit operational check lives in ``cockpit_ops``
and the explicit LangSmith inspection in ``cockpit_langsmith``.

Evidence model (accepted composition, no coarse enum): every item carries an
``execution_kind``, optional ``provenance`` in the accepted authoritative
vocabulary, an optional ``delivery_confirmation`` in the committed LangSmith
vocabulary, an optional recorded ``operational_classification`` and, for
curated records, the accepted classification text preserved verbatim. The
compositional invariants below reject combinations that would strengthen or
blur accepted evidence. Fresh views deliberately have no
``accepted_classification`` field: fresh execution views cannot be created
from static ledger evidence.

Intentional exclusion: the committed live-family delivery vocabulary also
contains ``synthetic_transport`` (an injected/bounded transport). The
reviewer cockpit never produces or presents injected-transport evidence as
part of the accepted final experience, so there is deliberately no
producible cockpit state for it; a later Builder must not "complete" the
delivery vocabulary with it.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from .contracts import Contract

OPERATIONAL_CLASSIFICATION = (
    "authorized deterministic local operational-telemetry pipeline "
    "verification"
)


class ExecutionKind(StrEnum):
    """How the presented content was produced."""

    DETERMINISTIC_DEMO = "deterministic_demo"
    CANONICAL_LIVE_DEMO = "canonical_live_demo"
    CANONICAL_REAL_LOCAL = "canonical_real_local"
    UNAVAILABLE = "unavailable"
    NOT_EXECUTED = "not_executed"


class PresentationProvenance(StrEnum):
    """Accepted authoritative provenance vocabulary; never renamed."""

    SYNTHETIC_OFFLINE = "synthetic_offline"
    LOCAL_PROVIDER_EXECUTION = "local_provider_execution"


class DeliveryConfirmation(StrEnum):
    """Committed LangSmith delivery/confirmation vocabulary; verbatim only.

    ``accepted_only`` means the write was accepted but the run was not
    readable in the bounded window; it never carries a service read.

    ``unverified_write`` means the write was accepted with an HTTP 2xx
    status and no programmatic service read-back exists.
    """

    SERVICE_READ = "service_read"
    ACCEPTED_ONLY = "accepted_only"
    UNVERIFIED_WRITE = "unverified_write"
    NOT_SENT = "not_sent"


class ViewSource(StrEnum):
    """Whether a presented item is fresh or curated/recorded."""

    FRESH_EXECUTION = "fresh_execution"
    RECORDED_HISTORICAL = "recorded_historical"


class CockpitMode(StrEnum):
    """Reviewer-facing cockpit modes; deterministic Demo is the baseline."""

    DEMO = "demo"
    LIVE_BYOK = "live_byok"
    OPERATIONS = "operations"
    GUIDE = "guide"


class OperationsState(StrEnum):
    """Operations surface activation life cycle; ``cockpit_ops`` performs queries."""

    NOT_ACTIVATED = "not_activated"
    QUERY_REQUESTED = "query_requested"
    UNAVAILABLE = "unavailable"
    RESULT = "result"


class LiveCapabilityState(StrEnum):
    """Whether live/BYOK execution is available in the current posture."""

    UNAVAILABLE = "unavailable"
    AVAILABLE_LOCAL_TRUSTED = "available_local_trusted"


_INERT_TEXT = Annotated[str, Field(strict=True, min_length=1, max_length=256)]


class EvidenceView(Contract):
    """Immutable fresh-evidence view: one produced, validated item.

    A fresh view has no accepted classification: fresh view state cannot be
    created from static ledger evidence. Model output, provider payloads and
    secrets have no field in this contract at all.

    Attributes:
        execution_kind: How the presented content was produced.
        provenance: Accepted provenance vocabulary where applicable.
        delivery_confirmation: Committed LangSmith vocabulary where
            applicable.
        reference_id: Inert externally sourced identifier text, escaped by
            the renderer; never a link authority.
    """

    execution_kind: ExecutionKind
    provenance: PresentationProvenance | None = None
    delivery_confirmation: DeliveryConfirmation | None = None
    reference_id: _INERT_TEXT | None = None

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    @model_validator(mode="after")
    def combination(self) -> "EvidenceView":
        """Reject evidence combinations stronger than their source.

        Raises:
            ValueError: A combination not supported by accepted evidence.
        """
        if self.execution_kind is ExecutionKind.CANONICAL_LIVE_DEMO:
            if self.provenance is not PresentationProvenance.SYNTHETIC_OFFLINE:
                raise ValueError(
                    "Canonical live demonstration requires synthetic_offline "
                    "provenance."
                )
            if self.delivery_confirmation not in (None, DeliveryConfirmation.NOT_SENT):
                raise ValueError(
                    "A synthetic demonstration carries no external delivery "
                    "confirmation."
                )
        elif self.execution_kind is ExecutionKind.CANONICAL_REAL_LOCAL:
            if self.provenance is not PresentationProvenance.LOCAL_PROVIDER_EXECUTION:
                raise ValueError(
                    "Real local execution provenance is required."
                )
        elif self.execution_kind is ExecutionKind.DETERMINISTIC_DEMO:
            if self.provenance is not None:
                raise ValueError(
                    "Deterministic demo views carry no model provenance."
                )
        elif self.provenance is not None or self.delivery_confirmation is not None:
            raise ValueError(
                "An unavailable or not-executed view carries no provenance or "
                "delivery fact."
            )
        return self

    @property
    def wrote_externally(self) -> bool:
        """Whether an external write occurred; ``not_sent`` never implies it."""
        return self.delivery_confirmation in (
            DeliveryConfirmation.SERVICE_READ,
            DeliveryConfirmation.ACCEPTED_ONLY,
            DeliveryConfirmation.UNVERIFIED_WRITE,
        )

    @property
    def service_read_confirmed(self) -> bool:
        """True only for ``service_read``; ``unverified_write`` never implies it."""
        return self.delivery_confirmation is DeliveryConfirmation.SERVICE_READ

    @property
    def source(self) -> ViewSource:
        """Fresh view state; cannot be presented as recorded history."""
        return ViewSource.FRESH_EXECUTION


class HistoricalEvidence(Contract):
    """Immutable curated recorded/historical item from accepted records.

    Presentation-layer static source derived from accepted repository
    ledger/documentation facts: not a fresh execution, not a runtime query,
    not telemetry storage, not a new evidence backend. The accepted
    classification text is preserved verbatim and never rewritten or
    inferred. Configuration never authorizes a privileged action.

    Attributes:
        execution_kind: How the recorded content was produced.
        provenance: Accepted provenance vocabulary where applicable.
        delivery_confirmation: Accepted LangSmith vocabulary where
            applicable; exact and never strengthened.
        operational_classification: The one recorded operational
            classification text; never invented or renamed.
        accepted_classification: The accepted classification preserved
            verbatim, as accepted.
        reference_id: Inert externally sourced identifier text.
        summary: Short curated factual summary line, or None.
    """

    execution_kind: Literal[
        ExecutionKind.DETERMINISTIC_DEMO,
        ExecutionKind.CANONICAL_LIVE_DEMO,
        ExecutionKind.CANONICAL_REAL_LOCAL,
    ]
    provenance: PresentationProvenance | None = None
    delivery_confirmation: DeliveryConfirmation | None = None
    operational_classification: str | None = None
    accepted_classification: Annotated[
        str, Field(strict=True, min_length=1, max_length=400)
    ]
    reference_id: _INERT_TEXT | None = None
    summary: (
        Annotated[str, Field(strict=True, min_length=1, max_length=400)] | None
    ) = None

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    @model_validator(mode="after")
    def combination(self) -> "HistoricalEvidence":
        """Reject records with facts their accepted record does not carry.

        Raises:
            ValueError: A combination not supported by accepted evidence.
        """
        if self.execution_kind is ExecutionKind.CANONICAL_LIVE_DEMO:
            if self.provenance is not PresentationProvenance.SYNTHETIC_OFFLINE:
                raise ValueError(
                    "Recorded synthetic demonstration requires synthetic_offline "
                    "provenance."
                )
        elif self.execution_kind is ExecutionKind.CANONICAL_REAL_LOCAL:
            if self.provenance is not PresentationProvenance.LOCAL_PROVIDER_EXECUTION:
                raise ValueError(
                    "Recorded real local execution keeps local_provider provenance."
                )
        elif self.provenance is not None:
            raise ValueError(
                "A deterministic historical record carries no model provenance."
            )
        if (
            self.delivery_confirmation is DeliveryConfirmation.NOT_SENT
            and self.execution_kind is ExecutionKind.DETERMINISTIC_DEMO
        ):
            raise ValueError(
                "not_sent is a delivery-state value, not a recorded confirmation."
            )
        if self.operational_classification is not None and (
            self.operational_classification != OPERATIONAL_CLASSIFICATION
        ):
            raise ValueError(
                "Only the accepted operational classification text is recorded."
            )
        return self

    @property
    def wrote_externally(self) -> bool:
        """Whether the accepted record shows an external write occurred."""
        return self.delivery_confirmation in (
            DeliveryConfirmation.SERVICE_READ,
            DeliveryConfirmation.ACCEPTED_ONLY,
            DeliveryConfirmation.UNVERIFIED_WRITE,
        )

    @property
    def service_read_confirmed(self) -> bool:
        """True only for ``service_read`` records."""
        return self.delivery_confirmation is DeliveryConfirmation.SERVICE_READ

    @property
    def source(self) -> ViewSource:
        """Recorded/historical; never presented as fresh evidence."""
        return ViewSource.RECORDED_HISTORICAL


class GuidanceSection(Contract):
    """One static reviewer guidance panel, rendered by the Guide tab.

    Attributes:
        title: Short unique panel heading.
        body: Static guidance text; no caller or runtime content.
    """

    title: Annotated[str, Field(strict=True, min_length=1, max_length=120)]
    body: Annotated[str, Field(strict=True, min_length=1, max_length=2000)]


_GUIDANCE = {
    "start": "Start here",
    "what": "What Module 6 demonstrates",
    "demo": "Demo mode (offline, no keys)",
    "live": "Live / BYOK (local trusted operator)",
    "classes": "Evidence classes",
    "history": "Historical versus fresh evidence",
    "stack": "Observability: LangSmith, OpenTelemetry, Prometheus, Grafana",
    "ops": "Operations tab and current-host localhost",
    "langsmith": "LangSmith: specialist AI/agent tracing",
    "test": "How to test each capability",
    "bounds": "What the evidence does not prove",
}
GUIDANCE_SECTIONS: tuple[GuidanceSection, ...] = (
    GuidanceSection(
        title=_GUIDANCE["start"],
        body=(
            "Start on the Deterministic demo tab: choose a demonstration, keep "
            "the sample text and select Run demonstration. Each result shows "
            "its evidence label, validated facts and local trace. Then open "
            "Operations and LangSmith tracing to compare recorded historical "
            "evidence with an explicit current check, and Live / BYOK to see "
            "why real inference is reserved for a trusted local operator. "
            "Nothing on this page executes, queries or delivers anything until "
            "you select an action."
        ),
    ),
    GuidanceSection(
        title=_GUIDANCE["what"],
        body=(
            "Module 6 demonstrates bounded, evidence-governed multi-agent "
            "orchestration in a standalone module. Orchestration architectures "
            "represented: LangGraph coordinator-worker, sequential, parallel "
            "and hierarchical graphs; a CrewAI collaborative crew; Google ADK "
            "delegation in one process and across two independent local "
            "worker processes; the canonical Researcher -> Analyst -> Critic "
            "workflow with bounded repair; and a local scaling benchmark. "
            "Observability is layered: application observation, LangSmith "
            "AI/agent tracing, and an OpenTelemetry -> Collector -> "
            "Prometheus -> Grafana operational stack, all presented through "
            "this one Streamlit reviewer cockpit."
        ),
    ),
    GuidanceSection(
        title=_GUIDANCE["demo"],
        body=(
            "Demo mode runs the accepted deterministic applications offline: "
            "no model inference, no provider, no credentials, no Docker and "
            "no telemetry delivery. Every result is deterministic demo "
            "evidence (deterministic_demo, or canonical_live_demo with "
            "synthetic_offline provenance for the synthetic canonical "
            "workflow): real deterministic LangGraph, CrewAI and ADK "
            "execution, not screenshots or fabricated success. A Demo result "
            "proves runtime scheduling, validated hand-offs, bounded failure "
            "handling and evidence creation. It does not prove model "
            "reasoning or quality, hosted operation, remote distribution or "
            "production capacity."
        ),
    ),
    GuidanceSection(
        title=_GUIDANCE["live"],
        body=(
            "Live / BYOK runs the same canonical Researcher -> Analyst -> "
            "Critic workflow with real local model inference (local Ollama, "
            "qwen2.5-coder:7b only) for a trusted private operator whose "
            "embedding supplies the runtime. BYOK means that trusted runtime "
            "brings its own provider connectivity; this page never asks for, "
            "stores or displays a key. Each click is a fresh explicit "
            "authorization for one execution under the fixed ADR-008 NORMAL "
            "profile; credential presence alone never authorizes anything, "
            "authority is never derived from session, environment or model "
            "output, and there is no automatic rerun or provider escalation. "
            "Public live is intentionally fail-closed: a public visitor must "
            "never be able to spend an operator's compute or credentials, and "
            "no deployment-compatible authority boundary exists, so a deployed "
            "or stock page always reports live as unavailable."
        ),
    ),
    GuidanceSection(
        title=_GUIDANCE["classes"],
        body=(
            "Each result carries a composed label instead of one coarse "
            "status. execution_kind: deterministic_demo, canonical_live_demo "
            "(synthetic, offline; no model executed), canonical_real_local "
            "(real local inference), unavailable or not_executed. provenance: "
            "synthetic_offline or local_provider_execution. "
            "delivery_confirmation (LangSmith only): service_read (the service "
            "returned the recorded run), accepted_only (write accepted, no "
            "read-back in the window), unverified_write (HTTP 2xx write, no "
            "read-back) or not_sent. operational_classification: only the one "
            "accepted recorded pipeline verification. source: fresh_execution "
            "or recorded_historical. LangSmith, OpenTelemetry and metric "
            "states on a run are local projections, never external delivery. "
            "Run 3 stays an out_of_policy_observation, and wording never "
            "upgrades a label."
        ),
    ),
    GuidanceSection(
        title=_GUIDANCE["history"],
        body=(
            "Recorded evidence is curated static content preserved from the "
            "accepted project records, labelled recorded/historical, with "
            "each accepted classification shown verbatim. It is never "
            "presented as a fresh execution and can never be promoted into "
            "one; fresh results always say when they were produced, and a "
            "failed or unavailable current check is never filled in from "
            "history."
        ),
    ),
    GuidanceSection(
        title=_GUIDANCE["stack"],
        body=(
            "AI/agent observability: LangSmith, the specialist tracing "
            "system for agent runs. Operational observability: OpenTelemetry "
            "instruments the application -> the OpenTelemetry Collector is "
            "the ingestion boundary -> Prometheus stores metrics and "
            "evaluates three alert rules -> Grafana is the specialist "
            "dashboard and drill-down. This containerized stack was verified "
            "end-to-end locally (recorded 2026-10-23: 14 of 14 workflows, "
            "dashboard provisioned, rules loaded); it is not hosted telemetry "
            "and Prometheus is never exposed publicly. Unified presentation: "
            "this Streamlit cockpit curates both natively. It never embeds "
            "Grafana, Prometheus or LangSmith, and it shows a current-host "
            "dashboard reference only as inert text after an explicit check "
            "has read the provisioned dashboard."
        ),
    ),
    GuidanceSection(
        title=_GUIDANCE["ops"],
        body=(
            "The Operations tab shows operational evidence only after you "
            "explicitly request a bounded local query: one read-only attempt "
            "against fixed 127.0.0.1 Prometheus and Grafana endpoints, with no "
            "retries or polling. Any 127.0.0.1 value means the loopback of "
            "the host running the app: in a deployed environment that is the "
            "deployed host or container, never a developer workstation, and "
            "the UI labels it accordingly. An unreachable local stack shows "
            "an honest unavailable state; values are never fabricated and "
            "history is never passed off as a fresh observation."
        ),
    ),
    GuidanceSection(
        title=_GUIDANCE["langsmith"],
        body=(
            "LangSmith is the specialist AI/agent tracing surface. The "
            "cockpit shows the recorded evidence natively (no iframe, no "
            "fetch): the accepted deterministic delivery (service_read) and "
            "the recorded live-model Run 5 (unverified_write), never merged. "
            "Identifiers are inert text. The explicit current check reads "
            "only allowlisted recorded traces through a read capability that "
            "a trusted runtime must supply; this page supplies none, so it "
            "reports unavailable without touching credentials. A positive "
            "read would mean only a current service observation of a "
            "recorded trace, never a new execution or delivery."
        ),
    ),
    GuidanceSection(
        title=_GUIDANCE["test"],
        body=(
            "Demo: run each demonstration and expect completed with validated "
            "roles; set one step on a graph to see denied, or a very short "
            "deadline to see timed_out. Synthetic canonical workflow: expect "
            "a synthetic_offline receipt with per-role accounting and local "
            "projections. Scaling: run the quick check and expect every cap "
            "respected and every worker reaped. Operations: select the check; "
            "without the local stack expect an honest unavailable state, with "
            "it expect fresh current-host values beside the unchanged recorded "
            "verification. LangSmith: select the check and expect "
            "unavailable in this posture. Live / BYOK: the action stays "
            "disabled unless a trusted embedding supplies the runtime. Each "
            "success proves exactly what its panel states."
        ),
    ),
    GuidanceSection(
        title=_GUIDANCE["bounds"],
        body=(
            "Recorded evidence does not prove production deployment, hosted "
            "observability, production reliability, SLA or SLO attainment, "
            "statistical reliability, hosted-model portability, release "
            "acceptance, or module completion. It proves exactly what its "
            "accepted record states, and neither more nor less."
        ),
    ),
)


class LiveCapability(Contract):
    """Truthful live/BYOK availability for the two runtime postures.

    Local trusted/operator live and deployed/public live are separate
    postures with separate availability. Local live reflects only the
    accepted trusted local/operator runtime: when that runtime is present,
    local live is available and this representation asserts nothing about a
    deployed boundary. Deployed/public live is always unavailable in the
    accepted architecture: no deployment-compatible
    secret/identity/authorization boundary exists, and a future one would
    need separate implementation, independent verification and explicit
    enablement — never a boolean flag. A deployed/public visitor never
    inherits local/operator authority. Credential presence is never an
    availability or authorization signal (this contract has no credential
    state at all); presentation state never constructs
    ``LiveAuthorization`` or any other privileged authority.

    Attributes:
        local_trusted_operator_runtime: Whether trusted embedding code
            injected the private-operator runtime for this render.
        deployment_compatible_authority_verified: Legacy descriptive flag
            kept for compatibility; it never enables public live.
    """

    local_trusted_operator_runtime: bool = False
    deployment_compatible_authority_verified: bool = False

    @property
    def local_live_available(self) -> bool:
        """The trusted local/operator runtime alone enables local live."""
        return self.local_trusted_operator_runtime

    @property
    def deployed_public_live_available(self) -> bool:
        """Fail closed: a verified flag is not an implemented authority boundary.

        The legacy field remains descriptive data for compatibility. No public
        boundary is accepted; a future implementation needs independent review,
        explicit enablement and fresh execution authority, not boolean toggles.
        """
        return False


class OperationsActivation(Contract):
    """Operations surface activation state; no query is embedded here.

    Constructing, importing or rendering this state performs zero requests.
    ``cockpit_ops`` performs the explicit bounded local query only when the
    reviewer selects the check; this contract only carries the activation
    state.

    Attributes:
        state: The activation state; ``not_activated`` by default.
    """

    state: OperationsState = OperationsState.NOT_ACTIVATED


def age_in_seconds(happened_ns: int) -> int:
    """Approximate age of a stored observation, in whole seconds.

    Args:
        happened_ns: Wall-clock nanosecond marker captured with the result.

    Returns:
        The whole number of seconds since the marker, floored at zero;
        presentation freshness only, never an authority or a probe.
    """
    import time

    return max(0, (time.time_ns() - happened_ns) // 1_000_000_000)


DEFAULT_COCKPIT_STATE = (
    CockpitMode.DEMO,
    LiveCapability(),
    OperationsActivation(),
)

CURATED_RUN_3 = HistoricalEvidence(
    execution_kind=ExecutionKind.CANONICAL_REAL_LOCAL,
    provenance=PresentationProvenance.LOCAL_PROVIDER_EXECUTION,
    accepted_classification="out_of_policy_observation",
    reference_id="612ab93b-368f-4775-af2b-ec2338c48bf6",
    summary=(
        "recorded real-local workflow execution; retained as an out-of-policy "
        "technical observation; not retro-authorized; not an authorized live "
        "success"
    ),
)
CURATED_RUN_4 = HistoricalEvidence(
    execution_kind=ExecutionKind.CANONICAL_REAL_LOCAL,
    provenance=PresentationProvenance.LOCAL_PROVIDER_EXECUTION,
    accepted_classification="Authorized current-path real-local verification",
    summary=(
        "one explicitly human-authorized NORMAL-profile real-local "
        "execution; authorization consumed by the single attempt; the "
        "accepted record carries no recorded identifier"
    ),
)
CURATED_RUN_5 = HistoricalEvidence(
    execution_kind=ExecutionKind.CANONICAL_REAL_LOCAL,
    provenance=PresentationProvenance.LOCAL_PROVIDER_EXECUTION,
    delivery_confirmation=DeliveryConfirmation.UNVERIFIED_WRITE,
    accepted_classification=(
        "One-run live-model current-path LangSmith projection and delivery "
        "verification (`unverified_write` receipt); authority-consumption "
        "status operator-attested and not independently confirmed"
    ),
    reference_id="e48944ac-1e67-4562-b6e7-e3cab5abbb4c",
    summary=(
        "recorded live-model trace projection and one delivered write under "
        "the committed unverified_write contract; global one-inference and "
        "one-write bounds not independently confirmed"
    ),
)
CURATED_LANGSMITH_DELIVERY = HistoricalEvidence(
    execution_kind=ExecutionKind.DETERMINISTIC_DEMO,
    delivery_confirmation=DeliveryConfirmation.SERVICE_READ,
    accepted_classification="current-path external LangSmith delivery verification",
    reference_id="01a166fa-1c8d-7b40-9686-a08cfd14444f",
    summary=(
        "independently accepted deterministic sanitized-trace delivery: one "
        "POST /runs/batch, 202, 4 runs accepted, root run returned by the "
        "service"
    ),
)
CURATED_OPERATIONAL_PIPELINE = HistoricalEvidence(
    execution_kind=ExecutionKind.DETERMINISTIC_DEMO,
    operational_classification=OPERATIONAL_CLASSIFICATION,
    accepted_classification=OPERATIONAL_CLASSIFICATION,
    summary=(
        "14/14 workflows (12 completed, 2 denied); 6 exports accepted, 0 "
        "failed; Prometheus total 14.0; 3 of 3 alert rules; Grafana healthy "
        "with the dashboard provisioned; datasource total 14.0; pipeline "
        "verification passed"
    ),
)

CURATED_HISTORICAL_RECORDS: tuple[HistoricalEvidence, ...] = (
    CURATED_RUN_3,
    CURATED_RUN_4,
    CURATED_RUN_5,
    CURATED_LANGSMITH_DELIVERY,
    CURATED_OPERATIONAL_PIPELINE,
)

__all__ = [
    "COCKPIT_MODE_DEFAULT",
    "DEFAULT_COCKPIT_STATE",
    "CURATED_HISTORICAL_RECORDS",
    "GUIDANCE_SECTIONS",
    "GuidanceSection",
    "EvidenceView",
    "ExecutionKind",
    "HistoricalEvidence",
    "LiveCapability",
    "OperationsActivation",
    "OperationsState",
    "CockpitMode",
    "ViewSource",
    "DeliveryConfirmation",
    "PresentationProvenance",
    "OPERATIONAL_CLASSIFICATION",
]

COCKPIT_MODE_DEFAULT = CockpitMode.DEMO
