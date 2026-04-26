import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from data.models.models import DeliveryAttempt, OutboxMessage, OutboxStatus, Tenant, WebhookEvent
from data.repositories import DjangoTenantAPIKeyRepository
from domain.interfaces import HttpResponse
from interface.tasks import webhooks as webhook_tasks


class ApplyAsyncRecorder:
    """Capture Celery scheduling requests during synchronous task execution."""

    def __init__(self, *, fail_on_call=None):
        self.fail_on_call = fail_on_call
        self.calls = []

    def __call__(self, args=None, kwargs=None, **options):
        call = {
            "args": tuple(args or ()),
            "kwargs": dict(kwargs or {}),
            "options": dict(options),
        }
        self.calls.append(call)
        if self.fail_on_call and len(self.calls) == self.fail_on_call:
            raise RuntimeError("Simulated task enqueue failure.")
        return SimpleNamespace(id=options.get("task_id"))


class RecordingGateway:
    """Small HTTP gateway stub that records outbound webhook requests."""

    def __init__(self, *, status_code=202, body="accepted"):
        self.status_code = status_code
        self.body = body
        self.requests = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def post(self, request):
        self.requests.append(request)
        return HttpResponse(
            status_code=self.status_code,
            body=self.body,
            headers={"x-mock-gateway": "true"},
            elapsed_seconds=0.01,
        )


