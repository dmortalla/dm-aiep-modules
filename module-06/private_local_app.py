"""Private-local Streamlit entry point for the Module 6 reviewer cockpit.

This wrapper is intentionally separate from the stock/public application entry
point. It injects the application-owned trusted runtime only while rendering
the cockpit for an already trusted private-local operator.
"""

from __future__ import annotations

import runpy
from pathlib import Path

from multi_agent_orchestration.cockpit_local_live import trusted_local_context
from private_local_runtime import runtime

APP = Path(__file__).with_name("app.py")

with trusted_local_context(runtime):
    runpy.run_path(str(APP), run_name="__main__")
