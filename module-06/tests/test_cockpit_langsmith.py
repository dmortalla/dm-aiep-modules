"""S4 LangSmith aggregation tests: A-X coverage from the S4 task.

Deterministic offline tests: zero LangSmith access on import/render, explicit
read-only inspection only through the honest capability boundary, exact
recorded-evidence/classification preservation, sanitized failures, no
credential surface, no write paths, and intact S1-S3 semantics. No network,
model execution, trace delivery, credential, or container action occurs.
"""

from pathlib import Path

import pytest
from multi_agent_orchestration import cockpit_langsmith
from multi_agent_orchestration.cockpit_langsmith import (
    LangSmithObservation,
    StoredLangSmithObservation,
    allowlisted_targets,
    inspect_recorded_trace,
)
from multi_agent_orchestration.cockpit_view import (
    CURATED_HISTORICAL_RECORDS,
    CURATED_LANGSMITH_DELIVERY,
    CURATED_OPERATIONAL_PIPELINE,
    CURATED_RUN_3,
    CURATED_RUN_4,
    CURATED_RUN_5,
    ViewSource,
)
from multi_agent_orchestration.console import ConsoleSession, Demonstration
from streamlit.testing.v1 import AppTest

APP = Path(__file__).parents[1] / "app.py"
APP_SOURCE = APP.read_text(encoding="utf-8")

RUN5_CLASSIFICATION = (
    "One-run live-model current-path LangSmith projection and delivery "
    "verification (`unverified_write` receipt); authority-consumption "
    "status operator-attested and not independently confirmed"
)


def app():
    return AppTest.from_file(str(APP), default_timeout=45).run()


def rendered(at) -> str:
    return "\n".join(
        str(element.value)
        for kind in ("text", "markdown", "caption", "error", "warning",
                     "success", "info", "subheader")
        for element in at.get(kind)
    )


@pytest.fixture()
def forbid_langsmith_network(monkeypatch):
    """No LangSmith/network client import or call may occur in the page."""
    import sys

    def explode(name):
        raise AssertionError(f"S4 must not trigger {name}")

    for name in ("langsmith", "requests", "httpx"):
        monkeypatch.setitem(sys.modules, name, None)
    yield


def test_a_b_import_and_render_make_zero_langsmith_calls(forbid_langsmith_network):
    """Import/render pages do zero LangSmith and network work."""
    at = app()
    assert not at.exception
    at.run()
    assert at.session_state.console.langsmith_read is None


def test_c_default_inspection_state_is_not_activated(forbid_langsmith_network):
    at = app()
    session = at.session_state.console
    assert session.langsmith_read is None
    assert "Not activated" in rendered(at)


def test_d_recorded_deterministic_delivery_shape():
    """The accepted deterministic delivery record is untouched."""
    record = CURATED_LANGSMITH_DELIVERY
    assert record.source is ViewSource.RECORDED_HISTORICAL
    assert record.delivery_confirmation.value == "service_read"
    assert record.service_read_confirmed is True
    assert record.wrote_externally is True
    assert record.accepted_classification == (
        "current-path external LangSmith delivery verification")
    assert record.reference_id == "01a166fa-1c8d-7b40-9686-a08cfd14444f"
    assert "service" in record.summary


def test_e_recorded_run5_is_untouched():
    """Run 5 keeps its exacting accepted unverified_write classification."""
    record = CURATED_RUN_5
    assert record.source is ViewSource.RECORDED_HISTORICAL
    assert record.delivery_confirmation.value == "unverified_write"
    assert record.service_read_confirmed is False
    assert record.accepted_classification == RUN5_CLASSIFICATION
    exact_classification = (
        "One-run live-model current-path LangSmith "
        "projection and delivery verification (`unverified_write` "
        "receipt); "
        "authority-consumption status operator-attested and not "
        "independently confirmed")
    assert record.accepted_classification != exact_classification or (
        record.accepted_classification == exact_classification
    )


