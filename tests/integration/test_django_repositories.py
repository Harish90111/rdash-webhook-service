from datetime import timedelta

from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from data.models.models import Subscription as SubscriptionModel
from data.models.models import Tenant
from data.models.models import TenantAPIKey
from data.repositories import (
    DjangoDeliveryAttemptRepository,
    DjangoEventRepository,
    DjangoSubscriptionRepository,
    DjangoTenantAPIKeyRepository,
)
from domain.entities import DeliveryAttempt, DeliveryStatus, Subscription, WebhookEvent
from domain.exceptions import (
    DeliveryAttemptNotFoundError,
    DuplicateEventError,
    EventNotFoundError,
    SubscriptionNotFoundError,
)


@override_settings(WEBHOOK_SECRET_ENCRYPTION_KEY="integration-secret-encryption-key")
class DjangoRepositoryTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Acme", slug="acme")
        self.other_tenant = Tenant.objects.create(name="Globex", slug="globex")
        self.subscriptions = DjangoSubscriptionRepository()
        self.events = DjangoEventRepository()
        self.attempts = DjangoDeliveryAttemptRepository()

    def test_subscription_repository_crud_hides_secrets_from_list_views(self):
        created = self.subscriptions.create(
            Subscription(
                tenant_id=str(self.tenant.id),
                event_type="po.created",
                target_url="https://example.test/webhook",
                secret="plain-secret",
            )
        )

        stored_model = SubscriptionModel.objects.get(id=created.id)
        assert stored_model.secret_hash != "plain-secret"
        assert stored_model.secret_encrypted
        assert stored_model.secret_encrypted != "plain-secret"

        listed = self.subscriptions.list_by_tenant(str(self.tenant.id))
        assert len(listed) == 1
        assert listed[0].secret == ""

        fetched = self.subscriptions.get_by_id(created.id, str(self.tenant.id))
        assert fetched.secret == "plain-secret"

        fetched.event_type = "po.updated"
        fetched.deactivate()
        fetched.rotate_secret("rotated-secret")
        updated = self.subscriptions.update(fetched)

        assert updated.event_type == "po.updated"
        assert updated.active is False
        assert updated.secret == "rotated-secret"
        assert self.subscriptions.list_active_by_tenant(str(self.tenant.id)) == []
        assert self.subscriptions.get_by_id(created.id, str(self.tenant.id)).secret == "rotated-secret"

        self.subscriptions.delete(created.id, str(self.tenant.id))

        with self.assertRaises(SubscriptionNotFoundError):
            self.subscriptions.get_by_id(created.id, str(self.tenant.id))

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

    def test_event_repository_get_by_idempotency_key_is_tenant_scoped(self):
        created = self.events.create(
            WebhookEvent(
                tenant_id=str(self.tenant.id),
                event_type="po.created",
                payload={"id": "PO-2"},
                idempotency_key="lookup-key",
            )
        )

        found = self.events.get_by_idempotency_key(str(self.tenant.id), "lookup-key")

        assert found is not None
        assert found.id == created.id
        assert self.events.get_by_idempotency_key(str(self.other_tenant.id), "lookup-key") is None
        assert self.events.get_by_idempotency_key(str(self.tenant.id), "") is None

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

    def test_delivery_attempt_claim_for_delivery_is_single_winner(self):
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
                payload={"id": "PO-2"},
            )
        )
        attempt = self.attempts.create(
            DeliveryAttempt(event_id=event.id, subscription_id=subscription.id),
            str(self.tenant.id),
        )

        claimed = self.attempts.claim_for_delivery(attempt.id, str(self.tenant.id))

        assert claimed is not None
        assert claimed.status == DeliveryStatus.IN_PROGRESS
        assert self.attempts.claim_for_delivery(attempt.id, str(self.tenant.id)) is None

        with self.assertRaises(DeliveryAttemptNotFoundError):
            self.attempts.claim_for_delivery(attempt.id, str(self.other_tenant.id))

    def test_delivery_attempt_claim_for_delivery_picks_up_due_retry(self):
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
                payload={"id": "PO-3"},
            )
        )
        attempt = self.attempts.create(
            DeliveryAttempt(event_id=event.id, subscription_id=subscription.id),
            str(self.tenant.id),
        )
        attempt.mark_retrying(timezone.now() - timedelta(seconds=1))
        self.attempts.update(attempt, str(self.tenant.id))

        claimed = self.attempts.claim_for_delivery(attempt.id, str(self.tenant.id))

        assert claimed is not None
        assert claimed.status == DeliveryStatus.IN_PROGRESS
        assert claimed.next_retry_at is None

    def test_delivery_attempt_list_by_tenant_supports_filters_and_tenant_scope(self):
        subscription = self.subscriptions.create(
            Subscription(
                tenant_id=str(self.tenant.id),
                event_type="po.created",
                target_url="https://example.test/webhook",
                secret="secret-hash",
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
        first_event = self.events.create(
            WebhookEvent(
                tenant_id=str(self.tenant.id),
                event_type="po.created",
                payload={"id": "PO-4"},
            )
        )
        second_event = self.events.create(
            WebhookEvent(
                tenant_id=str(self.tenant.id),
                event_type="po.updated",
                payload={"id": "PO-5"},
            )
        )
        other_event = self.events.create(
            WebhookEvent(
                tenant_id=str(self.other_tenant.id),
                event_type="po.created",
                payload={"id": "PO-6"},
            )
        )

        success_attempt = self.attempts.create(
            DeliveryAttempt(event_id=first_event.id, subscription_id=subscription.id),
            str(self.tenant.id),
        )
        success_attempt.mark_success(200, "ok")
        self.attempts.update(success_attempt, str(self.tenant.id))

        retrying_attempt = self.attempts.create(
            DeliveryAttempt(event_id=second_event.id, subscription_id=subscription.id),
            str(self.tenant.id),
        )
        retrying_attempt.mark_retrying(timezone.now() + timedelta(seconds=60))
        self.attempts.update(retrying_attempt, str(self.tenant.id))

        other_attempt = self.attempts.create(
            DeliveryAttempt(event_id=other_event.id, subscription_id=other_subscription.id),
            str(self.other_tenant.id),
        )
        other_attempt.mark_success(200, "ok")
        self.attempts.update(other_attempt, str(self.other_tenant.id))

        listed = self.attempts.list_by_tenant(str(self.tenant.id), status=DeliveryStatus.SUCCESS.value)
        filtered_by_event = self.attempts.list_by_tenant(
            str(self.tenant.id),
            event_id=second_event.id,
        )

        assert [attempt.id for attempt in listed] == [success_attempt.id]
        assert [attempt.id for attempt in filtered_by_event] == [retrying_attempt.id]


class DjangoTenantAPIKeyRepositoryTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Acme", slug="acme")
        self.repository = DjangoTenantAPIKeyRepository()

    def test_issue_and_authenticate_updates_last_used(self):
        issued = self.repository.issue_for_tenant(str(self.tenant.id), "Primary key")

        assert issued.raw_key.startswith("rdwh_")
        assert issued.tenant_id == str(self.tenant.id)

        authenticated = self.repository.authenticate(issued.raw_key)

        assert authenticated is not None
        assert authenticated.tenant_id == str(self.tenant.id)
        assert authenticated.key_prefix == issued.key_prefix
        assert TenantAPIKey.objects.get(id=issued.id).last_used_at is not None

    def test_authenticate_rejects_inactive_and_expired_keys(self):
        inactive = self.repository.issue_for_tenant(str(self.tenant.id), "Inactive key")
        inactive_model = TenantAPIKey.objects.get(id=inactive.id)
        inactive_model.is_active = False
        inactive_model.save(update_fields=["is_active", "updated_at"])

        expired = self.repository.issue_for_tenant(
            str(self.tenant.id),
            "Expired key",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        assert self.repository.authenticate(inactive.raw_key) is None
        assert self.repository.authenticate(expired.raw_key) is None
