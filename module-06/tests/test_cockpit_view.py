"""S1 cockpit view/state contract tests: A-S coverage from the S1 task.

Focused deterministic tests for ``cockpit_view``: immutability, accepted
vocabulary preservation, cross-field invariants that reject misleading
evidence combinations, recorded/historical separation, no side effects on
import/construction/rendering, authority isolation and guidance truthfulness.
No network, model, credential, container or delivery action occurs anywhere
in this suite; forbidden side-effect helpers are monkeypatched to prove they
are never invoked.
"""

import subprocess
import sys

import pytest
from multi_agent_orchestration import cockpit_view
from multi_agent_orchestration.cockpit_view import (
    CURATED_HISTORICAL_RECORDS,
    CURATED_RUN_4,
    DEFAULT_COCKPIT_STATE,
    GUIDANCE_SECTIONS,
    OPERATIONAL_CLASSIFICATION,
    CockpitMode,
    DeliveryConfirmation,
    EvidenceView,
    ExecutionKind,
    GuidanceSection,
    HistoricalEvidence,
    LiveCapability,
    OperationsActivation,
    OperationsState,
    PresentationProvenance,
    ViewSource,
)
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def forbid_network_and_execution(monkeypatch):
    """Fail loudly if any S1 state construction attempts a forbidden effect."""
    import socket
    import urllib.request

    def explode(name):
        raise AssertionError(f"S1 must not use {name}")

    monkeypatch.setattr(socket, "socket", lambda *a, **k: explode("socket.socket"))
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: explode(
        "socket.create_connection"))
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **k: explode("urlopen"))
    yield


def test_a_view_contracts_are_immutable():
    """Every cockpit contract is frozen; mutation is a validation error."""
    view = EvidenceView(
        execution_kind=ExecutionKind.CANONICAL_LIVE_DEMO,
        provenance=PresentationProvenance.SYNTHETIC_OFFLINE,
    )
    with pytest.raises(ValidationError):
        view.execution_kind = ExecutionKind.CANONICAL_REAL_LOCAL
    record = HistoricalEvidence(
        execution_kind=ExecutionKind.CANONICAL_REAL_LOCAL,
        provenance=PresentationProvenance.LOCAL_PROVIDER_EXECUTION,
        accepted_classification="out_of_policy_observation",
    )
    with pytest.raises(ValidationError):
        record.accepted_classification = "something else"
    assert record.model_copy() is not None


def test_b_accepted_vocabulary_is_preserved_verbatim():
    """Type vocabularies use the accepted strings exactly."""
    assert {k.value for k in ExecutionKind} == {
        "deterministic_demo", "canonical_live_demo", "canonical_real_local",
        "unavailable", "not_executed"}
    assert {p.value for p in PresentationProvenance} == {
        "synthetic_offline", "local_provider_execution"}
    assert {c.value for c in DeliveryConfirmation} == {
        "service_read", "accepted_only", "unverified_write", "not_sent"}
    assert {s.value for s in ViewSource} == {
        "fresh_execution", "recorded_historical"}
    assert {m.value for m in CockpitMode} == {
        "demo", "live_byok", "operations", "guide"}
    assert {s.value for s in OperationsState} == {
        "not_activated", "query_requested", "unavailable", "result"}
    assert OPERATIONAL_CLASSIFICATION == (
        "authorized deterministic local operational-telemetry pipeline "
        "verification")


def test_c_live_demo_requires_synthetic_provenance():
    """The canonical live demonstration carries synthetic_offline only."""
    view = EvidenceView(
        execution_kind=ExecutionKind.CANONICAL_LIVE_DEMO,
        provenance=PresentationProvenance.SYNTHETIC_OFFLINE,
        delivery_confirmation=DeliveryConfirmation.NOT_SENT,
    )
    assert view.wrote_externally is False
    with pytest.raises(ValidationError):
        EvidenceView(execution_kind=ExecutionKind.CANONICAL_LIVE_DEMO)