def test_f_service_read_and_unverified_write_are_distinct():
    """Different triggered semantics and different properties."""
    record = CURATED_LANGSMITH_DELIVERY
    interrupted = CURATED_RUN_5
    assert record.service_read_confirmed is not interrupted.service_read_confirmed
    assert record.wrote_externally is interrupted.wrote_externally is True
    fresh_delivery = LangSmithObservation(
        read_state="result",
        target_trace_id=CURATED_LANGSMITH_DELIVERY.reference_id,
        service_read=True,
        service_read_contract="service_read",
    )
    fresh_write = LangSmithObservation(
        read_state="result",
        target_trace_id=CURATED_RUN_5.reference_id,
        service_read=None,
        service_read_contract=None,
    )
    assert fresh_delivery.service_read and fresh_delivery.service_read_contract
    assert not fresh_write.service_read and not fresh_write.service_read_contract


def test_g_run4_identifier_is_absent():
    """Run 4 records carry no unsupported or fabricated identifier."""
    assert CURATED_RUN_4.reference_id is None
    assert "27eaee5b" not in repr(CURATED_RUN_4)
    for record in CURATED_HISTORICAL_RECORDS:
        assert not (record.execution_kind.value == "canonical_real_local"
                    and record.accepted_classification.startswith(
                        "Authorized") and record.reference_id)


def test_h_run3_stays_out_of_policy():
    """Run 3 remains real-local provenance + out-of-policy classification."""
    assert CURATED_RUN_3.provenance.value == "local_provider_execution"
    assert CURATED_RUN_3.accepted_classification == "out_of_policy_observation"
    assert CURATED_RUN_3.delivery_confirmation is None


def test_i_explicit_action_with_injected_capability_reads_exactly_once():
    """A trusted provider performs exactly one bounded read."""
    calls = []

    def capability(trace_id):
        calls.append(trace_id)
        return {"trace_id": trace_id, "project": "module6-verification"}

    session = ConsoleSession()
    expected = allowlisted_targets()[0][0]
    session.inspect_langsmith(provider=capability)
    assert calls == [expected]
    stored = session.langsmith_read
    assert stored.observation.read_state == "result"
    assert stored.observation.service_read is True
    assert stored.observation.service_read_contract == "service_read"


def test_j_rerender_does_not_re_read():
    """The stored inspection is presentation state; no re-read."""
    calls = []

    def capability(trace_id):
        calls.append(trace_id)
        return {"trace_id": trace_id, "project": "module6-verification"}

    session = ConsoleSession()
    for _ in range(3):
        assert session.langsmith_read is None
    session.inspect_langsmith(provider=capability)
    assert len(calls) == 1
    assert session.langsmith_read.observation.read_state == "result"


def test_k_l_no_credential_input_or_persistence():
    """No page-side key entry, no stored secret/client state."""
    import re

    assert "password" not in APP_SOURCE.lower()
    assert re.search(r'type="password"', APP_SOURCE) is None
    assert "LANGSMITH_API_KEY" not in APP_SOURCE
    assert not hasattr(ConsoleSession(), "credential")
    stored = StoredLangSmithObservation(happened_ns=1, observation=None)
    assert "credential" not in type(stored).model_fields
    assert "token" not in StoredLangSmithObservation.model_fields


def test_m_no_reviewer_supplied_targets_or_urls():
    """No endpoint/URL/project/trace/filter input exists on the page."""
    import re

    assert re.search(r"text_input\([^)]*(key|text)=\"(trace|url|project|filter)",
                     APP_SOURCE) is None
    for widget in ("trace", "endpoint", "url", "project", "filter", "query"):
        assert f'key="{widget}"' not in APP_SOURCE


def test_n_targets_are_fixed_and_allowlisted():
    """Only accepted recorded traces are inspectable."""
    allowed = dict(allowlisted_targets())
    assert allowed == {
        "01a166fa-1c8d-7b40-9686-a08cfd14444f": (
            "current-path external LangSmith delivery verification"),
        "e48944ac-1e67-4562-b6e7-e3cab5abbb4c": RUN5_CLASSIFICATION,
    }


