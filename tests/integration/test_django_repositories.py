from django.db import transaction
from django.test import TestCase

from data.models.models import Tenant
from data.repositories import (
    DjangoDeliveryAttemptRepository,
    DjangoEventRepository,
    DjangoSubscriptionRepository,
)
from domain.entities import DeliveryAttempt, DeliveryStatus, Subscription, WebhookEvent
from domain.exceptions import (
    DeliveryAttemptNotFoundError,
    DuplicateEventError,
    EventNotFoundError,
    SubscriptionNotFoundError,
)


class DjangoRepositoryTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Acme", slug="acme")
        self.other_tenant = Tenant.objects.create(name="Globex", slug="globex")
        self.subscriptions = DjangoSubscriptionRepository()
        self.events = DjangoEventRepository()
        self.attempts = DjangoDeliveryAttemptRepository()

    def test_subscription_repository_enforces_tenant_scope(self):
        subscription = self.subscriptions.create(
            Subscription(
                tenant_id=str(self.tenant.id),
                event_type="po.created",
                target_url="https://example.test/webhook",
                secret="secret-hash",
            )
        )

        assert self.subscriptions.get_by_id(subscription.id, str(self.tenant.id)).id == subscription.id

        with self.assertRaises(SubscriptionNotFoundError):
            self.subscriptions.get_by_id(subscription.id, str(self.other_tenant.id))

    def test_event_repository_raises_duplicate_for_reused_idempotency_key(self):
        self.events.create(
            WebhookEvent(
                tenant_id=str(self.tenant.id),
                event_type="po.created",
                payload={"id": "PO-1"},
                idempotency_key="key-1",
            )
        )

        with self.assertRaises(DuplicateEventError):
            with transaction.atomic():
                self.events.create(
                    WebhookEvent(
                        tenant_id=str(self.tenant.id),
                        event_type="po.created",
                        payload={"id": "PO-1"},
                        idempotency_key="key-1",
                    )
                )

    def test_event_repository_marks_processed_with_tenant_scope(self):
        event = self.events.create(
            WebhookEvent(
                tenant_id=str(self.tenant.id),
                event_type="po.created",
                payload={"id": "PO-1"},
            )
        )

        self.events.mark_processed(event.id, str(self.tenant.id))
        assert self.events.get_by_id(event.id, str(self.tenant.id)).processed is True

        with self.assertRaises(EventNotFoundError):
            self.events.mark_processed(event.id, str(self.other_tenant.id))

    def test_delivery_attempt_repository_enforces_event_and_subscription_tenant_scope(self):
        subscription = self.subscriptions.create(
            Subscription(
                tenant_id=str(self.tenant.id),
                event_type="po.created",
                target_url="https://example.test/webhook",
                secret="secret-hash",
            )
        )
        event = self.events.create(
            WebhookEvent(
                tenant_id=str(self.tenant.id),
                event_type="po.created",
                payload={"id": "PO-1"},
            )
        )
        attempt = self.attempts.create(
            DeliveryAttempt(event_id=event.id, subscription_id=subscription.id),
            str(self.tenant.id),
        )

        attempt.mark_success(204, "ok")
        updated = self.attempts.update(attempt, str(self.tenant.id))

        assert updated.status == DeliveryStatus.SUCCESS
        assert updated.response_body == "ok"

        with self.assertRaises(DeliveryAttemptNotFoundError):
            self.attempts.get_by_id(attempt.id, str(self.other_tenant.id))

    def test_delivery_attempt_create_rejects_cross_tenant_subscription(self):
        event = self.events.create(
            WebhookEvent(
                tenant_id=str(self.tenant.id),
                event_type="po.created",
                payload={"id": "PO-1"},
            )
        )
        other_subscription = self.subscriptions.create(
            Subscription(
                tenant_id=str(self.other_tenant.id),
                event_type="po.created",
                target_url="https://other.example.test/webhook",
                secret="secret-hash",
            )
        )

        with self.assertRaises(SubscriptionNotFoundError):
            self.attempts.create(
                DeliveryAttempt(event_id=event.id, subscription_id=other_subscription.id),
                str(self.tenant.id),
            )
