import logging
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory

from config.logging import StructuredJSONFormatter
from data.models.models import (
    DeliveryAttempt,
    DeliveryStatus,
    OutboxMessage,
    OutboxStatus,
    Subscription,
    Tenant,
    WebhookEvent,
)
from data.repositories import DjangoTenantAPIKeyRepository
from interface.views.monitoring import HealthCheckView


class StubDegradedHealthService:
    def snapshot(self):
        return {
            "service": "rdash-webhook-service",
            "version": "v1",
            "environment": "test",
            "status": "degraded",
            "timestamp": timezone.now().isoformat(),
            "checks": {
                "database": {"status": "error"},
                "broker": {"status": "ok"},
            },
        }


class DegradedHealthCheckView(HealthCheckView):
    health_service_class = StubDegradedHealthService


class MonitoringEndpointTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.api_key_repository = DjangoTenantAPIKeyRepository()
        self.tenant = Tenant.objects.create(name="Acme", slug="acme")
        self.other_tenant = Tenant.objects.create(name="Globex", slug="globex")

    def _client_for_tenant(self, tenant: Tenant) -> APIClient:
        issued_key = self.api_key_repository.issue_for_tenant(str(tenant.id), f"{tenant.slug}-metrics")
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=issued_key.raw_key)
        return client

    def test_health_endpoint_allows_unauthenticated_requests(self):
        response = APIClient().get("/api/health/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["status"] == "ok"
        assert response.data["data"]["checks"]["database"]["status"] == "ok"
        assert response.data["data"]["checks"]["broker"]["status"] == "ok"

    def test_health_view_returns_503_for_degraded_snapshot(self):
        request = self.factory.get("/api/health/")

        response = DegradedHealthCheckView.as_view()(request)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["data"]["status"] == "degraded"

    def test_metrics_endpoint_requires_authentication(self):
        response = APIClient().get("/api/metrics/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_metrics_endpoint_returns_tenant_scoped_delivery_and_outbox_metrics(self):
        subscription = Subscription.objects.create(
            tenant=self.tenant,
            event_type="po.created",
            target_url="https://example.test/acme",
            secret_hash="secret-hash",
        )
        other_subscription = Subscription.objects.create(
            tenant=self.other_tenant,
            event_type="po.created",
            target_url="https://example.test/globex",
            secret_hash="secret-hash",
        )
        event_success = WebhookEvent.objects.create(
            tenant=self.tenant,
            event_type="po.created",
            payload={"id": "PO-1"},
            processed=True,
            processed_at=timezone.now(),
        )
        event_dead_letter = WebhookEvent.objects.create(
            tenant=self.tenant,
            event_type="po.created",
            payload={"id": "PO-2"},
            processed=False,
        )
        WebhookEvent.objects.filter(id=event_dead_letter.id).update(
            received_at=timezone.now() - timedelta(seconds=180)
        )
        event_retrying = WebhookEvent.objects.create(
            tenant=self.tenant,
            event_type="po.created",
            payload={"id": "PO-3"},
            processed=False,
        )
        other_event = WebhookEvent.objects.create(
            tenant=self.other_tenant,
            event_type="po.created",
            payload={"id": "PO-9"},
            processed=True,
            processed_at=timezone.now(),
        )
        DeliveryAttempt.objects.create(
            event=event_success,
            subscription=subscription,
            status=DeliveryStatus.SUCCESS,
            completed_at=timezone.now(),
        )
        DeliveryAttempt.objects.create(
            event=event_dead_letter,
            subscription=subscription,
            status=DeliveryStatus.DEAD_LETTER,
            completed_at=timezone.now(),
        )
        delayed_attempt = DeliveryAttempt.objects.create(
            event=event_retrying,
            subscription=subscription,
            status=DeliveryStatus.RETRYING,
            next_retry_at=timezone.now() + timedelta(seconds=30),
        )
        DeliveryAttempt.objects.filter(id=delayed_attempt.id).update(
            created_at=timezone.now() - timedelta(seconds=240)
        )
        DeliveryAttempt.objects.create(
            event=other_event,
            subscription=other_subscription,
            status=DeliveryStatus.SUCCESS,
            completed_at=timezone.now(),
        )
        OutboxMessage.objects.create(
            tenant=self.tenant,
            event=event_success,
            task_name="interface.tasks.fanout_event",
            status=OutboxStatus.PENDING,
        )
        OutboxMessage.objects.create(
            tenant=self.tenant,
            event=event_dead_letter,
            task_name="interface.tasks.replay_event",
            status=OutboxStatus.FAILED,
        )
        stale_outbox = OutboxMessage.objects.create(
            tenant=self.tenant,
            event=event_dead_letter,
            task_name="interface.tasks.requeue_event",
            status=OutboxStatus.IN_PROGRESS,
        )
        OutboxMessage.objects.filter(id=stale_outbox.id).update(
            available_at=timezone.now() - timedelta(seconds=300)
        )
        OutboxMessage.objects.create(
            tenant=self.other_tenant,
            event=other_event,
            task_name="interface.tasks.fanout_event",
            status=OutboxStatus.PUBLISHED,
        )

        response = self._client_for_tenant(self.tenant).get("/api/metrics/")

        assert response.status_code == status.HTTP_200_OK
        payload = response.data["data"]
        assert payload["tenant_id"] == str(self.tenant.id)
        assert payload["subscriptions"] == {"total": 1, "active": 1}
        assert payload["events"]["received"] == 3
        assert payload["events"]["processed"] == 1
        assert payload["events"]["pending"] == 2
        assert payload["events"]["oldest_pending_age_seconds"] >= 170
        assert payload["deliveries"]["total"] == 3
        assert payload["deliveries"]["completed"] == 2
        assert payload["deliveries"]["success_rate"] == 50.0
        assert payload["deliveries"]["failure_rate"] == 50.0
        assert payload["deliveries"]["lag_seconds"] >= 230
        assert payload["deliveries"]["by_status"]["success"] == 1
        assert payload["deliveries"]["by_status"]["dead_letter"] == 1
        assert payload["deliveries"]["by_status"]["retrying"] == 1
        assert payload["outbox"]["total"] == 3
        assert payload["outbox"]["backlog"] == 3
        assert payload["outbox"]["oldest_backlog_age_seconds"] >= 290
        assert payload["outbox"]["by_status"]["pending"] == 1
        assert payload["outbox"]["by_status"]["in_progress"] == 1
        assert payload["outbox"]["by_status"]["failed"] == 1


def test_structured_json_formatter_includes_context_fields():
    formatter = StructuredJSONFormatter()
    record = logging.makeLogRecord(
        {
            "name": "webhook.tasks",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "fanout_event_completed",
            "args": (),
            "event": "fanout_event_completed",
            "tenant_id": "tenant-1",
            "enqueued_count": 3,
            "component": "fanout_worker",
        }
    )

    payload = formatter.format(record)

    assert '"event":"fanout_event_completed"' in payload
    assert '"logger":"webhook.tasks"' in payload
    assert '"tenant_id":"tenant-1"' in payload
    assert '"component":"fanout_worker"' in payload
