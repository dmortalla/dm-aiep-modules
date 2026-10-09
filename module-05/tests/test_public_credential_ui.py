"""PR-01 tests for Module 5 public session-only provider credentials."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

MODULE_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = MODULE_ROOT / "app.py"


def _load_app():
    """Load the Streamlit module without importing another academic module."""
    spec = importlib.util.spec_from_file_location("module05_pr01_app", APP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def page() -> AppTest:
    """Return the Module 5 Streamlit application test harness."""
    return AppTest.from_file(str(APP_PATH)).run(timeout=30)


def test_public_ui_is_session_only() -> None:
    """The public application exposes no persistence or OS credential path."""
    source = APP_PATH.read_text(encoding="utf-8-sig")

    forbidden = (
        "save_local_credentials",
        "read_local_credential(",
        "read_local_credential_names",
        "remove_local_credentials",
        "delete_local_env",
        "read_os_credential",
        "os.environ",
        "getenv",
        "dotenv",
        "Save entered keys locally",
        "Authorize stored",
        "Authorize OS",
        "Delete local .env",
    )

    for value in forbidden:
        assert value not in source


def test_public_ui_has_masked_session_controls() -> None:
    """The UI exposes explicit masked authorization and clearing controls."""
    source = APP_PATH.read_text(encoding="utf-8-sig")

    assert "Authorize entered keys for this session" in source
    assert "Clear all session credentials" in source
    assert "authorized_session_key" in source
    assert 'type="password"' in source
    assert "Security reminder:" in source


def test_provider_choices_are_application_allowlisted() -> None:
    """Only approved providers receive credential slots."""
    app = _load_app()

    assert tuple(app.PROVIDER_CREDENTIALS) == ("OpenAI", "Anthropic")
    assert (
        app.PROVIDER_CREDENTIALS["OpenAI"]["session_authorized_key"]
        == "authorized_openai_api_key"
    )
    assert (
        app.PROVIDER_CREDENTIALS["Anthropic"]["session_authorized_key"]
        == "authorized_anthropic_api_key"
    )


def test_unknown_provider_has_no_credential_authority() -> None:
    """Untrusted provider names cannot select arbitrary credential state."""
    app = _load_app()

    with pytest.raises(ValueError, match="Unsupported provider"):
        app.authorized_session_key("shell")


def test_zero_key_startup(page: AppTest) -> None:
    """The public application starts without authorized provider credentials."""
    assert not page.exception
    assert "authorized_openai_api_key" not in page.session_state
    assert "authorized_anthropic_api_key" not in page.session_state


def test_entering_key_without_authorization_does_not_authorize(
    page: AppTest,
) -> None:
    """Typing a credential alone does not grant provider authority."""
    page.text_input(key="credential_openai").input("sk-test-secret").run()

    assert "authorized_openai_api_key" not in page.session_state


def test_explicit_authorization_is_session_scoped(page: AppTest) -> None:
    """Authorization moves only entered values into session authority."""
    page.text_input(key="credential_openai").input("sk-test-secret").run()
    page.button(key="authorize_session_credentials").click().run()

    assert not page.exception
    assert page.session_state["authorized_openai_api_key"] == "sk-test-secret"
    assert "authorized_anthropic_api_key" not in page.session_state
    assert page.session_state["credential_openai"] == ""


def test_clear_removes_all_authorized_credentials(page: AppTest) -> None:
    """The explicit clear action removes all provider credentials."""
    page.text_input(key="credential_openai").input("sk-openai-secret")
    page.text_input(key="credential_anthropic").input("sk-ant-secret").run()
    page.button(key="authorize_session_credentials").click().run()

    assert page.session_state["authorized_openai_api_key"] == "sk-openai-secret"
    assert page.session_state["authorized_anthropic_api_key"] == "sk-ant-secret"

    page.button(key="clear_session_credentials").click().run()

    assert "authorized_openai_api_key" not in page.session_state
    assert "authorized_anthropic_api_key" not in page.session_state


def test_pr01_does_not_connect_credentials_to_provider_calls() -> None:
    """PR-01 authorization must not itself enable billable provider execution."""
    source = APP_PATH.read_text(encoding="utf-8-sig")

    assert "run_openai_demo(goal, api_key=" not in source
    assert "run_anthropic_demo(goal, api_key=" not in source


def test_public_ui_does_not_render_full_authorized_key(page: AppTest) -> None:
    """Credential material does not appear in ordinary rendered text."""
    secret = "sk-super-secret-pr01-value"
    page.text_input(key="credential_openai").input(secret).run()
    page.button(key="authorize_session_credentials").click().run()

    rendered: list[str] = []
    for collection_name in (
        "text",
        "caption",
        "info",
        "warning",
        "success",
        "error",
        "markdown",
    ):
        for element in getattr(page, collection_name):
            rendered.append(str(element.value))

    assert secret not in "\n".join(rendered)
