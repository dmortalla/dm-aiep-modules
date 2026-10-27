"""Local console launch with fixed loopback binding and disabled usage telemetry."""

from pathlib import Path


def main():
    from streamlit.web.cli import main as streamlit_main

    streamlit_main(
        [
            "run",
            str(Path(__file__).with_name("app.py").resolve()),
            "--server.address=127.0.0.1",
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
            "--client.showErrorDetails=none",
            "--server.maxMessageSize=1",
        ],
        prog_name="streamlit",
    )


if __name__ == "__main__":
    main()
