"""Read-oriented delivery attempt use cases."""

from copy import deepcopy
from datetime import datetime, timezone
from typing import Callable, Optional, Sequence

from domain.entities import DeliveryAttempt, DeliveryStatus
from domain.exceptions import DeliveryFailedError, DeliveryRetryNotAllowedError

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


class RetryDeliveryAttempt:
    """Queue an immediate manual retry for a tenant-scoped delivery attempt."""

    allowed_statuses = {
        DeliveryStatus.FAILED,
        DeliveryStatus.DEAD_LETTER,
    }

    def __init__(
        self,
        repository: DeliveryAttemptRepository,
        enqueue_retry: Callable[[DeliveryAttempt, str], None],
    ):
        self.repository = repository
        self.enqueue_retry = enqueue_retry

    def __call__(self, *, tenant_id: str, attempt_id: str) -> DeliveryAttempt:
        attempt = self.repository.get_by_id(attempt_id, tenant_id)
        if attempt.status not in self.allowed_statuses:
            raise DeliveryRetryNotAllowedError(
                context={
                    "attempt_id": attempt_id,
                    "tenant_id": tenant_id,
                    "status": attempt.status.value,
                }
            )

        original_attempt = deepcopy(attempt)
        attempt.status = DeliveryStatus.RETRYING
        attempt.next_retry_at = datetime.now(timezone.utc)
        attempt.completed_at = None
        persisted_attempt = self.repository.update(attempt, tenant_id)
        try:
            self.enqueue_retry(persisted_attempt, tenant_id)
        except Exception as exc:
            self.repository.update(original_attempt, tenant_id)
            raise DeliveryFailedError(
                "Manual delivery retry could not be queued.",
                context={
                    "attempt_id": attempt_id,
                    "tenant_id": tenant_id,
                },
            ) from exc
        return persisted_attempt
