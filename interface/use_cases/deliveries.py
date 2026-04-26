"""Read-oriented delivery attempt use cases."""

from typing import Optional, Sequence

from domain.entities import DeliveryAttempt
from domain.interfaces import DeliveryAttemptRepository


class ListDeliveryAttempts:
    """List tenant-scoped delivery attempts with optional filters."""

    def __init__(self, repository: DeliveryAttemptRepository):
        self.repository = repository

    def __call__(
        self,
        *,
        tenant_id: str,
        status: Optional[str] = None,
        event_id: Optional[str] = None,
        subscription_id: Optional[str] = None,
    ) -> Sequence[DeliveryAttempt]:
        return self.repository.list_by_tenant(
            tenant_id,
            status=status,
            event_id=event_id,
            subscription_id=subscription_id,
        )
