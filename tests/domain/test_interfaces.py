import pytest

from domain.entities import DeliveryAttempt, Subscription, WebhookEvent
from domain.interfaces import (
    DeliveryAttemptRepository,
    EventRepository,
    HttpGateway,
    HttpRequest,
    HttpResponse,
    HttpTimeouts,
    SubscriptionRepository,
)


class InMemorySubscriptionRepository:
    def create(self, subscription: Subscription) -> Subscription:
        return subscription

    def get_by_id(self, subscription_id: str, tenant_id: str) -> Subscription:
        return Subscription(
            id=subscription_id,
            tenant_id=tenant_id,
            event_type="po.created",
            target_url="https://example.test/webhook",
        )

    def list_by_tenant(self, tenant_id: str):
        return []

    def list_active_by_tenant(self, tenant_id: str):
        return []

    def update(self, subscription: Subscription) -> Subscription:
        return subscription

    def delete(self, subscription_id: str, tenant_id: str) -> None:
        return None


class InMemoryEventRepository:
    def create(self, event: WebhookEvent) -> WebhookEvent:
        return event

    def get_by_id(self, event_id: str, tenant_id: str) -> WebhookEvent:
        return WebhookEvent(id=event_id, tenant_id=tenant_id, event_type="po.created")

    def get_by_idempotency_key(self, tenant_id: str, idempotency_key: str):
        return None

    def mark_processed(self, event_id: str, tenant_id: str) -> None:
        return None


class InMemoryDeliveryAttemptRepository:
    def create(self, attempt: DeliveryAttempt, tenant_id: str) -> DeliveryAttempt:
        return attempt

    def get_by_id(self, attempt_id: str, tenant_id: str) -> DeliveryAttempt:
        return DeliveryAttempt(
            id=attempt_id,
            event_id="event-1",
            subscription_id="subscription-1",
        )

    def find_by_event_and_subscription(
        self,
        event_id: str,
        subscription_id: str,
        tenant_id: str,
    ):
        return None

    def list_for_event(self, event_id: str, tenant_id: str):
        return []

    def update(self, attempt: DeliveryAttempt, tenant_id: str) -> DeliveryAttempt:
        return attempt


class RecordingHttpGateway:
    def post(self, request: HttpRequest) -> HttpResponse:
        return HttpResponse(status_code=204, elapsed_seconds=0.1)


def test_repository_protocols_are_runtime_checkable():
    assert isinstance(InMemorySubscriptionRepository(), SubscriptionRepository)
    assert isinstance(InMemoryEventRepository(), EventRepository)
    assert isinstance(InMemoryDeliveryAttemptRepository(), DeliveryAttemptRepository)


def test_http_gateway_protocol_is_runtime_checkable():
    gateway = RecordingHttpGateway()
    request = HttpRequest(
        url="https://example.test/webhook",
        body='{"event":"po.created"}',
        headers={"X-Signature": "sha256=test"},
    )

    assert isinstance(gateway, HttpGateway)
    assert gateway.post(request).is_success is True


def test_http_timeouts_reject_non_positive_values():
    with pytest.raises(ValueError, match="connect_seconds"):
        HttpTimeouts(connect_seconds=0)

    with pytest.raises(ValueError, match="read_seconds"):
        HttpTimeouts(read_seconds=0)


def test_http_request_requires_url():
    with pytest.raises(ValueError, match="url is required"):
        HttpRequest(url="", body="{}", headers={})
