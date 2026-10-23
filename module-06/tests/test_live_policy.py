"""ADR-008 NORMAL real-local budget profile pins and authority separation.

These tests lock the human-approved named budget profile in
``multi_agent_orchestration.live_policy`` and prove that policy configuration
stays strictly separate from execution authority: the profile is exact
``LiveBudget`` data, alone authorizes nothing, induces no import side effects,
is consumed by no execution path and does not couple to the synthetic console
authority.
"""

import ast
import importlib
import subprocess
import sys
from pathlib import Path

import pytest
from multi_agent_orchestration import live_policy
from multi_agent_orchestration.live_contracts import (
    MAX_DEADLINE_MS,
    MAX_INPUT_CHARS,
    MAX_OUTPUT_TOKENS,
    MAX_REPAIR_ATTEMPTS,
    MAX_REPLY_BYTES,
    PLANNED_MODEL_CALLS,
    LiveAuthorization,
    LiveBudget,
    LiveFailureCategory,
    require_live_authorization,
)
from multi_agent_orchestration.live_errors import LiveExecutionError

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "src" / "multi_agent_orchestration"
ENTRY_SCRIPTS = (
    "app.py",
    "run_console.py",
    "run_benchmark.py",
    "run_langsmith.py",
    "run_telemetry.py",
)


def test_normal_values_are_locked():
    """NORMAL profile values match ADR-008 exactly."""
    budget = live_policy.NORMAL_REAL_LOCAL_BUDGET
    assert isinstance(budget, LiveBudget)
    assert budget.deadline_ms == live_policy.NORMAL_REAL_LOCAL_DEADLINE_MS == 200_000
    assert (
        budget.call_timeout_ms
        == live_policy.NORMAL_REAL_LOCAL_CALL_TIMEOUT_MS
        == 45_000
    )
    assert (
        budget.max_model_calls
        == live_policy.NORMAL_REAL_LOCAL_MAX_MODEL_CALLS
        == 4
    )
    assert budget.max_repair_attempts == 1
    assert budget.max_concurrency == 1


def test_normal_content_bounds_equal_accepted_contract_ceilings():
    """Real-local content bounds are the accepted contract ceilings."""
    budget = live_policy.NORMAL_REAL_LOCAL_BUDGET
    assert budget.max_input_chars == MAX_INPUT_CHARS == 4_096
    assert budget.max_output_tokens == MAX_OUTPUT_TOKENS == 4_096
    assert budget.max_reply_bytes == MAX_REPLY_BYTES == 16_000


def test_call_accounting_structure_is_preserved():
    """Planned calls plus the repair ceiling equal the hard call total."""
    assert PLANNED_MODEL_CALLS == 3
    assert MAX_REPAIR_ATTEMPTS == 1
    budget = live_policy.NORMAL_REAL_LOCAL_BUDGET
    assert (
        budget.max_model_calls
        == PLANNED_MODEL_CALLS + budget.max_repair_attempts
        == 4
    )


def test_profile_is_inside_the_generic_schema_ceiling():
    """The NORMAL profile stays below the provisional generic ceiling."""
    assert MAX_DEADLINE_MS == 300_000
    assert live_policy.NORMAL_REAL_LOCAL_DEADLINE_MS <= MAX_DEADLINE_MS
    assert (
        live_policy.NORMAL_REAL_LOCAL_CALL_TIMEOUT_MS
        <= live_policy.NORMAL_REAL_LOCAL_DEADLINE_MS
    )


def test_structural_four_call_deadline_relationship():
    """Deadline covers four full call bounds plus the fixed allowance."""
    reference = (
        4 * live_policy.NORMAL_REAL_LOCAL_CALL_TIMEOUT_MS
        + live_policy.NORMAL_REAL_LOCAL_ALLOWANCE_MS
    )
    assert live_policy.NORMAL_REAL_LOCAL_DEADLINE_MS == reference == 200_000
    assert live_policy.NORMAL_REAL_LOCAL_ALLOWANCE_MS == 20_000


def test_profile_is_live_budget_not_live_authorization():
    """The profile carries no selection, mode or authorization identity."""
    budget = live_policy.NORMAL_REAL_LOCAL_BUDGET
    assert not isinstance(budget, LiveAuthorization)
    fields = set(type(budget).model_fields)
    assert fields == set(LiveBudget.model_fields)
    for forbidden in ("mode", "selection", "executed", "authorized"):
        assert forbidden not in fields


def test_profile_alone_cannot_authorize_execution():
    """Feeding the profile to the authority boundary is a closed refusal."""
    with pytest.raises(LiveExecutionError) as refused:
        require_live_authorization(live_policy.NORMAL_REAL_LOCAL_BUDGET)
    assert refused.value.category == LiveFailureCategory.AUTHORIZATION_REFUSED


