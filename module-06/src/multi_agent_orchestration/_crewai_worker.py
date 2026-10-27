"""Private local process entry point; fail closed on any attempted external access."""

import contextlib
import io
import ipaddress
import json
import socket
import sys
import traceback

from .contracts import RuntimeId, WorkflowRequest
from .errors import InvalidWorkflowRequestError


def main() -> None:
    """Execute one fixed offline crew and return a bounded private JSON envelope."""
    attempts = []
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_dns = socket.getaddrinfo

    def local(host):
        if host in ("localhost", b"localhost"):
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def connect(sock, address):
        if isinstance(address, tuple) and local(address[0]):
            return original_connect(sock, address)
        attempts.append(True)
        raise RuntimeError("Offline CrewAI denies external connections.")

    def connect_ex(sock, address):
        if isinstance(address, tuple) and local(address[0]):
            return original_connect_ex(sock, address)
        attempts.append(True)
        raise RuntimeError("Offline CrewAI denies external connections.")

    def dns(host, *args, **kwargs):
        if local(host):
            return original_dns(host, *args, **kwargs)
        attempts.append(True)
        raise RuntimeError("Offline CrewAI denies external DNS.")

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = dns
    try:
        request = WorkflowRequest.model_validate_json(sys.stdin.buffer.read(32_000))
        if request.runtime != RuntimeId.CREWAI:
            raise InvalidWorkflowRequestError("Crew worker requires explicit CrewAI.")
        with contextlib.redirect_stdout(io.StringIO()):
            from ._crewai_adapter import run_crew

            result = run_crew(request)
        if attempts:
            raise RuntimeError("CrewAI attempted forbidden external access.")
        packet = {"output": result.model_dump(mode="json")}
    except Exception as exc:
        packet = {
            "error_type": type(exc).__name__,
            "cause": traceback.format_exc()[-4096:],
        }
    print(json.dumps(packet))


if __name__ == "__main__":
    main()
