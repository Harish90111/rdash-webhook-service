from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from data.models.models import DeliveryAttempt, DeliveryStatus, Subscription, Tenant, WebhookEvent
from data.repositories import DjangoTenantAPIKeyRepository


class DeliveryListingEndpointTests(TestCase):
    def setUp(self):
        self.api_key_repository = DjangoTenantAPIKeyRepository()
        self.tenant = Tenant.objects.create(name="Acme", slug="acme")
        self.other_tenant = Tenant.objects.create(name="Globex", slug="globex")

    def _client_for_tenant(self, tenant: Tenant) -> APIClient:
        issued_key = self.api_key_repository.issue_for_tenant(str(tenant.id), f"{tenant.slug}-deliveries")
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=issued_key.raw_key)
        return client

    def test_delivery_listing_requires_authentication(self):
        response = APIClient().get("/api/deliveries/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["error"]["code"] == "authentication_required"

    def test_delivery_listing_is_tenant_scoped_paginated_and_filterable_by_status(self):
        subscription = Subscription.objects.create(
            tenant=self.tenant,
            event_type="po.*",
            target_url="https://example.test/acme",
            secret_hash="secret-hash",
        )
        other_subscription = Subscription.objects.create(
            tenant=self.other_tenant,
            event_type="po.*",
            target_url="https://example.test/globex",
            secret_hash="secret-hash",
        )
        older_event = WebhookEvent.objects.create(
            tenant=self.tenant,
            event_type="po.created",
            payload={"id": "PO-1"},
            processed=True,
            processed_at=timezone.now(),
        )
        newer_event = WebhookEvent.objects.create(
            tenant=self.tenant,
            event_type="po.updated",
            payload={"id": "PO-2"},
            processed=True,
            processed_at=timezone.now(),
        )
        other_event = WebhookEvent.objects.create(
            tenant=self.other_tenant,
            event_type="po.created",
            payload={"id": "PO-9"},
            processed=True,
            processed_at=timezone.now(),
        )

        older_attempt = DeliveryAttempt.objects.create(
            event=older_event,
            subscription=subscription,
            status=DeliveryStatus.SUCCESS,
            completed_at=timezone.now(),
        )
        newer_attempt = DeliveryAttempt.objects.create(
            event=newer_event,
            subscription=subscription,
            status=DeliveryStatus.RETRYING,
            next_retry_at=timezone.now(),
        )
        DeliveryAttempt.objects.create(
            event=other_event,
            subscription=other_subscription,
            status=DeliveryStatus.SUCCESS,
            completed_at=timezone.now(),
        )

        paginated_response = self._client_for_tenant(self.tenant).get("/api/deliveries/?page_size=1")

        assert paginated_response.status_code == status.HTTP_200_OK
        assert len(paginated_response.data["data"]) == 1
        assert paginated_response.data["data"][0]["id"] in {
            str(older_attempt.id),
            str(newer_attempt.id),
        }
        assert paginated_response.data["meta"]["pagination"]["count"] == 2
        assert paginated_response.data["meta"]["pagination"]["page"] == 1
        assert paginated_response.data["meta"]["pagination"]["page_size"] == 1
        assert paginated_response.data["meta"]["pagination"]["total_pages"] == 2
        assert paginated_response.data["meta"]["pagination"]["next"] is not None
        assert paginated_response.data["meta"]["pagination"]["previous"] is None

        filtered_response = self._client_for_tenant(self.tenant).get(
            f"/api/deliveries/?status=success&subscription_id={subscription.id}"
        )

        assert filtered_response.status_code == status.HTTP_200_OK
        assert [item["id"] for item in filtered_response.data["data"]] == [str(older_attempt.id)]
        assert filtered_response.data["meta"]["pagination"]["count"] == 1

    def test_delivery_listing_rejects_invalid_status_filter(self):
        response = self._client_for_tenant(self.tenant).get("/api/deliveries/?status=unknown")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "validation_error"


class DeliveryRetryEndpointTests(TestCase):
    def setUp(self):
        self.api_key_repository = DjangoTenantAPIKeyRepository()
        self.tenant = Tenant.objects.create(name="Acme", slug="acme")
        self.other_tenant = Tenant.objects.create(name="Globex", slug="globex")

    def _client_for_tenant(self, tenant: Tenant) -> APIClient:
        issued_key = self.api_key_repository.issue_for_tenant(str(tenant.id), f"{tenant.slug}-deliveries")
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=issued_key.raw_key)
        return client

    def test_delivery_retry_requires_authentication(self):
        response = APIClient().post(
            "/api/deliveries/11111111-1111-1111-1111-111111111111/retry/",
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["error"]["code"] == "authentication_required"

    def test_delivery_retry_queues_dead_letter_attempt_immediately(self):
        subscription = Subscription.objects.create(
            tenant=self.tenant,
            event_type="po.*",
            target_url="https://example.test/acme",
            secret_hash="secret-hash",
        )
        event = WebhookEvent.objects.create(
            tenant=self.tenant,
            event_type="po.created",
            payload={"id": "PO-1"},
            processed=True,
            processed_at=timezone.now(),
        )
        attempt = DeliveryAttempt.objects.create(
            event=event,
            subscription=subscription,
            status=DeliveryStatus.DEAD_LETTER,
            attempt_number=5,
            error_message="endpoint unavailable",
            completed_at=timezone.now(),
        )

        with patch("interface.views.deliveries.deliver_webhook.apply_async") as apply_async:
            response = self._client_for_tenant(self.tenant).post(
                f"/api/deliveries/{attempt.id}/retry/",
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data["data"]["id"] == str(attempt.id)
        assert response.data["data"]["status"] == DeliveryStatus.RETRYING.value
        assert response.data["meta"]["queued"] is True
        apply_async.assert_called_once()
        attempt.refresh_from_db()
        assert attempt.status == DeliveryStatus.RETRYING
        assert attempt.completed_at is None
        assert attempt.next_retry_at is not None

    def test_delivery_retry_is_tenant_scoped(self):
        subscription = Subscription.objects.create(
            tenant=self.other_tenant,
            event_type="po.*",
            target_url="https://example.test/globex",
            secret_hash="secret-hash",
        )
        event = WebhookEvent.objects.create(
            tenant=self.other_tenant,
            event_type="po.created",
            payload={"id": "PO-2"},
        )
        attempt = DeliveryAttempt.objects.create(
            event=event,
            subscription=subscription,
            status=DeliveryStatus.DEAD_LETTER,
            completed_at=timezone.now(),
        )

        response = self._client_for_tenant(self.tenant).post(
            f"/api/deliveries/{attempt.id}/retry/",
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delivery_retry_rejects_non_retryable_status(self):
        subscription = Subscription.objects.create(
            tenant=self.tenant,
            event_type="po.*",
            target_url="https://example.test/acme",
            secret_hash="secret-hash",
        )
        event = WebhookEvent.objects.create(
            tenant=self.tenant,
            event_type="po.created",
            payload={"id": "PO-3"},
        )
        attempt = DeliveryAttempt.objects.create(
            event=event,
            subscription=subscription,
            status=DeliveryStatus.SUCCESS,
            completed_at=timezone.now(),
        )

        response = self._client_for_tenant(self.tenant).post(
            f"/api/deliveries/{attempt.id}/retry/",
            format="json",
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error"]["code"] == "delivery_retry_not_allowed"
