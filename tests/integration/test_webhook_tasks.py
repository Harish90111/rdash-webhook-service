from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from data.models.models import DeliveryAttempt, DeliveryStatus, Subscription, Tenant, WebhookEvent
from interface.tasks import webhooks as webhook_tasks
from interface.use_cases.delivery_tasks import delivery_task_id, tenant_queue_name


class DeliveryRetryRecoveryTaskTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Acme", slug="acme")
        self.subscription = Subscription.objects.create(
            tenant=self.tenant,
            event_type="po.*",
            target_url="https://example.test/acme",
            secret_hash="secret-hash",
        )

    def test_recover_delivery_retries_enqueues_only_overdue_retrying_attempts(self):
        overdue_event = WebhookEvent.objects.create(
            tenant=self.tenant,
            event_type="po.created",
            payload={"id": "PO-1"},
        )
        future_event = WebhookEvent.objects.create(
            tenant=self.tenant,
            event_type="po.updated",
            payload={"id": "PO-2"},
        )
        overdue_attempt = DeliveryAttempt.objects.create(
            event=overdue_event,
            subscription=self.subscription,
            status=DeliveryStatus.RETRYING,
            next_retry_at=timezone.now() - timedelta(minutes=5),
        )
        DeliveryAttempt.objects.create(
            event=future_event,
            subscription=self.subscription,
            status=DeliveryStatus.RETRYING,
            next_retry_at=timezone.now() + timedelta(minutes=5),
        )

        with patch.object(webhook_tasks.deliver_webhook, "apply_async") as apply_async:
            webhook_tasks.recover_delivery_retries.run(limit=10)

        apply_async.assert_called_once_with(
            kwargs={"attempt_id": str(overdue_attempt.id), "tenant_id": str(self.tenant.id)},
            queue=tenant_queue_name(str(self.tenant.id)),
            task_id=delivery_task_id(str(overdue_attempt.id)),
        )