def test_profile_import_has_no_authority_or_provider_side_effects():
    """The module exports budget data only, at import and after reimport."""
    importlib.reload(live_policy)
    profile = {
        name
        for name, value in vars(live_policy).items()
        if not name.startswith("__")
    }
    assert profile == {
        "LiveBudget",
        "NORMAL_REAL_LOCAL_ALLOWANCE_MS",
        "NORMAL_REAL_LOCAL_BUDGET",
        "NORMAL_REAL_LOCAL_CALL_TIMEOUT_MS",
        "NORMAL_REAL_LOCAL_DEADLINE_MS",
        "NORMAL_REAL_LOCAL_MAX_MODEL_CALLS",
    }
    authority = [
        value
        for value in vars(live_policy).values()
        if isinstance(value, LiveAuthorization)
    ]
    assert authority == []


def test_live_policy_import_stays_sdk_and_network_free():
    """A fresh import of the policy module imports no SDK or client stack."""
    script = (
        "import sys\n"
        "from multi_agent_orchestration import live_policy\n"
        "banned = ('openai', 'anthropic', 'google', 'litellm', 'httpx',\n"
        "          'requests', 'langchain', 'langgraph', 'langsmith',\n"
        "          'crewai', 'ollama', 'streamlit', 'dotenv')\n"
        "roots = {name.split('.')[0] for name in sys.modules}\n"
        "assert not (roots & set(banned)), sorted(roots & set(banned))\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=120
    )
    assert done.returncode == 0, done.stderr[-2000:]


def test_no_execution_path_consumes_the_real_local_profile():
    """No module in the package or console app consumes the profile."""
    offenders = []
    for path in sorted(PACKAGE_DIR.glob("*.py")):
        if path.name == "live_policy.py":
            continue
        text = path.read_text(encoding="utf-8")
        for token in (
            "live_policy",
            "NORMAL_REAL_LOCAL_BUDGET",
            "NORMAL_LIVE_BUDGET",
        ):
            if token in text:
                offenders.append(f"{path.name}:{token}")
    entry_dir = PACKAGE_DIR.parent.parent
    for name in ENTRY_SCRIPTS:
        text = (entry_dir / name).read_text(encoding="utf-8")
        for token in (
            "live_policy",
            "NORMAL_REAL_LOCAL_BUDGET",
            "NORMAL_LIVE_BUDGET",
        ):
            if token in text:
                offenders.append(f"{name}:{token}")
    assert offenders == [], offenders


def test_canonical_default_authorization_remains_absent():
    """No module-level or default LiveAuthorization exists on the API path."""
    import multi_agent_orchestration.canonical_workflow as canonical

    defaults = [
        value
        for value in vars(canonical).values()
        if isinstance(value, LiveAuthorization)
    ]
    assert defaults == []


def test_synthetic_console_authority_semantics_unchanged():
    """The synthetic path keeps its own accepted 30,000/5,000 authority."""
    tree = ast.parse((PACKAGE_DIR / "console_live.py").read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "LiveBudget"
    ]
    assert len(calls) == 1
    kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in calls[0].keywords}
    assert kwargs == {
        "max_model_calls": 4,
        "max_repair_attempts": 1,
        "max_concurrency": 1,
        "deadline_ms": 30000,
        "call_timeout_ms": 5000,
        "max_input_chars": 4096,
        "max_output_tokens": 256,
        "max_reply_bytes": 4096,
    }


def test_authorization_still_requires_exact_construction():
    """Authority needs exact data; deviation budgets are explicit, separate."""
    with pytest.raises(LiveExecutionError) as refused:
        require_live_authorization(None)
    assert refused.value.category == LiveFailureCategory.AUTHORIZATION_REFUSED

    authority = {
        "mode": "live-model",
        "selection": {
            "execution_class": "local_model_inference",
            "provider": "ollama",
            "model": "qwen2.5-coder:7b",
        },
        "budget": {
            "max_model_calls": 4,
            "max_repair_attempts": 1,
            "max_concurrency": 1,
            "deadline_ms": 100_000,
            "call_timeout_ms": 30_000,
            "max_input_chars": 4_096,
            "max_output_tokens": 4_096,
            "max_reply_bytes": 16_000,
        },
    }

    with pytest.raises(LiveExecutionError) as refused_data:
        require_live_authorization(authority)
    assert (
        refused_data.value.category
        == LiveFailureCategory.AUTHORIZATION_REFUSED
    )

    deviation = require_live_authorization(LiveAuthorization.model_validate(authority))
    assert isinstance(deviation, LiveAuthorization)
    assert deviation.budget.deadline_ms == 100_000
    assert deviation.budget != live_policy.NORMAL_REAL_LOCAL_BUDGET
