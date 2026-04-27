from types import SimpleNamespace

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.test import APIRequestFactory, force_authenticate

from data.models.models import Subscription as SubscriptionModel, Tenant
from data.repositories import DjangoTenantAPIKeyRepository
from domain.exceptions import DuplicateSubscriptionError
from domain.entities import Subscription
from interface.views.subscriptions import SubscriptionCollectionView, SubscriptionDetailView


class InMemorySubscriptionRepository:
    subscriptions = {}

    def create(self, subscription):
        self.subscriptions[(subscription.tenant_id, subscription.id)] = subscription
        return subscription

    def get_by_id(self, subscription_id, tenant_id):
        return self.subscriptions[(tenant_id, subscription_id)]

    def list_by_tenant(self, tenant_id):
        return [
            subscription
            for (stored_tenant_id, _), subscription in self.subscriptions.items()
            if stored_tenant_id == tenant_id
        ]

    def list_active_by_tenant(self, tenant_id):
        return [subscription for subscription in self.list_by_tenant(tenant_id) if subscription.active]

    def update(self, subscription):
        self.subscriptions[(subscription.tenant_id, subscription.id)] = subscription
        return subscription

    def delete(self, subscription_id, tenant_id):
        del self.subscriptions[(tenant_id, subscription_id)]


class SubscriptionCollectionTestView(SubscriptionCollectionView):
    repository_class = InMemorySubscriptionRepository


class SubscriptionDetailTestView(SubscriptionDetailView):
    repository_class = InMemorySubscriptionRepository


class DuplicateSubscriptionRepository(InMemorySubscriptionRepository):
    def create(self, subscription):
        raise DuplicateSubscriptionError(
            context={
                "tenant_id": subscription.tenant_id,
                "event_type": subscription.event_type,
                "target_url": subscription.target_url,
            }
        )

    def get_by_id(self, subscription_id, tenant_id):
        return Subscription(
            id=subscription_id,
            tenant_id=tenant_id,
            event_type="po.created",
            target_url="https://example.test/webhook",
            secret="stored-secret-hash",
        )

    def update(self, subscription):
        raise DuplicateSubscriptionError(
            context={
                "tenant_id": subscription.tenant_id,
                "event_type": subscription.event_type,
                "target_url": subscription.target_url,
            }
        )


class DuplicateSubscriptionCollectionView(SubscriptionCollectionView):
    repository_class = DuplicateSubscriptionRepository


class DuplicateSubscriptionDetailView(SubscriptionDetailView):
    repository_class = DuplicateSubscriptionRepository


def authenticated_request(method, path, data=None):
    factory = APIRequestFactory()
    request = getattr(factory, method)(path, data=data or {}, format="json")
    force_authenticate(
        request,
        user=SimpleNamespace(is_authenticated=True, tenant_id="tenant-1"),
    )
    return request


def test_create_subscription_returns_secret_once_and_uses_principal_tenant():
    InMemorySubscriptionRepository.subscriptions = {}
    view = SubscriptionCollectionTestView.as_view()
    request = authenticated_request(
        "post",
        "/api/subscriptions/",
        {"event_type": "po.created", "target_url": "https://example.test/webhook"},
    )

    response = view(request)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["data"]["tenant_id"] == "tenant-1"
    assert response.data["data"]["secret"]


def test_list_subscription_does_not_return_secret():
    InMemorySubscriptionRepository.subscriptions = {}
    repository = InMemorySubscriptionRepository()
    repository.create(
        Subscription(
            id="11111111-1111-1111-1111-111111111111",
            tenant_id="tenant-1",
            event_type="po.created",
            target_url="https://example.test/webhook",
            secret="stored-secret-hash",
        )
    )
    view = SubscriptionCollectionTestView.as_view()
    request = authenticated_request("get", "/api/subscriptions/")

    response = view(request)

    assert response.status_code == status.HTTP_200_OK
    assert "secret" not in response.data["data"][0]


def test_patch_subscription_can_toggle_active_without_secret():
    InMemorySubscriptionRepository.subscriptions = {}
    subscription_id = "11111111-1111-1111-1111-111111111111"
    repository = InMemorySubscriptionRepository()
    repository.create(
        Subscription(
            id=subscription_id,
            tenant_id="tenant-1",
            event_type="po.created",
            target_url="https://example.test/webhook",
            secret="stored-secret-hash",
        )
    )
    view = SubscriptionDetailTestView.as_view()
    request = authenticated_request(
        "patch",
        f"/api/subscriptions/{subscription_id}/",
        {"active": False},
    )

    response = view(request, subscription_id=subscription_id)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["data"]["active"] is False
    assert "secret" not in response.data["data"]


def test_create_subscription_rejects_body_tenant_id():
    view = SubscriptionCollectionTestView.as_view()
    request = authenticated_request(
        "post",
        "/api/subscriptions/",
        {
            "tenant_id": "attacker",
            "event_type": "po.created",
            "target_url": "https://example.test/webhook",
        },
    )

    response = view(request)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["error"]["code"] == "validation_error"
    assert response.data["error"]["message"] == "Request validation failed."
    assert response.data["error"]["context"]["details"]["non_field_errors"][0] == {
        "message": "tenant_id must come from authentication.",
        "code": "invalid",
    }


def test_create_subscription_returns_conflict_json_for_duplicate_subscription():
    view = DuplicateSubscriptionCollectionView.as_view()
    request = authenticated_request(
        "post",
        "/api/subscriptions/",
        {
            "event_type": "po.created",
            "target_url": "https://example.test/webhook",
        },
    )

    response = view(request)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["error"]["code"] == "duplicate_subscription"
    assert response.data["error"]["message"] == (
        "A subscription already exists for this event type and target URL."
    )


def test_patch_subscription_returns_conflict_json_for_duplicate_subscription():
    subscription_id = "11111111-1111-1111-1111-111111111111"
    view = DuplicateSubscriptionDetailView.as_view()
    request = authenticated_request(
        "patch",
        f"/api/subscriptions/{subscription_id}/",
        {"target_url": "https://example.test/other"},
    )

    response = view(request, subscription_id=subscription_id)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["error"]["code"] == "duplicate_subscription"


class SubscriptionEndpointTests(TestCase):
    def setUp(self):
        self.api_key_repository = DjangoTenantAPIKeyRepository()
        self.tenant = Tenant.objects.create(
            id="11111111-1111-1111-1111-111111111111",
            name="Acme",
            slug="acme",
        )
        issued_key = self.api_key_repository.issue_for_tenant(str(self.tenant.id), "subscriptions")
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=issued_key.raw_key)

    def test_duplicate_subscription_returns_conflict_json_with_real_repository(self):
        SubscriptionModel.objects.create(
            tenant=self.tenant,
            event_type="invoice.paid",
            target_url="http://localhost:8000/api/health/",
            secret_hash="secret-hash",
            secret_encrypted="encrypted-secret",
        )

        response = self.client.post(
            "/api/subscriptions/",
            {
                "event_type": "invoice.paid",
                "target_url": "http://localhost:8000/api/health/",
                "active": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error"]["code"] == "duplicate_subscription"
        assert response.data["error"]["message"] == (
            "A subscription already exists for this event type and target URL."
        )
        assert response.data["error"]["context"] == {
            "tenant_id": str(self.tenant.id),
            "event_type": "invoice.paid",
            "target_url": "http://localhost:8000/api/health/",
        }
