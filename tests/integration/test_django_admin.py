from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from data.models.models import (
    CircuitBreakerState,
    DeliveryAttempt,
    OutboxMessage,
    Subscription,
    Tenant,
    TenantAPIKey,
    WebhookEvent,
)


class DjangoAdminTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin_user = user_model.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="admin",
        )
        self.client.force_login(self.admin_user)
        self.tenant = Tenant.objects.create(name="Acme Corp", slug="acme-corp")

    def test_webhook_models_are_registered_with_admin_site(self):
        registered_models = set(admin.site._registry)

        assert Tenant in registered_models
        assert TenantAPIKey in registered_models
        assert Subscription in registered_models
        assert WebhookEvent in registered_models
        assert DeliveryAttempt in registered_models
        assert OutboxMessage in registered_models
        assert CircuitBreakerState in registered_models

    def test_admin_can_create_subscription_with_plain_secret(self):
        response = self.client.post(
            reverse("admin:webhook_data_subscription_add"),
            data={
                "tenant": str(self.tenant.id),
                "event_type": "po.created",
                "target_url": "https://example.test/webhooks/orders",
                "active": "on",
                "signing_secret": "super-secret-value",
                "_save": "Save",
            },
        )

        assert response.status_code == 302
        subscription = Subscription.objects.get()
        assert subscription.secret_hash
        assert subscription.secret_hash != "super-secret-value"
        assert subscription.secret_encrypted
        assert subscription.secret_encrypted != "super-secret-value"

    def test_admin_can_issue_api_key_for_tenant(self):
        response = self.client.post(
            reverse("admin:webhook_data_tenantapikey_add"),
            data={
                "tenant": str(self.tenant.id),
                "name": "Primary integration key",
                "expires_at_0": "",
                "expires_at_1": "",
                "_save": "Save",
            },
            follow=True,
        )

        assert response.status_code == 200
        api_key = TenantAPIKey.objects.get()
        assert api_key.name == "Primary integration key"
        assert api_key.key_prefix
        assert api_key.key_hash
        messages = list(response.context["messages"])
        assert any("Raw API key for Primary integration key:" in str(message) for message in messages)

    def test_webhook_event_changelist_renders(self):
        WebhookEvent.objects.create(
            tenant=self.tenant,
            event_type="po.created",
            payload={"id": "PO-1"},
            idempotency_key="po-created-1",
        )

        response = self.client.get(reverse("admin:webhook_data_webhookevent_changelist"))

        assert response.status_code == 200
