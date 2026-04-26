"""httpx-backed webhook delivery gateway."""

import logging
import time
from typing import Mapping, Optional

import httpx
from django.conf import settings

from domain.interfaces import HttpGateway, HttpRequest, HttpResponse, HttpTimeouts


DEFAULT_RESPONSE_BODY_LIMIT = 500

logger = logging.getLogger("webhook.delivery")


class WebhookGatewayError(RuntimeError):
    """Raised when a webhook request cannot be completed by the transport."""

    def __init__(self, message: str, *, elapsed_seconds: float, attempts: int) -> None:
        self.elapsed_seconds = elapsed_seconds
        self.attempts = attempts
        super().__init__(message)


class HttpxWebhookGateway(HttpGateway):
    """
    Deliver webhook requests using httpx with strict timeouts.

    Durable delivery retries are owned by Celery delivery tasks. The optional
    transport retry count defaults to zero to avoid hidden duplicate POSTs.
    """

    def __init__(
        self,
        *,
        client: Optional[httpx.Client] = None,
        default_timeouts: Optional[HttpTimeouts] = None,
        response_body_limit: int = DEFAULT_RESPONSE_BODY_LIMIT,
        max_transport_retries: int = 0,
        retry_backoff_seconds: float = 0.0,
    ) -> None:
        if response_body_limit <= 0:
            raise ValueError("response_body_limit must be greater than zero")
        if max_transport_retries < 0:
            raise ValueError("max_transport_retries cannot be negative")
        if retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds cannot be negative")

        self._client = client
        self._owns_client = client is None
        self._default_timeouts = default_timeouts or HttpTimeouts(
            connect_seconds=float(getattr(settings, "WEBHOOK_CONNECT_TIMEOUT", 5)),
            read_seconds=float(getattr(settings, "WEBHOOK_READ_TIMEOUT", 15)),
        )
        self._response_body_limit = response_body_limit
        self._max_transport_retries = max_transport_retries
        self._retry_backoff_seconds = retry_backoff_seconds

    def post(self, request: HttpRequest) -> HttpResponse:
        started_at = time.monotonic()
        attempts = 0
        last_error: Optional[Exception] = None

        while attempts <= self._max_transport_retries:
            attempts += 1
            try:
                response = self._client_for_request().post(
                    request.url,
                    content=request.body,
                    headers=dict(request.headers),
                    timeout=self._to_httpx_timeout(request.timeouts or self._default_timeouts),
                )
                elapsed = time.monotonic() - started_at
                response_body = self._truncate_response_body(response.text)
                self._log_response(request, response.status_code, response_body, elapsed, attempts)
                return HttpResponse(
                    status_code=response.status_code,
                    body=response_body,
                    headers=self._flatten_headers(response.headers),
                    elapsed_seconds=elapsed,
                )
            except httpx.RequestError as exc:
                last_error = exc
                elapsed = time.monotonic() - started_at
                logger.warning(
                    "webhook_delivery_transport_error",
                    extra={
                        "target_url": request.url,
                        "attempts": attempts,
                        "elapsed_seconds": elapsed,
                        "error": str(exc),
                    },
                )
                if attempts > self._max_transport_retries:
                    break
                if self._retry_backoff_seconds:
                    time.sleep(self._retry_backoff_seconds)

        elapsed = time.monotonic() - started_at
        raise WebhookGatewayError(
            str(last_error) if last_error else "Webhook transport request failed.",
            elapsed_seconds=elapsed,
            attempts=attempts,
        )

    def close(self) -> None:
        """Close the owned httpx client, if one was lazily created."""
        if self._client is not None and self._owns_client:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def _client_for_request(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client()
        return self._client

    @staticmethod
    def _to_httpx_timeout(timeouts: HttpTimeouts) -> httpx.Timeout:
        return httpx.Timeout(
            timeout=None,
            connect=timeouts.connect_seconds,
            read=timeouts.read_seconds,
            write=timeouts.read_seconds,
            pool=timeouts.connect_seconds,
        )

    def _truncate_response_body(self, body: str) -> str:
        return body[: self._response_body_limit]

    @staticmethod
    def _flatten_headers(headers: Mapping[str, str]) -> Mapping[str, str]:
        return {str(key).lower(): str(value) for key, value in headers.items()}

    @staticmethod
    def _log_response(
        request: HttpRequest,
        status_code: int,
        response_body: str,
        elapsed_seconds: float,
        attempts: int,
    ) -> None:
        logger.info(
            "webhook_delivery_response",
            extra={
                "target_url": request.url,
                "status_code": status_code,
                "elapsed_seconds": elapsed_seconds,
                "attempts": attempts,
                "response_body": response_body,
                "metadata": dict(request.metadata or {}),
            },
        )