def test_d_synthetic_demo_cannot_masquerade_as_real_local():
    """The synthetic demonstration never gains real-execution facts."""
    with pytest.raises(ValidationError):
        EvidenceView(
            execution_kind=ExecutionKind.CANONICAL_LIVE_DEMO,
            provenance=PresentationProvenance.LOCAL_PROVIDER_EXECUTION,
        )
    with pytest.raises(ValidationError):
        HistoricalEvidence(
            execution_kind=ExecutionKind.CANONICAL_LIVE_DEMO,
            provenance=PresentationProvenance.LOCAL_PROVIDER_EXECUTION,
            accepted_classification="canonical_real_local",
        )
    with pytest.raises(ValidationError):
        EvidenceView(
            execution_kind=ExecutionKind.CANONICAL_LIVE_DEMO,
            provenance=PresentationProvenance.SYNTHETIC_OFFLINE,
            delivery_confirmation=DeliveryConfirmation.UNVERIFIED_WRITE,
        )


def test_e_real_local_canot_masquerade_as_deterministic_or_synthetic():
    """Real local executions keep their provenance or are refused."""
    with pytest.raises(ValidationError):
        EvidenceView(execution_kind=ExecutionKind.CANONICAL_REAL_LOCAL)
    with pytest.raises(ValidationError):
        EvidenceView(
            execution_kind=ExecutionKind.CANONICAL_REAL_LOCAL,
            provenance=PresentationProvenance.SYNTHETIC_OFFLINE,
        )
    real = EvidenceView(
        execution_kind=ExecutionKind.CANONICAL_REAL_LOCAL,
        provenance=PresentationProvenance.LOCAL_PROVIDER_EXECUTION,
    )
    assert real.wrote_externally is False


def test_f_unavailable_and_not_executed_reject_success_facts():
    """No success fact can ride on unavailable/not-executed views."""
    for kind in (ExecutionKind.UNAVAILABLE, ExecutionKind.NOT_EXECUTED):
        for confirmation in (
            DeliveryConfirmation.SERVICE_READ,
            DeliveryConfirmation.ACCEPTED_ONLY,
            DeliveryConfirmation.UNVERIFIED_WRITE,
        ):
            with pytest.raises(ValidationError):
                EvidenceView(execution_kind=kind, delivery_confirmation=confirmation)
        with pytest.raises(ValidationError):
            EvidenceView(
                execution_kind=kind,
                provenance=PresentationProvenance.LOCAL_PROVIDER_EXECUTION,
            )
        with pytest.raises(ValidationError):
            EvidenceView(
                execution_kind=kind,
                provenance=PresentationProvenance.SYNTHETIC_OFFLINE,
            )
        base = EvidenceView(execution_kind=kind)
        assert base.wrote_externally is False
        assert base.service_read_confirmed is False


def test_g_recorded_history_cannot_become_fresh_and_fresh_has_no_accepted_text():
    """The separation is structural, not a convention."""
    assert "accepted_classification" not in EvidenceView.model_fields
    assert "source" not in EvidenceView.model_fields
    assert "source" not in HistoricalEvidence.model_fields
    fresh = EvidenceView(execution_kind=ExecutionKind.DETERMINISTIC_DEMO)
    recorded = HistoricalEvidence(
        execution_kind=ExecutionKind.CANONICAL_REAL_LOCAL,
        provenance=PresentationProvenance.LOCAL_PROVIDER_EXECUTION,
        accepted_classification="out_of_policy_observation",
    )
    assert fresh.source is ViewSource.FRESH_EXECUTION
    assert recorded.source is ViewSource.RECORDED_HISTORICAL
    assert recorded.source != fresh.source


def accepted_records_by_reference():
    return {record.reference_id: record for record in CURATED_HISTORICAL_RECORDS}


def test_h_curated_records_preserve_accepted_classifications_verbatim():
    """Every curated record preserves its accepted classification exactly."""
    assert accepted_records_by_reference() is not None
    expected = {
        "612ab93b-368f-4775-af2b-ec2338c48bf6": "out_of_policy_observation",
        "e48944ac-1e67-4562-b6e7-e3cab5abbb4c": (
            "One-run live-model current-path LangSmith projection and "
            "delivery verification (`unverified_write` receipt); "
            "authority-consumption status operator-attested and not "
            "independently confirmed"),
        "01a166fa-1c8d-7b40-9686-a08cfd14444f": (
            "current-path external LangSmith delivery verification"),
    }
    by_reference = accepted_records_by_reference()
    for reference, classification in expected.items():
        assert by_reference[reference].accepted_classification == classification
    run_4 = CURATED_RUN_4
    assert run_4.accepted_classification == (
        "Authorized current-path real-local verification")
    assert run_4.reference_id is None
    assert "27eaee5b" not in repr(run_4)
    assert run_4.service_read_confirmed is False
    assert by_reference[
        "01a166fa-1c8d-7b40-9686-a08cfd14444f"
    ].service_read_confirmed is True
    operational = [
        record
        for record in CURATED_HISTORICAL_RECORDS
        if record.operational_classification is not None
    ]
    assert len(operational) == 1
    assert (
        operational[0].operational_classification == OPERATIONAL_CLASSIFICATION
    )
    assert operational[0].accepted_classification == OPERATIONAL_CLASSIFICATION


