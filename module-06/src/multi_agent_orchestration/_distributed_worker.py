"""One-shot credential-free process endpoint; no worker-created trusted evidence."""

import asyncio
import contextlib
import hashlib
import hmac
import io
import ipaddress
import os
import socket
import sys

from .distributed import decode_packet, encode_packet, validate_assignment
from .distributed_contracts import (
    MAX_PACKET_BYTES,
    WorkerAssignment,
    WorkerFailure,
    WorkerId,
    WorkerReady,
    WorkerRelease,
    WorkerStarted,
)
from .errors import InvalidRuntimeOutputError, InvalidWorkflowRequestError


def install_offline_guard():
    """Deny/count every non-loopback attempt, even if a library swallows it."""
    attempts = []
    connect, connect_ex, dns = (
        socket.socket.connect,
        socket.socket.connect_ex,
        socket.getaddrinfo,
    )

    def local(host):
        if host in ("localhost", b"localhost"):
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def guarded(original):
        def execute(sock, address):
            if isinstance(address, tuple) and local(address[0]):
                return original(sock, address)
            attempts.append(True)
            raise RuntimeError("Offline worker denies external connections.")

        return execute

    def guarded_dns(host, *args, **kwargs):
        if local(host):
            return dns(host, *args, **kwargs)
        attempts.append(True)
        raise RuntimeError("Offline worker denies external DNS.")

    socket.socket.connect = guarded(connect)
    socket.socket.connect_ex = guarded(connect_ex)
    socket.getaddrinfo = guarded_dns
    return attempts


class DiscardLogs(io.TextIOBase):
    def write(self, text):
        return len(text)


def read_frame():
    data = sys.stdin.buffer.readline(MAX_PACKET_BYTES + 1)
    if len(data) > MAX_PACKET_BYTES or not data.endswith(b"\n"):
        raise InvalidWorkflowRequestError("Worker input framing is invalid.")
    return data


def validate_bootstrap(data: bytes, worker: WorkerId, digest: str, coordinator: int):
    """Trusted launcher binds the exact bytes; digest is integrity, not remote auth."""
    if not hmac.compare_digest(hashlib.sha256(data).hexdigest(), digest):
        raise InvalidWorkflowRequestError("Assignment differs from launcher authority.")
    assignment = decode_packet(data, WorkerAssignment)
    assignment = validate_assignment(assignment)
    if (
        assignment.worker != worker
        or assignment.coordinator_pid != coordinator
        or coordinator != os.getppid()
    ):
        raise InvalidWorkflowRequestError(
            "Worker assignment parent/identity is invalid."
        )
    return assignment


def main():
    attempts = install_offline_guard()
    stream = sys.stdout.buffer

    def emit(packet):
        stream.write(encode_packet(packet))
        stream.flush()

    try:
        if len(sys.argv) != 4:
            raise InvalidWorkflowRequestError("Worker launch contract is invalid.")
        worker, digest, coordinator = (
            WorkerId(sys.argv[1]),
            sys.argv[2],
            int(sys.argv[3]),
        )
        if coordinator != os.getppid() or len(digest) != 64:
            raise InvalidWorkflowRequestError("Worker launch authority is invalid.")
        pid = os.getpid()
        emit(WorkerReady(worker=worker, pid=pid, coordinator_pid=coordinator))
        assignment = validate_bootstrap(read_frame(), worker, digest, coordinator)

        async def barrier(state):
            emit(
                WorkerStarted(
                    workflow_id=state.workflow_id,
                    task_id=state.task_id,
                    assignment_id=state.assignment_id,
                    worker=state.worker,
                    role=state.role,
                    pid=pid,
                )
            )
            release = decode_packet(read_frame(), WorkerRelease)
            if release != WorkerRelease(
                assignment_id=state.assignment_id,
                worker=state.worker,
                coordinator_pid=coordinator,
            ) or sys.stdin.buffer.read(1):
                raise InvalidWorkflowRequestError(
                    "Worker release authority is invalid."
                )

        # No SDK diagnostics or task data reach the protocol/public output.
        with contextlib.redirect_stdout(DiscardLogs()):
            from ._distributed_adk import run_assignment

            response = asyncio.run(run_assignment(assignment, pid, barrier))
        if attempts:
            raise RuntimeError("Worker attempted forbidden external access.")
        emit(response)
    except Exception as exc:
        category = (
            "offline"
            if attempts
            else "invalid_assignment"
            if isinstance(exc, InvalidWorkflowRequestError)
            else "invalid_output"
            if isinstance(exc, InvalidRuntimeOutputError)
            else "execution"
        )
        emit(WorkerFailure(category=category, cause_type=type(exc).__name__))


if __name__ == "__main__":
    main()
