from django.db import IntegrityError, transaction
from django.test import TestCase

from data.models.models import (
    DeliveryAttempt,
    DeliveryStatus,
    Subscription,
    Tenant,
    TenantAPIKey,
    WebhookEvent,
)


class WebhookDataModelTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Acme", slug="acme")

    def test_tenant_api_key_stores_hash_metadata_only(self):
        api_key = TenantAPIKey.objects.create(
            tenant=self.tenant,
            name="Default",
            key_prefix="rdwh_1234",
            key_hash="hash-value",
        )

        assert api_key.tenant == self.tenant
        assert api_key.key_hash == "hash-value"

    def test_subscription_is_unique_per_tenant_event_and_target(self):
        Subscription.objects.create(
            tenant=self.tenant,
            event_type="po.created",
            target_url="https://example.test/webhook",
            secret_hash="secret-hash",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Subscription.objects.create(
                    tenant=self.tenant,
                    event_type="po.created",
                    target_url="https://example.test/webhook",
                    secret_hash="different-hash",
                )

    def test_event_idempotency_key_is_unique_per_tenant(self):
        WebhookEvent.objects.create(
            tenant=self.tenant,
            event_type="po.created",
            payload={"id": "PO-1"},
            idempotency_key="key-1",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WebhookEvent.objects.create(
                    tenant=self.tenant,
                    event_type="po.created",
                    payload={"id": "PO-1"},
                    idempotency_key="key-1",
                )

    def test_delivery_attempt_is_unique_per_event_subscription_pair(self):
        subscription = Subscription.objects.create(
            tenant=self.tenant,
            event_type="po.created",
            target_url="https://example.test/webhook",
            secret_hash="secret-hash",
        )
        event = WebhookEvent.objects.create(
            tenant=self.tenant,
            event_type="po.created",
            payload={"id": "PO-1"},
            idempotency_key="key-1",
        )
        attempt = DeliveryAttempt.objects.create(event=event, subscription=subscription)

        assert attempt.status == DeliveryStatus.PENDING

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DeliveryAttempt.objects.create(event=event, subscription=subscription)
