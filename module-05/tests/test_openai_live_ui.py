"""PR-02 tests for explicit, bounded, zero-implicit-call OpenAI live execution."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

MODULE_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = MODULE_ROOT / "app.py"


def _load_app():
    """Load the Module 5 Streamlit application for isolated unit tests."""
    spec = importlib.util.spec_from_file_location("module05_pr02_app", APP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_live_openai_policy_is_bounded() -> None:
    """The live path must use conservative application-owned limits."""
    app = _load_app()

    assert app.OPENAI_LIVE_MAX_REQUESTS == 3
    assert app.OPENAI_LIVE_MAX_TOOL_CALLS == 4
    assert app.OPENAI_LIVE_TIMEOUT_SECONDS == 20.0
    assert app.OPENAI_LIVE_MODEL == "gpt-5.6-terra"


def test_live_openai_rejects_missing_credential() -> None:
    """No credential means no client construction and therefore no live call."""
    app = _load_app()

    with pytest.raises(ValueError, match="authorized session credential"):
        app.run_openai_live("Calculate 6 times 7", api_key="")


def test_live_openai_constructs_client_only_inside_explicit_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The explicit runner supplies the session key without persisting it."""
    app = _load_app()
    captured: dict[str, Any] = {}
    secret = "sk-pr02-secret-never-display"

    class FakeOpenAI:
        """Capture constructor arguments without network access."""

        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    def fake_run(
        client: Any,
        registry: Any,
        *,
        model: str,
        user_input: str,
        max_requests: int,
        max_tool_calls: int,
    ) -> SimpleNamespace:
        captured["client"] = client
        captured["registry"] = registry
        captured["model"] = model
        captured["user_input"] = user_input
        captured["max_requests"] = max_requests
        captured["max_tool_calls"] = max_tool_calls
        return SimpleNamespace(output_text="live-path-test-result")

    monkeypatch.setattr(app, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(app, "run_openai_function_calling", fake_run)

    result = app.run_openai_live("Calculate 6 times 7", api_key=secret)

    assert captured["api_key"] == secret
    assert captured["max_retries"] == 0
    assert captured["timeout"] == app.OPENAI_LIVE_TIMEOUT_SECONDS
    assert captured["model"] == app.OPENAI_LIVE_MODEL
    assert captured["max_requests"] == app.OPENAI_LIVE_MAX_REQUESTS
    assert captured["max_tool_calls"] == app.OPENAI_LIVE_MAX_TOOL_CALLS
    assert result.output_text == "live-path-test-result"
    assert result.error is None
    assert result.evidence.startswith("LIVE OpenAI evidence:")
    assert "completed successfully" in result.evidence
    assert secret not in repr(result)


def test_live_openai_uses_application_owned_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The live provider receives the existing allowlisted ToolRegistry."""
    app = _load_app()
    observed: dict[str, Any] = {}

    class FakeOpenAI:
        """Network-free OpenAI constructor stand-in."""

        def __init__(self, **kwargs: Any) -> None:
            observed["client_kwargs"] = kwargs

    def fake_run(
        client: Any,
        registry: Any,
        **kwargs: Any,
    ) -> SimpleNamespace:
        observed["registry"] = registry
        observed["tools"] = tuple(app.response_tools(registry))
        return SimpleNamespace(output_text="ok")

    monkeypatch.setattr(app, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(app, "run_openai_function_calling", fake_run)

    result = app.run_openai_live("Calculate 6 times 7", api_key="sk-test")

    assert result.output_text == "ok"
    assert observed["tools"]
    tool_names = {tool["name"] for tool in observed["tools"]}
    assert "shell" not in tool_names


def test_live_openai_sanitizes_remote_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider exceptions must not reflect secrets or remote detail."""
    app = _load_app()
    secret = "sk-secret-that-must-not-leak"
    provider_detail = "remote-provider-sensitive-detail"

    class FakeOpenAI:
        """Network-free client constructor."""

        def __init__(self, **kwargs: Any) -> None:
            pass

    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError(f"{provider_detail}: {secret}")

    monkeypatch.setattr(app, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(app, "run_openai_function_calling", fail)

    result = app.run_openai_live("Calculate 6 times 7", api_key=secret)

    assert result.error is not None
    assert "RuntimeError" in result.error
    assert secret not in result.error
    assert provider_detail not in result.error
    assert not result.evidence.startswith("LIVE OpenAI evidence:")
    assert "not yet been established" in result.evidence


def test_streamlit_zero_key_state_disables_live_openai() -> None:
    """Public startup must disable live execution without authorization."""
    page = AppTest.from_file(str(APP_PATH)).run(timeout=30)

    live_button = next(
        button
        for button in page.button
        if button.label == "Run OpenAI LIVE - may incur cost"
    )

    assert live_button.disabled is True
    assert "authorized_openai_api_key" not in page.session_state


def test_source_requires_explicit_live_button() -> None:
    """Startup and credential authorization must not invoke the live runner."""
    source = APP_PATH.read_text(encoding="utf-8-sig")

    assert 'key="run_openai_live"' in source
    assert "Run OpenAI LIVE - may incur cost" in source
    assert "run_openai_live(" in source
    assert "OpenAI(" in source
    assert "max_retries=0" in source
    assert "timeout=OPENAI_LIVE_TIMEOUT_SECONDS" in source


def test_live_path_does_not_persist_or_log_credentials() -> None:
    """PR-02 must preserve PR-01's session-only credential boundary."""
    source = APP_PATH.read_text(encoding="utf-8-sig")

    forbidden = (
        "os.environ",
        "getenv",
        "dotenv",
        "write_text(api_key",
        "write_bytes(api_key",
        "print(api_key",
        "logger.info(api_key",
        "logger.debug(api_key",
    )

    for value in forbidden:
        assert value not in source

def test_integration_error_rendering_distinguishes_pre_and_post_tool_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UI failure evidence must not falsely claim that zero tools executed."""
    app = _load_app()
    messages: list[str] = []

    monkeypatch.setattr(app.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.st, "code", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.st, "json", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.st, "text", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.st, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        app.st,
        "error",
        lambda message, **kwargs: messages.append(message),
    )

    class NullExpander:
        """Minimal context manager for rendering tests."""

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(
        app.st,
        "expander",
        lambda *args, **kwargs: NullExpander(),
    )

    before_tool = app.IntegrationDemo(
        integration="OpenAI Function Calling - LIVE",
        evidence="attempted",
        tools_sent=[],
        requests=[],
        executed=[],
        error="RuntimeError: live OpenAI request failed safely.",
    )
    app._render_integration_result(before_tool)
    assert messages[-1] == "Execution stopped safely before any tool ran."

    after_tool = app.IntegrationDemo(
        integration="OpenAI Function Calling - LIVE",
        evidence="attempted",
        tools_sent=[],
        requests=[],
        executed=["calculator"],
        error="RuntimeError: live OpenAI request failed safely.",
    )
    app._render_integration_result(after_tool)
    assert "after one or more allowlisted tools ran" in messages[-1]
