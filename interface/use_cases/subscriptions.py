"""Subscription management use cases."""

import logging
import secrets
from dataclasses import dataclass
from typing import Mapping, Sequence

from domain.entities import Subscription
from domain.interfaces import SubscriptionRepository


SECRET_BYTES = 32

logger = logging.getLogger("webhook.subscriptions")


@dataclass(frozen=True)
class CreateSubscriptionResult:
    """Create result carrying the one-time raw secret."""

    subscription: Subscription
    secret: str


def generate_subscription_secret() -> str:
    """Generate a URL-safe subscription signing secret."""
    return secrets.token_urlsafe(SECRET_BYTES)

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
            secret=raw_secret,
        )
        persisted = self.repository.create(subscription)
        logger.info(
            "subscription_created",
            extra={
                "event": "subscription_created",
                "component": "subscription_management",
                "tenant_id": tenant_id,
                "subscription_id": persisted.id,
                "event_type": persisted.event_type,
                "target_url": persisted.target_url,
                "active": persisted.active,
            },
        )
        return CreateSubscriptionResult(subscription=persisted, secret=raw_secret)


class ListSubscriptions:
    def __init__(self, repository: SubscriptionRepository):
        self.repository = repository

    def __call__(self, *, tenant_id: str) -> Sequence[Subscription]:
        subscriptions = self.repository.list_by_tenant(tenant_id)
        logger.debug(
            "subscriptions_listed",
            extra={
                "event": "subscriptions_listed",
                "component": "subscription_management",
                "tenant_id": tenant_id,
                "count": len(subscriptions),
            },
        )
        return subscriptions


class GetSubscription:
    def __init__(self, repository: SubscriptionRepository):
        self.repository = repository

    def __call__(self, *, tenant_id: str, subscription_id: str) -> Subscription:
        subscription = self.repository.get_by_id(subscription_id, tenant_id)
        logger.debug(
            "subscription_retrieved",
            extra={
                "event": "subscription_retrieved",
                "component": "subscription_management",
                "tenant_id": tenant_id,
                "subscription_id": subscription_id,
            },
        )
        return subscription


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
        changed_fields = sorted(str(key) for key in changes.keys())

        if "event_type" in changes:
            subscription.event_type = str(changes["event_type"])
        if "target_url" in changes:
            subscription.target_url = str(changes["target_url"])
        if "active" in changes:
            if changes["active"]:
                subscription.activate()
            else:
                subscription.deactivate()

        updated_subscription = self.repository.update(subscription)
        logger.info(
            "subscription_updated",
            extra={
                "event": "subscription_updated",
                "component": "subscription_management",
                "tenant_id": tenant_id,
                "subscription_id": subscription_id,
                "changed_fields": changed_fields,
                "active": updated_subscription.active,
            },
        )
        return updated_subscription


class DeleteSubscription:
    def __init__(self, repository: SubscriptionRepository):
        self.repository = repository

    def __call__(self, *, tenant_id: str, subscription_id: str) -> None:
        self.repository.delete(subscription_id, tenant_id)
        logger.info(
            "subscription_deleted",
            extra={
                "event": "subscription_deleted",
                "component": "subscription_management",
                "tenant_id": tenant_id,
                "subscription_id": subscription_id,
            },
        )
