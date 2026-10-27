"""Regression tests for the private-local Module 6 launcher composition."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1]
LAUNCHER = MODULE / "run_local_live.py"
WRAPPER = MODULE / "private_local_app.py"
RUNTIME_HOLDER = MODULE / "private_local_runtime.py"


def _load_launcher():
    """Import the launcher without invoking Streamlit."""
    spec = importlib.util.spec_from_file_location(
        "module6_private_local_launcher",
        LAUNCHER,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_import_does_not_launch_streamlit(monkeypatch):
    """Importing the launcher must never start Streamlit."""
    import streamlit.web.cli as cli

    calls = []
    monkeypatch.setattr(
        cli,
        "main",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    module = _load_launcher()

    assert calls == []
    assert module.APP == WRAPPER


def test_launcher_targets_wrapper_with_loopback_safety(monkeypatch):
    """The private launcher must execute only the trusted wrapper on loopback."""
    module = _load_launcher()
    calls = []

    monkeypatch.setattr(
        module.cli,
        "main",
        lambda args, prog_name=None: calls.append((args, prog_name)),
    )

    module.main()

    assert len(calls) == 1
    args, prog_name = calls[0]

    assert prog_name == "streamlit"
    assert args[:3] == ["streamlit", "run", str(WRAPPER)]
    assert "--server.address=127.0.0.1" in args
    assert "--server.headless=true" in args
    assert "--browser.gatherUsageStats=false" in args
    assert "--client.showErrorDetails=false" in args
    assert "--server.maxMessageSize=1" in args


def test_wrapper_uses_accepted_trusted_context_composition():
    """The wrapper must reproduce the accepted trusted embedding architecture."""
    source = WRAPPER.read_text(encoding="utf-8")

    assert "from private_local_runtime import runtime" in source
    assert "with trusted_local_context(runtime):" in source
    assert 'runpy.run_path(str(APP), run_name="__main__")' in source


def test_runtime_holder_owns_one_explicit_private_runtime():
    """The holder must construct only the explicit private-local capability."""
    source = RUNTIME_HOLDER.read_text(encoding="utf-8")

    assert 'TrustedLocalRuntime(posture="trusted-private-local")' in source
    assert "LiveAuthorization" not in source
    assert "run_explicit_action" not in source
    assert "os.environ" not in source
    assert "getenv" not in source


def test_launcher_contains_no_runpy_interception():
    """The repaired launcher must not depend on Streamlit internals."""
    source = LAUNCHER.read_text(encoding="utf-8")

    assert "runpy" not in source
    assert "trusted_run_path" not in source
    assert "runpy.run_path =" not in source


@pytest.mark.parametrize(
    "path",
    [LAUNCHER, WRAPPER, RUNTIME_HOLDER],
)
def test_private_entry_points_are_utf8_without_bom(path):
    """Private entry points remain plain UTF-8 without a byte-order mark."""
    raw = path.read_bytes()

    assert not raw.startswith(b"\xef\xbb\xbf")
    raw.decode("utf-8")
