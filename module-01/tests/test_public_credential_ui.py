from pathlib import Path

APP_PATH = Path(__file__).parents[1] / "app.py"


def test_public_ui_is_session_only() -> None:
    source = APP_PATH.read_text(encoding="utf-8")

    forbidden = (
        "save_local_credentials",
        "read_local_credential(",
        "read_local_credential_names",
        "remove_local_credentials",
        "delete_local_env",
        "read_os_credential",
        "Save entered keys locally",
        "Authorize stored",
        "Authorize OS",
        "Delete local .env",
    )

    for value in forbidden:
        assert value not in source


def test_public_ui_retains_session_controls() -> None:
    source = APP_PATH.read_text(encoding="utf-8")

    assert "Authorize entered keys for this session" in source
    assert "Clear all session credentials" in source
    assert "authorized_session_key" in source


def test_public_ui_has_security_reminder() -> None:
    source = APP_PATH.read_text(encoding="utf-8")

    assert "Security reminder:" in source
    assert "prefers-reduced-motion" in source
    assert "close this tab" in source