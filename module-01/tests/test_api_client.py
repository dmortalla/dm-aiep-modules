"""Tests for the asynchronous HTTP API client."""

import httpx
import pytest
from ai_engineering_foundations.api_client import APIClientError, AsyncAPIClient


@pytest.mark.asyncio
async def test_get_json_returns_decoded_response() -> None:
    """Successful JSON responses should be decoded."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)

    async with AsyncAPIClient(transport=transport) as client:
        response = await client.get_json("https://example.test/status")

    assert response == {"status": "ok"}


@pytest.mark.asyncio
async def test_post_json_sends_payload() -> None:
    """POST requests should send JSON payloads."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.content == b'{"prompt":"hello"}'
        return httpx.Response(200, json={"accepted": True})

    transport = httpx.MockTransport(handler)

    async with AsyncAPIClient(transport=transport) as client:
        response = await client.post_json(
            "https://example.test/generate",
            json={"prompt": "hello"},
        )

    assert response == {"accepted": True}


@pytest.mark.asyncio
async def test_retryable_status_is_retried() -> None:
    """Server errors should be retried before succeeding."""

    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1

        if attempts == 1:
            return httpx.Response(503, request=request)

        return httpx.Response(200, json={"status": "recovered"})

    transport = httpx.MockTransport(handler)

    async with AsyncAPIClient(
        transport=transport,
        max_retries=1,
        backoff_seconds=0,
    ) as client:
        response = await client.get_json("https://example.test/status")

    assert attempts == 2
    assert response == {"status": "recovered"}


@pytest.mark.asyncio
async def test_non_retryable_status_fails_immediately() -> None:
    """Client errors other than 429 should not be retried."""

    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(400, request=request)

    transport = httpx.MockTransport(handler)

    async with AsyncAPIClient(
        transport=transport,
        max_retries=3,
        backoff_seconds=0,
    ) as client:
        with pytest.raises(APIClientError, match="HTTP 400"):
            await client.get_json("https://example.test/status")

    assert attempts == 1


@pytest.mark.asyncio
async def test_invalid_json_raises_client_error() -> None:
    """Successful non-JSON responses should produce a clear client error."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="not-json",
            request=request,
        )

    transport = httpx.MockTransport(handler)

    async with AsyncAPIClient(transport=transport) as client:
        with pytest.raises(APIClientError, match="not valid JSON"):
            await client.get_json("https://example.test/status")


def test_invalid_client_configuration_is_rejected() -> None:
    """Unsafe retry and timeout configuration should fail early."""

    with pytest.raises(ValueError, match="timeout"):
        AsyncAPIClient(timeout=0)

    with pytest.raises(ValueError, match="max_retries"):
        AsyncAPIClient(max_retries=-1)

    with pytest.raises(ValueError, match="backoff_seconds"):
        AsyncAPIClient(backoff_seconds=-1)


@pytest.mark.asyncio
async def test_rate_limit_respects_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP 429 should respect a valid server Retry-After instruction."""
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1

        if attempts == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "2"},
                request=request,
            )

        return httpx.Response(200, json={"status": "ok"}, request=request)

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(
        "ai_engineering_foundations.api_client.asyncio.sleep",
        fake_sleep,
    )

    async with AsyncAPIClient(
        transport=httpx.MockTransport(handler),
        max_retries=1,
        backoff_seconds=0.25,
    ) as client:
        response = await client.get_json("https://example.test/rate-limited")

    assert response == {"status": "ok"}
    assert attempts == 2
    assert delays == [2.0]


@pytest.mark.asyncio
async def test_invalid_retry_after_falls_back_to_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid Retry-After values should fall back to exponential backoff."""
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1

        if attempts == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "invalid"},
                request=request,
            )

        return httpx.Response(200, json={"status": "ok"}, request=request)

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(
        "ai_engineering_foundations.api_client.asyncio.sleep",
        fake_sleep,
    )

    async with AsyncAPIClient(
        transport=httpx.MockTransport(handler),
        max_retries=1,
        backoff_seconds=0.25,
    ) as client:
        response = await client.get_json("https://example.test/rate-limited")

    assert response == {"status": "ok"}
    assert delays == [0.25]