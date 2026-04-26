import httpx
import pytest

from data.gateways import DEFAULT_RESPONSE_BODY_LIMIT, HttpxWebhookGateway, WebhookGatewayError
from domain.interfaces import HttpRequest, HttpTimeouts


def test_httpx_gateway_posts_request_and_truncates_response_body():
    def handler(request):
        assert request.url == "https://example.test/webhook"
        assert request.headers["x-signature"] == "sha256=test"
        assert request.content == b'{"ok":true}'
        return httpx.Response(202, text="x" * (DEFAULT_RESPONSE_BODY_LIMIT + 5))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    gateway = HttpxWebhookGateway(client=client)

    response = gateway.post(
        HttpRequest(
            url="https://example.test/webhook",
            body='{"ok":true}',
            headers={"X-Signature": "sha256=test"},
            timeouts=HttpTimeouts(connect_seconds=5, read_seconds=15),
        )
    )

    assert response.status_code == 202
    assert response.is_success is True
    assert len(response.body) == DEFAULT_RESPONSE_BODY_LIMIT


def test_httpx_gateway_uses_strict_timeout_values():
    gateway = HttpxWebhookGateway()

    timeout = gateway._to_httpx_timeout(HttpTimeouts(connect_seconds=3, read_seconds=11))

    assert timeout.connect == 3
    assert timeout.read == 11
    assert timeout.write == 11
    assert timeout.pool == 3


def test_httpx_gateway_retries_transport_errors_when_configured():
    calls = {"count": 0}

    def handler(request):
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ConnectError("connect failed", request=request)
        return httpx.Response(204)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    gateway = HttpxWebhookGateway(client=client, max_transport_retries=1)

    response = gateway.post(HttpRequest(url="https://example.test/webhook", body="{}", headers={}))

    assert response.status_code == 204
    assert calls["count"] == 2


def test_httpx_gateway_raises_transport_error_after_retries():
    def handler(request):
        raise httpx.ReadTimeout("read timed out", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    gateway = HttpxWebhookGateway(client=client, max_transport_retries=1)

    with pytest.raises(WebhookGatewayError) as exc_info:
        gateway.post(HttpRequest(url="https://example.test/webhook", body="{}", headers={}))

    assert exc_info.value.attempts == 2


def test_httpx_gateway_rejects_invalid_configuration():
    with pytest.raises(ValueError, match="response_body_limit"):
        HttpxWebhookGateway(response_body_limit=0)

    with pytest.raises(ValueError, match="max_transport_retries"):
        HttpxWebhookGateway(max_transport_retries=-1)
