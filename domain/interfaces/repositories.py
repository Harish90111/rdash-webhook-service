"""Repository protocols used by application use cases."""

from __future__ import annotations

from typing import Optional, Protocol, Sequence, runtime_checkable

from domain.entities import DeliveryAttempt, Subscription, WebhookEvent


@runtime_checkable
class SubscriptionRepository(Protocol):
    """Persistence contract for webhook subscriptions."""

    def create(self, subscription: Subscription) -> Subscription:
        ...

    def get_by_id(self, subscription_id: str, tenant_id: str) -> Subscription:
        ...

    def list_by_tenant(self, tenant_id: str) -> Sequence[Subscription]:
        ...

    def list_active_by_tenant(self, tenant_id: str) -> Sequence[Subscription]:
        ...

    def update(self, subscription: Subscription) -> Subscription:
        ...

    def delete(self, subscription_id: str, tenant_id: str) -> None:
        ...


@runtime_checkable
class EventRepository(Protocol):
    """Persistence contract for incoming webhook events."""

    def create(self, event: WebhookEvent) -> WebhookEvent:
        ...

    def get_by_id(self, event_id: str, tenant_id: str) -> WebhookEvent:
        ...

    def get_by_idempotency_key(
        self,
        tenant_id: str,
        idempotency_key: str,
    ) -> Optional[WebhookEvent]:
        ...

    def mark_processed(self, event_id: str, tenant_id: str) -> None:
        ...


@runtime_checkable
class DeliveryAttemptRepository(Protocol):
    """
    Persistence contract for delivery attempt state.

    Delivery attempts are tenant-scoped through their event and subscription.
    The tenant_id parameter is deliberately part of read/update methods so data
    repositories cannot accidentally expose cross-tenant delivery state.
    """

    def create(self, attempt: DeliveryAttempt, tenant_id: str) -> DeliveryAttempt:
        ...

    def get_by_id(self, attempt_id: str, tenant_id: str) -> DeliveryAttempt:
        ...

    def claim_for_delivery(self, attempt_id: str, tenant_id: str) -> Optional[DeliveryAttempt]:
        """
        Atomically claim a delivery attempt for worker execution.

        Returns None when the attempt is already terminal, already in progress,
        or waiting for a future retry window.
        """
        ...

    def find_by_event_and_subscription(
        self,
        event_id: str,
        subscription_id: str,
        tenant_id: str,
    ) -> Optional[DeliveryAttempt]:
        ...

    def list_for_event(self, event_id: str, tenant_id: str) -> Sequence[DeliveryAttempt]:
        ...

    def list_by_tenant(
        self,
        tenant_id: str,
        *,
        status: Optional[str] = None,
        event_id: Optional[str] = None,
        subscription_id: Optional[str] = None,
    ) -> Sequence[DeliveryAttempt]:
        ...

    def list_overdue_retrying(
        self,
        *,
        limit: int,
    ) -> Sequence[tuple[DeliveryAttempt, str]]:
        """
        Return retrying attempts whose retry window has elapsed.

        Each returned item includes the tenant id needed to safely re-enqueue
        the attempt onto its tenant-scoped delivery queue.
        """
        ...

    def update(self, attempt: DeliveryAttempt, tenant_id: str) -> DeliveryAttempt:
        ...
