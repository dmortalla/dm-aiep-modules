"""Offline guards for every Module 6 test, including real SDK construction."""

import ipaddress
import socket

import pytest


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Disable telemetry and fail any non-loopback DNS/connection attempt."""
    for name, value in {
        "OTEL_SDK_DISABLED": "true",
        "CREWAI_TELEMETRY_ENABLED": "false",
        "CREWAI_TELEMETRY_DISABLED": "true",
        "LITELLM_LOCAL_MODEL_COST_MAP": "true",
        "DO_NOT_TRACK": "1",
        "LANGSMITH_TRACING": "false",
        "LANGCHAIN_TRACING_V2": "false",
    }.items():
        monkeypatch.setenv(name, value)
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
        attempts.append("connect")
        raise AssertionError("Module 6 tests forbid non-loopback connections.")

    def connect_ex(sock, address):
        if isinstance(address, tuple) and local(address[0]):
            return original_connect_ex(sock, address)
        attempts.append("connect_ex")
        raise AssertionError("Module 6 tests forbid non-loopback connections.")

    def dns(host, *args, **kwargs):
        if local(host):
            return original_dns(host, *args, **kwargs)
        attempts.append("dns")
        raise AssertionError("Module 6 tests forbid non-loopback DNS.")

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", dns)
    yield
    assert attempts == [], (
        "An SDK attempted external access even if it caught the error."
    )
