from types import SimpleNamespace

from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

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