def test_i_run3_dual_fact_is_independent_and_unstrengthened():
    """Run 3 keeps real-local provenance and out-of-policy classification."""
    record = accepted_records_by_reference()[
        "612ab93b-368f-4775-af2b-ec2338c48bf6"
    ]
    assert record.provenance is PresentationProvenance.LOCAL_PROVIDER_EXECUTION
    assert record.accepted_classification == "out_of_policy_observation"
    assert record.delivery_confirmation is None
    assert record.service_read_confirmed is False
    authoritative_record = record
    assert authoritative_record.accepted_classification == "out_of_policy_observation"
    assert accepted_records_by_reference() is not None


def test_j_service_read_and_accepted_only_stay_distinct():
    """An accepted-only write carries no service read-back fact."""
    record = HistoricalEvidence(
        execution_kind=ExecutionKind.CANONICAL_REAL_LOCAL,
        provenance=PresentationProvenance.LOCAL_PROVIDER_EXECUTION,
        delivery_confirmation=DeliveryConfirmation.ACCEPTED_ONLY,
        accepted_classification="accepted-only recorded state",
    )
    assert (
        DeliveryConfirmation.SERVICE_READ.value
        != DeliveryConfirmation.ACCEPTED_ONLY.value
    )
    assert record.wrote_externally is True
    assert record.service_read_confirmed is False


def test_k_unverified_write_never_implies_service_read():
    """The committed live-family vocabulary stays weaker, by construction."""
    from_run5 = accepted_records_by_reference()[
        "e48944ac-1e67-4562-b6e7-e3cab5abbb4c"
    ]
    assert from_run5.delivery_confirmation is DeliveryConfirmation.UNVERIFIED_WRITE
    assert from_run5.service_read_confirmed is False
    assert from_run5.wrote_externally is True
    fresh = EvidenceView(
        execution_kind=ExecutionKind.CANONICAL_LIVE_DEMO,
        provenance=PresentationProvenance.SYNTHETIC_OFFLINE,
    )
    assert fresh.service_read_confirmed is False


def test_l_not_sent_does_not_imply_delivery():
    """No external write or confirmation can follow from not_sent."""
    view = EvidenceView(
        execution_kind=ExecutionKind.CANONICAL_LIVE_DEMO,
        provenance=PresentationProvenance.SYNTHETIC_OFFLINE,
        delivery_confirmation=DeliveryConfirmation.NOT_SENT,
    )
    assert view.wrote_externally is False
    assert view.service_read_confirmed is False


def test_m_synthetic_transport_is_not_a_producible_cockpit_state():
    """Injected-transport delivery evidence is intentionally excluded."""
    values = {value for kind in (DeliveryConfirmation,) for value in kind.__members__}
    assert "synthetic_transport" not in values
    assert "synthetic_transport" not in cockpit_view.__all__
    assert "never produces or presents injected-transport evidence" in (
        cockpit_view.__doc__)


def test_n_operations_state_constructs_without_any_request():
    """Activation state is data only; default is not activated."""
    activation = OperationsActivation()
    assert activation.state is OperationsState.NOT_ACTIVATED
    assert not any(
        name in vars(activation) or hasattr(type(activation), name)
        for name in ("request", "fetch", "probe", "deliver", "urlopen")
    )
    requested = OperationsActivation(state=OperationsState.QUERY_REQUESTED)
    assert requested.state is OperationsState.QUERY_REQUESTED


def test_o_import_and_construction_have_no_side_effect_stacks():
    """A fresh interpreter import pulls no network/SDK provider stack."""
    script = (
        "import sys\n"
        "from multi_agent_orchestration import cockpit_view\n"
        "banned = ('httpx', 'requests', 'langsmith', 'prometheus',\n"
        "          'streamlit', 'live_contracts', 'live_langsmith',\n"
        "          'telemetry_delivery', 'telemetry')\n"
        "roots = {name.split('.')[0] for name in sys.modules}\n"
        "hits = roots & set(banned) | {name for name in banned if name in\n"
        "                                      sys.modules}\n"
        "assert not hits, sorted(hits)\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=120
    )
    assert done.returncode == 0, done.stderr[-2000:]


