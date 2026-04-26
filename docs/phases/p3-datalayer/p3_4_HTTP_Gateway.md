# Phase 3.4 - HTTP Gateway

Branch: `feature/p3-datalayer-p3_4_HTTP_Gateway`

## Objective

Provide the infrastructure adapter that sends signed webhook payloads to subscriber endpoints using `httpx` with strict timeout behavior.

## Changes

- Added `HttpxWebhookGateway`.
- Added strict connect/read timeout conversion from the domain `HttpTimeouts` contract into `httpx.Timeout`.
- Added response body truncation for bounded delivery logging.
- Added structured response/error logging through the `webhook.delivery` logger.
- Added optional transport retry handling, defaulting to zero hidden retries.
- Added integration-style tests using `httpx.MockTransport`.

## Architecture Notes

- Durable webhook retry policy remains owned by Celery delivery tasks, not the gateway. The gateway defaults to one transport attempt so delivery attempts remain observable.
- Optional `max_transport_retries` is available for narrow network retry use cases, but callers must opt in.
- The gateway returns the domain-owned `HttpResponse` value object rather than leaking `httpx.Response`.
- Infinite timeouts are never used; connect/read/write/pool timeout values are always finite.
- Response bodies are truncated before returning/logging so subscriber responses cannot bloat delivery attempt records.

## Verification

- `python -m compileall data tests`
- Attempted `python -c "import httpx; print(httpx.__version__)"`; blocked because `httpx` is not installed in the current local Python environment.

## Deferred

- Runtime execution of `tests/integration/test_httpx_gateway.py` is deferred until `httpx` and `pytest` are installed locally.
- Celery delivery task integration is handled in Phase 4.4.
