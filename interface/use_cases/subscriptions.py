"""Subscription management use cases."""

import hashlib
import secrets
from dataclasses import dataclass
from typing import Mapping, Sequence

from domain.entities import Subscription
from domain.interfaces import SubscriptionRepository


SECRET_BYTES = 32


@dataclass(frozen=True)
class CreateSubscriptionResult:
    """Create result carrying the one-time raw secret."""

    subscription: Subscription
    secret: str


def generate_subscription_secret() -> str:
    """Generate a URL-safe subscription signing secret."""
    return secrets.token_urlsafe(SECRET_BYTES)


def hash_subscription_secret(secret: str) -> str:
    """Hash a subscription secret before persistence."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


class CreateSubscription:
    def __init__(self, repository: SubscriptionRepository):
        self.repository = repository

    def __call__(self, *, tenant_id: str, event_type: str, target_url: str, active: bool = True) -> CreateSubscriptionResult:
        raw_secret = generate_subscription_secret()
        subscription = Subscription(
            tenant_id=tenant_id,
            event_type=event_type,
            target_url=target_url,
            active=active,
            secret=hash_subscription_secret(raw_secret),
        )
        persisted = self.repository.create(subscription)
        return CreateSubscriptionResult(subscription=persisted, secret=raw_secret)


class ListSubscriptions:
    def __init__(self, repository: SubscriptionRepository):
        self.repository = repository

    def __call__(self, *, tenant_id: str) -> Sequence[Subscription]:
        return self.repository.list_by_tenant(tenant_id)


class GetSubscription:
    def __init__(self, repository: SubscriptionRepository):
        self.repository = repository

    def __call__(self, *, tenant_id: str, subscription_id: str) -> Subscription:
        return self.repository.get_by_id(subscription_id, tenant_id)


class PatchSubscription:
    def __init__(self, repository: SubscriptionRepository):
        self.repository = repository

    def __call__(
        self,
        *,
        tenant_id: str,
        subscription_id: str,
        changes: Mapping[str, object],
    ) -> Subscription:
        subscription = self.repository.get_by_id(subscription_id, tenant_id)

        if "event_type" in changes:
            subscription.event_type = str(changes["event_type"])
        if "target_url" in changes:
            subscription.target_url = str(changes["target_url"])
        if "active" in changes:
            if changes["active"]:
                subscription.activate()
            else:
                subscription.deactivate()

        return self.repository.update(subscription)


class DeleteSubscription:
    def __init__(self, repository: SubscriptionRepository):
        self.repository = repository

    def __call__(self, *, tenant_id: str, subscription_id: str) -> None:
        self.repository.delete(subscription_id, tenant_id)
