"""Launch the Module 6 cockpit for one trusted private-local operator.

This entry point is intentionally separate from the stock/public launcher.
Streamlit executes ``private_local_app.py`` directly; that wrapper supplies the
application-owned trusted runtime while rendering ``app.py``. Credential
presence, environment state, hostname and provider availability never create
authority.
"""

from __future__ import annotations

from pathlib import Path

from streamlit.web import cli

APP = Path(__file__).with_name("private_local_app.py")


def main() -> None:
    """Start the hardened loopback Streamlit server for a private operator."""
    cli.main(
        [
            "streamlit",
            "run",
            str(APP),
            "--server.address=127.0.0.1",
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
            "--client.showErrorDetails=false",
            "--server.maxMessageSize=1",
        ],
        prog_name="streamlit",
    )


if __name__ == "__main__":
    main()
