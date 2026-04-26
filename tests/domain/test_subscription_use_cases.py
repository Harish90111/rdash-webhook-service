from domain.entities import Subscription
from interface.use_cases.subscriptions import (
    CreateSubscription,
    PatchSubscription,
    hash_subscription_secret,
)


class MemorySubscriptionRepository:
    def __init__(self):
        self.subscriptions = {}

    def create(self, subscription):
        self.subscriptions[(subscription.tenant_id, subscription.id)] = subscription
        return subscription

    def get_by_id(self, subscription_id, tenant_id):
        return self.subscriptions[(tenant_id, subscription_id)]

    def list_by_tenant(self, tenant_id):
        return []

    def list_active_by_tenant(self, tenant_id):
        return []

    def update(self, subscription):
        self.subscriptions[(subscription.tenant_id, subscription.id)] = subscription
        return subscription

    def delete(self, subscription_id, tenant_id):
        del self.subscriptions[(tenant_id, subscription_id)]


def test_create_subscription_hashes_secret_for_persistence():
    repository = MemorySubscriptionRepository()
    result = CreateSubscription(repository)(
        tenant_id="tenant-1",
        event_type="po.created",
        target_url="https://example.test/webhook",
    )

    assert result.secret
    assert result.subscription.secret == hash_subscription_secret(result.secret)
    assert result.subscription.secret != result.secret


def test_patch_subscription_updates_allowed_fields():
    repository = MemorySubscriptionRepository()
    subscription = repository.create(
        Subscription(
            id="11111111-1111-1111-1111-111111111111",
            tenant_id="tenant-1",
            event_type="po.created",
            target_url="https://example.test/webhook",
            secret="stored-secret-hash",
        )
    )

    patched = PatchSubscription(repository)(
        tenant_id="tenant-1",
        subscription_id=subscription.id,
        changes={"event_type": "po.approved", "active": False},
    )

    assert patched.event_type == "po.approved"
    assert patched.active is False