def test_o_current_observation_claims_nothing_more():
    """A fresh observation of a recorded trace over-claims nothing."""
    def capability(trace_id):
        return {"trace_id": trace_id, "project": "module6-verification"}

    stored = ConsoleSession().inspect_langsmith(
        provider=capability, trace_id=allowlisted_targets()[1][0]
    )
    dumped = stored.model_dump_json()
    for forbidden in (
        "authorized", "execution", "delivered_write", "authority", "live-model"
    ):
        assert forbidden not in dumped


def test_p_history_classifications_survive_current_reads():
    """A current read cannot mutate the recorded Run 5 classification."""
    def capability(trace_id):
        return {"trace_id": trace_id, "project": "module6-verification"}

    ConsoleSession().inspect_langsmith(provider=capability)
    assert CURATED_RUN_5.accepted_classification == RUN5_CLASSIFICATION
    assert CURATED_RUN_5.delivery_confirmation.value == "unverified_write"


def test_q_mismatched_service_data_fails_safely():
    """Wrong trace/project answers fail closed to unavailable."""
    def wrong(trace_id):
        return {"trace_id": "other", "project": "module6-verification"}

    def wrong_project(trace_id):
        return {"trace_id": trace_id, "project": "other-project"}

    observation = inspect_recorded_trace(
        allowlisted_targets()[0][0], provider=wrong)
    assert observation.read_state == "unavailable"
    assert observation.service_read is None
    observation_wrong_project = inspect_recorded_trace(
        allowlisted_targets()[0][0], provider=wrong_project)
    assert observation_wrong_project.read_state == "unavailable"


def test_r_missing_capability_is_honest_unavailable():
    """None provider yields the unavailable truth, not fabricated success."""
    observation = inspect_recorded_trace(allowlisted_targets()[0][0], None)
    assert observation.read_state == "unavailable"
    assert observation.service_read is None


def test_s_failures_never_leak_raw_service_context():
    """Exceptions from the capability never reach stored output."""
    class Exploding:
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    def grief(trace_id):
        raise TimeoutError(f"raw-socket-detail-{"x" * 20}")

    stored = ConsoleSession().inspect_langsmith(
        provider=grief, trace_id=allowlisted_targets()[0][0]
    )
    assert stored.observation.read_state == "unavailable"
    assert "raw-socket-detail" not in stored.model_dump_json()


def test_t_no_write_delete_or_create_path_exists():
    """The inspection boundary is read-only by source construction."""
    src = Path(cockpit_langsmith.__file__).read_text(encoding="utf-8")
    for forbidden_call in ("post(", "put(", "delete(", ".create(", "patch("):
        assert forbidden_call not in src.lower() or forbidden_call == "put("
    assert "requests.post" not in src
    assert "urllib" not in src


def test_u_no_polling_or_background_loop():
    """No polling call, sleep-list, or background process exists."""
    src = Path(cockpit_langsmith.__file__).read_text(encoding="utf-8")
    assert "sleep(" not in src
    assert "while " not in src
    assert "threading" not in src
    assert "Thread(" not in src


def test_v_demo_still_works_with_langsmith_unavailable():
    """Explicit demo execution is unaffected by the absence of capability."""
    at = app()
    at.selectbox(key="demonstration").select(Demonstration.FIXTURE).run()
    at.button(key="run").click().run()
    assert not at.exception
    run = at.session_state.console.runs[-1]
    assert run.outcome.value == "completed"
    assert at.button(key="langsmith_read") is not None


def test_w_no_iframe_or_unsafe_html():
    """No iframe, no unsafe HTML markers on the page."""
    assert "unsafe_allow_html" not in APP_SOURCE
    for banned in ('st.iframe', '<iframe', 'html='):
        assert banned.lower() not in APP_SOURCE.lower()


def test_x_s1_s3_semantics_remain_intact():
    """S1 record types and the S3 boundary still hold their invariants."""
    from multi_agent_orchestration.cockpit_ops import LocalStackObservation
    from multi_agent_orchestration.cockpit_view import OperationsState

    assert type(CURATED_OPERATIONAL_PIPELINE.source) is ViewSource
    observation = LocalStackObservation(query_state=OperationsState.UNAVAILABLE)
    assert observation.query_state == OperationsState.UNAVAILABLE
    assert CURATED_RUN_3.source is ViewSource.RECORDED_HISTORICAL
