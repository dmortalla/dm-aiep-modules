"""Own the trusted private-local runtime for one local Streamlit process.

Importing this module constructs the application-owned capability but does not
authorize or execute a live action. The runtime is reused across Streamlit
reruns within this private process.
"""

from multi_agent_orchestration.cockpit_local_live import TrustedLocalRuntime

runtime = TrustedLocalRuntime(posture="trusted-private-local")