@override_settings(
    WEBHOOK_SECRET_ENCRYPTION_KEY="e2e-secret-encryption-key",
    WEBHOOK_RETRY_JITTER=0.0,
)
class WebhookDeliveryFlowE2ETests(TestCase):
    def setUp(self):
        self.api_key_repository = DjangoTenantAPIKeyRepository()

    def _auth_client(self, tenant: Tenant) -> APIClient:
        issued_key = self.api_key_repository.issue_for_tenant(
            str(tenant.id),
            f"{tenant.slug}-e2e",
        )
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=issued_key.raw_key)
        return client

    def _create_subscription(self, client: APIClient, *, event_type: str, target_url: str):
        response = client.post(
            "/api/subscriptions/",
            {"event_type": event_type, "target_url": target_url},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        return response.data["data"]

    def _ingest_event(
        self,
        client: APIClient,
        *,
        event_type: str,
        payload: dict,
        idempotency_key: str,
    ):
        response = client.post(
            "/api/events/",
            {
                "event_type": event_type,
                "payload": payload,
                "idempotency_key": idempotency_key,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        return response

    def _dispatch_outbox(self):
        recorder = ApplyAsyncRecorder()
        with patch.object(webhook_tasks.fanout_event, "apply_async", side_effect=recorder):
            webhook_tasks.dispatch_outbox_batch.run(limit=100, locked_by="e2e-dispatcher")
        return recorder.calls

    def _fan_out(self, *, event_id: str, tenant_id: str):
        recorder = ApplyAsyncRecorder()
        with patch.object(webhook_tasks.deliver_webhook, "apply_async", side_effect=recorder):
            webhook_tasks.fanout_event.run(event_id=event_id, tenant_id=tenant_id)
        return recorder.calls

    def _deliver(self, delivery_calls, gateway: RecordingGateway):
        with patch.object(webhook_tasks, "HttpxWebhookGateway", return_value=gateway):
            with patch.object(webhook_tasks.deliver_webhook, "apply_async") as retry_enqueue:
                for call in delivery_calls:
                    webhook_tasks.deliver_webhook.run(**call["kwargs"])
        return retry_enqueue

    def test_full_ingestion_to_delivery_path_matches_wildcard_subscription(self):
        tenant = Tenant.objects.create(name="Acme", slug="acme")
        client = self._auth_client(tenant)
        subscription = self._create_subscription(
            client,
            event_type="po.*",
            target_url="https://example.test/acme",
        )

        response = self._ingest_event(
            client,
            event_type="po.created",
            payload={"id": "PO-1"},
            idempotency_key="event-1",
        )
        event_id = response.data["data"]["id"]

        outbox_message = OutboxMessage.objects.get(event_id=event_id)
        assert outbox_message.status == OutboxStatus.PENDING

        fanout_calls = self._dispatch_outbox()

        assert len(fanout_calls) == 1
        assert fanout_calls[0]["kwargs"]["event_id"] == event_id
        assert fanout_calls[0]["kwargs"]["tenant_id"] == str(tenant.id)

        outbox_message.refresh_from_db()
        assert outbox_message.status == OutboxStatus.PUBLISHED

        delivery_calls = self._fan_out(event_id=event_id, tenant_id=str(tenant.id))

        assert len(delivery_calls) == 1

        gateway = RecordingGateway()
        retry_enqueue = self._deliver(delivery_calls, gateway)

        attempt = DeliveryAttempt.objects.get(event_id=event_id)
        event = WebhookEvent.objects.get(id=event_id)
        request = gateway.requests[0]
        delivered_body = json.loads(request.body)

        assert str(attempt.subscription_id) == subscription["id"]
        assert attempt.status == "success"
        assert event.processed is True
        assert len(gateway.requests) == 1
        assert retry_enqueue.call_count == 0
        assert request.url == "https://example.test/acme"
        assert request.headers["X-Webhook-Event"] == event_id
        assert request.headers["X-Webhook-Event-Type"] == "po.created"
        assert request.headers["X-Signature-Version"] == "v1"
        assert "X-Signature" in request.headers
        assert "X-Webhook-Timestamp" in request.headers
        assert delivered_body["event_type"] == "po.created"
        assert delivered_body["tenant_id"] == str(tenant.id)

    def test_fanout_replay_after_crash_does_not_duplicate_attempt_rows(self):
        tenant = Tenant.objects.create(name="Acme", slug="acme")
        client = self._auth_client(tenant)
        self._create_subscription(
            client,
            event_type="po.*",
            target_url="https://example.test/acme/orders",
        )
        self._create_subscription(
            client,
            event_type="po.created",
            target_url="https://example.test/acme/created",
        )

        response = self._ingest_event(
            client,
            event_type="po.created",
            payload={"id": "PO-2"},
            idempotency_key="event-2",
        )
        event_id = response.data["data"]["id"]
        dispatch_calls = self._dispatch_outbox()

        first_pass = ApplyAsyncRecorder(fail_on_call=2)
        with patch.object(webhook_tasks.deliver_webhook, "apply_async", side_effect=first_pass):
            with self.assertRaises(RuntimeError):
                webhook_tasks.fanout_event.run(**dispatch_calls[0]["kwargs"])

        assert DeliveryAttempt.objects.filter(event_id=event_id).count() == 2
        assert WebhookEvent.objects.get(id=event_id).processed is False

        second_pass = self._fan_out(**dispatch_calls[0]["kwargs"])

        assert DeliveryAttempt.objects.filter(event_id=event_id).count() == 2
        assert WebhookEvent.objects.get(id=event_id).processed is True
        assert len(second_pass) == 2

        attempt_ids = {
            str(attempt_id)
            for attempt_id in DeliveryAttempt.objects.filter(event_id=event_id).values_list(
                "id",
                flat=True,
            )
        }
        replayed_attempt_ids = {call["kwargs"]["attempt_id"] for call in second_pass}
        assert replayed_attempt_ids == attempt_ids

    def test_duplicate_delivery_messages_only_send_one_http_request(self):
        tenant = Tenant.objects.create(name="Acme", slug="acme")
        client = self._auth_client(tenant)
        self._create_subscription(
            client,
            event_type="po.created",
            target_url="https://example.test/acme/orders",
        )

        response = self._ingest_event(
            client,
            event_type="po.created",
            payload={"id": "PO-3"},
            idempotency_key="event-3",
        )
        event_id = response.data["data"]["id"]

        dispatch_calls = self._dispatch_outbox()
        delivery_calls = self._fan_out(**dispatch_calls[0]["kwargs"])

        gateway = RecordingGateway()
        retry_enqueue = self._deliver(delivery_calls * 2, gateway)
        attempt = DeliveryAttempt.objects.get(event_id=event_id)

        assert attempt.status == "success"
        assert len(gateway.requests) == 1
        assert retry_enqueue.call_count == 0

    def test_end_to_end_flow_is_tenant_isolated(self):
        tenant_a = Tenant.objects.create(name="Acme", slug="acme")
        tenant_b = Tenant.objects.create(name="Globex", slug="globex")
        client_a = self._auth_client(tenant_a)
        client_b = self._auth_client(tenant_b)
        subscription_a = self._create_subscription(
            client_a,
            event_type="po.*",
            target_url="https://example.test/acme",
        )
        self._create_subscription(
            client_b,
            event_type="po.*",
            target_url="https://example.test/globex",
        )

        response = self._ingest_event(
            client_a,
            event_type="po.created",
            payload={"id": "PO-4"},
            idempotency_key="event-4",
        )
        event_id = response.data["data"]["id"]

        dispatch_calls = self._dispatch_outbox()

        assert len(dispatch_calls) == 1
        assert dispatch_calls[0]["kwargs"]["tenant_id"] == str(tenant_a.id)
        assert OutboxMessage.objects.filter(tenant_id=tenant_b.id).count() == 0
        assert WebhookEvent.objects.filter(tenant_id=tenant_b.id).count() == 0

        delivery_calls = self._fan_out(**dispatch_calls[0]["kwargs"])
        gateway = RecordingGateway()
        self._deliver(delivery_calls, gateway)

        assert DeliveryAttempt.objects.filter(subscription__tenant_id=tenant_b.id).count() == 0
        assert DeliveryAttempt.objects.filter(subscription__tenant_id=tenant_a.id).count() == 1
        assert str(DeliveryAttempt.objects.get(event_id=event_id).subscription_id) == subscription_a["id"]
        assert [request.url for request in gateway.requests] == ["https://example.test/acme"]
