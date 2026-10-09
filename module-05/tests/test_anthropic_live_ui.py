"""Zero-network tests for Module 5 bounded Anthropic live execution."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _load_app() -> Any:
    """Load the Streamlit application as an isolated test module."""
    spec = importlib.util.spec_from_file_location(
        "module_05_anthropic_live_test_app",
        APP_PATH,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_anthropic_live_constants_are_bounded_and_application_owned() -> None:
    """Live Anthropic execution uses finite application-owned limits."""
    app = _load_app()

    assert app.ANTHROPIC_LIVE_MODEL == "claude-sonnet-5-5"
    assert app.ANTHROPIC_LIVE_MAX_REQUESTS == 3
    assert app.ANTHROPIC_LIVE_MAX_TOOL_CALLS == 4
    assert app.ANTHROPIC_LIVE_MAX_OUTPUT_TOKENS == 1024
    assert app.ANTHROPIC_LIVE_TIMEOUT_SECONDS == 20.0


def test_anthropic_live_rejects_missing_goal_or_credential() -> None:
    """A live provider cannot run without both explicit inputs."""
    app = _load_app()

    with pytest.raises(ValueError, match="non-empty goal"):
        app.run_anthropic_live(" ", api_key="session-key")

    with pytest.raises(ValueError, match="session credential"):
        app.run_anthropic_live("Use the calculator.", api_key=" ")


def test_anthropic_live_uses_sdk_and_existing_tool_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The live adapter preserves SDK and ToolRegistry boundaries."""
    app = _load_app()
    captured: dict[str, Any] = {}

    class FakeAnthropic:
        def __init__(self, **kwargs: Any) -> None:
            captured["client_kwargs"] = kwargs

    class FakeRegistry:
        def names(self) -> tuple[str, ...]:
            """Return the application-owned allowlisted tool names."""
            return ("calculator", "knowledge_lookup")

    registry = FakeRegistry()

    def fake_registry(callback: Any = None) -> FakeRegistry:
        captured["callback"] = callback
        return registry

    def fake_runner(
        client: object,
        runner_registry: object,
        **kwargs: Any,
    ) -> SimpleNamespace:
        captured["client"] = client
        captured["registry"] = runner_registry
        captured["runner_kwargs"] = kwargs
        return SimpleNamespace(output_text="Anthropic live success")

    monkeypatch.setattr(app, "Anthropic", FakeAnthropic)
    monkeypatch.setattr(app, "observed_registry", fake_registry)
    monkeypatch.setattr(app, "run_anthropic_tool_use", fake_runner)

    demo = app.run_anthropic_live(
        "Use an allowlisted tool.",
        api_key="session-only-secret",
    )

    assert captured["client_kwargs"] == {
        "api_key": "session-only-secret",
        "max_retries": 0,
        "timeout": app.ANTHROPIC_LIVE_TIMEOUT_SECONDS,
    }
    assert captured["registry"] is registry

    runner_kwargs = captured["runner_kwargs"]
    assert runner_kwargs["model"] == app.ANTHROPIC_LIVE_MODEL
    assert runner_kwargs["max_tokens"] == app.ANTHROPIC_LIVE_MAX_OUTPUT_TOKENS
    assert runner_kwargs["max_requests"] == app.ANTHROPIC_LIVE_MAX_REQUESTS
    assert runner_kwargs["max_tool_calls"] == app.ANTHROPIC_LIVE_MAX_TOOL_CALLS

    assert demo.output_text == "Anthropic live success"
    assert demo.evidence.startswith("LIVE Anthropic evidence:")
    assert "completed successfully" in demo.evidence


def test_anthropic_live_failure_does_not_create_live_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An attempted provider request is not successful LIVE evidence."""
    app = _load_app()

    class FakeAnthropic:
        def __init__(self, **kwargs: Any) -> None:
            del kwargs

    def fail_runner(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise RuntimeError("provider-secret-detail")

    monkeypatch.setattr(app, "Anthropic", FakeAnthropic)
    monkeypatch.setattr(app, "run_anthropic_tool_use", fail_runner)

    demo = app.run_anthropic_live(
        "Attempt the provider workflow.",
        api_key="do-not-leak-this-key",
    )

    assert not demo.evidence.startswith("LIVE Anthropic evidence:")
    assert "not yet been established" in demo.evidence
    assert demo.error == "RuntimeError: live Anthropic request failed safely."
    assert "provider-secret-detail" not in demo.error
    assert "do-not-leak-this-key" not in demo.error


def test_anthropic_live_source_requires_explicit_billable_action() -> None:
    """Credential presence alone cannot initiate Anthropic live execution."""
    source = APP_PATH.read_text(encoding="utf-8")

    assert 'authorized_session_key("Anthropic")' in source
    assert '"Run Anthropic LIVE - may incur cost"' in source
    assert 'key="run_anthropic_live"' in source
    assert "disabled=anthropic_live_key is None" in source
    assert "run_anthropic_live(" in source
    assert "api_key=anthropic_live_key or" in source
    assert "max_retries=0" in source
    assert "Live request bodies are intentionally not retained" in source

def test_anthropic_live_ui_evidence_and_render_order() -> None:
    """Live evidence text is current and results render after both live controls."""
    source = APP_PATH.read_text(encoding="utf-8")

    assert "Anthropic live execution remains" not in source
    assert "deferred to PR-03" not in source
    assert "OpenAI LIVE and Anthropic LIVE buttons" in source

    openai_button = source.index('"Run OpenAI LIVE - may incur cost"')
    anthropic_button = source.index('"Run Anthropic LIVE - may incur cost"')
    render_lookup = source.index(
        'demo: IntegrationDemo | None = st.session_state.get("integration_demo")',
        anthropic_button,
    )
    render_call = source.index("_render_integration_result(demo)", render_lookup)

    assert openai_button < anthropic_button < render_lookup < render_call
