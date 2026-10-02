"""Deterministic credential management for Module 1.

Credential operations are an application authority boundary. LLM prompts,
responses, and provider output are untrusted data and must never invoke or
control these functions.

The application starts with zero authorized credentials. Credentials become
usable only after an explicit user action authorizes a session credential,
a project-local credential, or an operating-system credential.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from pathlib import Path

ALLOWED_CREDENTIALS = frozenset(
    {
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
    }
)


class CredentialSecurityError(ValueError):
    """Represent a rejected credential-management operation."""


def _validate_name(name: str) -> None:
    """Reject credential names outside the explicit allowlist."""
    if name not in ALLOWED_CREDENTIALS:
        raise CredentialSecurityError(f"Unsupported credential name: {name}")


def _validate_value(value: str) -> str:
    """Validate a secret without exposing it in an error message."""
    normalized = value.strip()

    if not normalized:
        raise CredentialSecurityError("Credential value cannot be empty.")

    if "\n" in normalized or "\r" in normalized:
        raise CredentialSecurityError(
            "Credential value cannot contain line breaks."
        )

    return normalized


def read_local_credential_names(env_path: Path) -> frozenset[str]:
    """Return configured allowlisted names without returning secret values."""
    if not env_path.is_file():
        return frozenset()

    configured: set[str] = set()

    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()

        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        name, value = stripped.split("=", 1)
        name = name.strip()

        if name in ALLOWED_CREDENTIALS and value.strip():
            configured.add(name)

    return frozenset(configured)


def _read_allowed_values(env_path: Path) -> dict[str, str]:
    """Read only allowlisted credentials from the local environment file."""
    if not env_path.is_file():
        return {}

    values: dict[str, str] = {}

    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()

        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        name, value = stripped.split("=", 1)
        name = name.strip()

        if name in ALLOWED_CREDENTIALS and value.strip():
            values[name] = value.strip()

    return values


def _write_atomic(env_path: Path, values: Mapping[str, str]) -> None:
    """Atomically write the allowlisted local credential file."""
    env_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Module 1 local credentials",
        "# Never commit this file.",
        "",
    ]

    for name in sorted(values):
        _validate_name(name)
        lines.append(f"{name}={_validate_value(values[name])}")

    payload = "\n".join(lines) + "\n"

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=".env.",
        suffix=".tmp",
        dir=env_path.parent,
        text=True,
    )

    try:
        with os.fdopen(
            file_descriptor,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            handle.write(payload)

        Path(temporary_name).replace(env_path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def save_local_credentials(
    env_path: Path,
    updates: Mapping[str, str],
) -> frozenset[str]:
    """Persist explicitly selected credentials while preserving existing ones."""
    if not updates:
        raise CredentialSecurityError("No credentials were supplied.")

    current = _read_allowed_values(env_path)

    for name, value in updates.items():
        _validate_name(name)
        current[name] = _validate_value(value)

    _write_atomic(env_path, current)
    return frozenset(current)


def remove_local_credentials(
    env_path: Path,
    names: set[str],
) -> frozenset[str]:
    """Remove selected local credentials without touching OS credentials."""
    if not names:
        raise CredentialSecurityError("No credentials were selected.")

    current = _read_allowed_values(env_path)

    for name in names:
        _validate_name(name)
        current.pop(name, None)

    if current:
        _write_atomic(env_path, current)
    else:
        env_path.unlink(missing_ok=True)

    return frozenset(current)


def delete_local_env(env_path: Path) -> None:
    """Delete only the explicitly supplied project-local environment file."""
    env_path.unlink(missing_ok=True)


def read_local_credential(env_path: Path, name: str) -> str | None:
    """Read one explicitly requested project-local credential."""
    _validate_name(name)
    return _read_allowed_values(env_path).get(name)


def read_os_credential(name: str) -> str | None:
    """Read one explicitly requested operating-system credential."""
    _validate_name(name)
    return os.getenv(name)