def test_p_local_and_deployed_live_postures_are_separate():
    """B1: local/deployed postures availability semantics, truthfully."""
    default_state = DEFAULT_COCKPIT_STATE
    assert default_state[0] is CockpitMode.DEMO
    default = default_state[1]
    assert default.local_live_available is False
    assert default.deployed_public_live_available is False

    local_only = LiveCapability(local_trusted_operator_runtime=True)
    assert local_only.local_live_available is True
    assert local_only.deployed_public_live_available is False

    boundary_only = LiveCapability(
        deployment_compatible_authority_verified=True)
    assert boundary_only.local_live_available is False
    # S5 follow-up: a verified flag alone is not an authority boundary.
    assert boundary_only.deployed_public_live_available is False

    both = LiveCapability(
        local_trusted_operator_runtime=True,
        deployment_compatible_authority_verified=True,
    )
    assert both.local_live_available is True
    assert both.deployed_public_live_available is False  # No accepted public boundary

    for capability in (default, local_only, boundary_only, both):
        assert not hasattr(capability, "credential")
        assert "credential" not in type(capability).model_fields
        vars_snapshot = vars(capability)
        assert "credential" not in vars_snapshot
        assert "api_key" not in repr(capability)


def test_q_presentation_state_cannot_authorize_execution():
    """No cockpit contract can construct or produce authority."""
    assert "LiveAuthorization" not in vars(cockpit_view)
    assert not any(
        isinstance(value, type) and "Authorization" in value.__name__
        for value in vars(cockpit_view).values()
    )
    forbidden_modules = {
        "multi_agent_orchestration.live_contracts",
        "multi_agent_orchestration.live_langsmith",
        "multi_agent_orchestration.langsmith_delivery",
        "multi_agent_orchestration.telemetry_delivery",
    }
    imported = {
        module.__name__
        for module in vars(cockpit_view).values()
        if isinstance(module, type(type))
    }
    assert not (imported & forbidden_modules)


def test_r_guidance_carries_required_distinctions_without_overclaims():
    """Guidance explains boundaries and never states forbidden claims."""
    titles = {section.title for section in GUIDANCE_SECTIONS}
    assert len(titles) == len(GUIDANCE_SECTIONS)
    text = "\n".join(
        f"{section.title}\n{section.body}" for section in GUIDANCE_SECTIONS
    ).lower()
    for required in (
        "deterministic demo", "no model inference", "no credentials",
        "fresh explicit authorization", "credential presence alone never",
        "recorded/historical", "never presented as a fresh execution",
        "loopback of the host running the app", "unreachable local stack",
        "langsmith", "no iframe", "prometheus", "grafana", "opentelemetry"
    ):
        assert required in text or required.replace(" ", "") in text, required
    for forbidden in (
        "production ready", "production-ready", "meets an sla",
        "becomes authorized", "deployed to production",
    ):
        assert forbidden not in text, forbidden


def test_s_invalid_combinations_fail_with_sanitized_deterministic_errors():
    """Rejected combinations raise the same closed error every time."""
    marker = "unique-inert-marker-9f8e7"
    with pytest.raises(ValidationError) as first:
        EvidenceView(
            execution_kind=ExecutionKind.UNAVAILABLE,
            delivery_confirmation=DeliveryConfirmation.SERVICE_READ,
            reference_id=marker,
        )
    with pytest.raises(ValidationError) as second:
        EvidenceView(
            execution_kind=ExecutionKind.UNAVAILABLE,
            delivery_confirmation=DeliveryConfirmation.SERVICE_READ,
            reference_id="different marker",
        )
    assert str(first.value) == str(second.value)
    assert marker not in str(first.value)
    with pytest.raises(ValidationError):
        HistoricalEvidence(
            execution_kind=ExecutionKind.CANONICAL_REAL_LOCAL,
            provenance=PresentationProvenance.LOCAL_PROVIDER_EXECUTION,
            operational_classification="hosted production telemetry verification",
            accepted_classification="anything",
        )
    with pytest.raises(ValidationError):
        GuidanceSection(title="", body="x")
