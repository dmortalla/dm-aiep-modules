"""Production-oriented asynchronous HTTP API client."""

import asyncio
import logging
from collections.abc import Mapping
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class APIClientError(RuntimeError):
    """Represent a failure while communicating with an HTTP API."""


class AsyncAPIClient:
    """Provide safe asynchronous JSON API requests with retries and timeouts."""

    def __init__(
        self,
        *,
        base_url: str = "",
        timeout: float = 10.0,
        max_retries: int = 2,
        backoff_seconds: float = 0.25,
        headers: Mapping[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Initialize the asynchronous API client.

        Args:
            base_url: Optional base URL applied to relative request paths.
            timeout: Request timeout in seconds.
            max_retries: Number of retries after the initial attempt.
            backoff_seconds: Base delay used for exponential retry backoff.
            headers: Optional default HTTP headers.
            transport: Optional HTTPX transport, primarily for testing.
        """
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        if backoff_seconds < 0:
            raise ValueError("backoff_seconds cannot be negative")

        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout),
            headers=headers,
            transport=transport,
        )

    async def __aenter__(self) -> "AsyncAPIClient":
        """Enter the asynchronous context manager."""

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: Any,
    ) -> None:
        """Close the underlying HTTP client."""

        await self.aclose()

    async def aclose(self) -> None:
        """Release network resources."""

        await self._client.aclose()

    async def request_json(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """Send an HTTP request and return its decoded JSON response.

        Retries are attempted for transport failures, timeouts, HTTP 429,
        and HTTP 5xx responses. Other HTTP errors fail immediately.
        """
        attempts = self._max_retries + 1

        for attempt in range(attempts):
            try:
                response = await self._client.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers=headers,
                )

                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()

                if response.is_error:
                    response.raise_for_status()

                try:
                    return response.json()
                except ValueError as exc:
                    raise APIClientError(
                        "API returned a response that was not valid JSON."
                    ) from exc

            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt >= self._max_retries:
                    raise APIClientError(
                        f"API request failed after {attempts} attempts."
                    ) from exc

                await self._wait_before_retry(attempt, exc)

            except httpx.HTTPStatusError as exc:
                retryable = (
                    exc.response.status_code == 429
                    or exc.response.status_code >= 500
                )

                if not retryable or attempt >= self._max_retries:
                    raise APIClientError(
                        f"API returned HTTP {exc.response.status_code}."
                    ) from exc

                await self._wait_before_retry(attempt, exc)

        raise APIClientError("API request failed unexpectedly.")

    async def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        """Send a GET request and return decoded JSON."""

        return await self.request_json("GET", url, params=params)

    async def post_json(
        self,
        url: str,
        *,
        json: Any | None = None,
    ) -> Any:
        """Send a POST request and return decoded JSON."""

        return await self.request_json("POST", url, json=json)

    async def _wait_before_retry(
        self,
        attempt: int,
        error: Exception,
    ) -> None:
        """Log a retry and wait using exponential backoff."""

        delay = self._backoff_seconds * (2**attempt)

        logger.warning(
            "API request failed (%s). Retrying in %.2f seconds.",
            type(error).__name__,
            delay,
        )

        if delay > 0:
            await asyncio.sleep(delay)
