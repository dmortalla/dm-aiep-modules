"""Explicitly gated live-provider evidence tests for Module 5.

Normal test execution remains zero-network and zero-cost. A live provider test
can execute only when RUN_LIVE_LLM_TESTS=1 and that provider's credential is
present. OpenAI and Anthropic eligibility is intentionally independent.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType

import pytest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
LIVE_OPT_IN = "RUN_LIVE_LLM_TESTS"
OPENAI_CREDENTIAL = "OPENAI_API_KEY"
ANTHROPIC_CREDENTIAL = "ANTHROPIC_API_KEY"


def live_provider_eligible(
    credential_name: str,
    *,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Return whether one provider is explicitly eligible for live verification.

    Args:
        credential_name: Environment-variable name for the provider credential.
        environ: Environment mapping to inspect. Defaults to the process environment.

    Returns:
        True only when live testing is explicitly enabled and the selected
        provider credential is non-empty.
    """
    environment = os.environ if environ is None else environ
    return (
        environment.get(LIVE_OPT_IN) == "1"
        and bool(environment.get(credential_name, "").strip())
    )


def _load_app() -> ModuleType:
    """Load the Module 5 Streamlit application only after live eligibility passes."""
    spec = importlib.util.spec_from_file_location(
        "module_05_live_provider_evidence_app",
        APP_PATH,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_live_gate_requires_explicit_opt_in() -> None:
    """Credential presence alone must never authorize live execution."""
    environment = {OPENAI_CREDENTIAL: "present-but-unused"}

    assert not live_provider_eligible(OPENAI_CREDENTIAL, environ=environment)


def test_live_gate_rejects_disabled_opt_in() -> None:
    """Only the exact application-owned opt-in value enables live eligibility."""
    environment = {
        LIVE_OPT_IN: "0",
        OPENAI_CREDENTIAL: "present-but-unused",
    }

    assert not live_provider_eligible(OPENAI_CREDENTIAL, environ=environment)


def test_live_gate_requires_selected_provider_credential() -> None:
    """Opt-in without the selected provider credential remains ineligible."""
    environment = {LIVE_OPT_IN: "1"}

    assert not live_provider_eligible(OPENAI_CREDENTIAL, environ=environment)
    assert not live_provider_eligible(ANTHROPIC_CREDENTIAL, environ=environment)


def test_provider_live_eligibility_is_independent() -> None:
    """One credential must not authorize the other provider path."""
    openai_only = {
        LIVE_OPT_IN: "1",
        OPENAI_CREDENTIAL: "present-but-unused",
    }
    anthropic_only = {
        LIVE_OPT_IN: "1",
        ANTHROPIC_CREDENTIAL: "present-but-unused",
    }

    assert live_provider_eligible(OPENAI_CREDENTIAL, environ=openai_only)
    assert not live_provider_eligible(ANTHROPIC_CREDENTIAL, environ=openai_only)
    assert live_provider_eligible(ANTHROPIC_CREDENTIAL, environ=anthropic_only)
    assert not live_provider_eligible(OPENAI_CREDENTIAL, environ=anthropic_only)


def test_blank_provider_credential_is_ineligible() -> None:
    """Whitespace-only credential material cannot authorize a live test."""
    environment = {
        LIVE_OPT_IN: "1",
        OPENAI_CREDENTIAL: "   ",
    }

    assert not live_provider_eligible(OPENAI_CREDENTIAL, environ=environment)


@pytest.mark.skipif(
    not live_provider_eligible(OPENAI_CREDENTIAL),
    reason="OpenAI live verification requires explicit opt-in and credential.",
)
def test_openai_live_provider_evidence() -> None:
    """Verify one genuine bounded OpenAI workflow through ToolRegistry."""
    app = _load_app()
    credential = os.environ[OPENAI_CREDENTIAL]

    demo = app.run_openai_live(
        "Use the calculator tool to calculate 6 times 7. Return the result.",
        api_key=credential,
    )

    assert demo.error is None
    assert demo.output_text.strip()
    assert "calculator" in demo.executed
    assert "LIVE OpenAI evidence" in demo.evidence


@pytest.mark.skipif(
    not live_provider_eligible(ANTHROPIC_CREDENTIAL),
    reason="Anthropic live verification requires explicit opt-in and credential.",
)
def test_anthropic_live_provider_evidence() -> None:
    """Verify one genuine bounded Anthropic workflow through ToolRegistry."""
    app = _load_app()
    credential = os.environ[ANTHROPIC_CREDENTIAL]

    demo = app.run_anthropic_live(
        "Use the calculator tool to calculate 6 times 7. Return the result.",
        api_key=credential,
    )

    assert demo.error is None
    assert demo.output_text.strip()
    assert "calculator" in demo.executed
    assert "LIVE Anthropic evidence" in demo.evidence
