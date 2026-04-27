"""Read-oriented delivery attempt use cases."""

from copy import deepcopy
from datetime import datetime, timezone
import logging
from typing import Callable, Optional, Sequence

from domain.entities import DeliveryAttempt, DeliveryStatus
from domain.exceptions import DeliveryFailedError, DeliveryRetryNotAllowedError

from domain.interfaces import DeliveryAttemptRepository


logger = logging.getLogger("webhook.deliveries")


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
        attempts = self.repository.list_by_tenant(
            tenant_id,
            status=status,
            event_id=event_id,
            subscription_id=subscription_id,
        )
        logger.debug(
            "delivery_attempts_listed",
            extra={
                "event": "delivery_attempts_listed",
                "component": "delivery_visibility",
                "tenant_id": tenant_id,
                "status_filter": status,
                "event_id": event_id,
                "subscription_id": subscription_id,
                "count": len(attempts),
            },
        )
        return attempts


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
            logger.warning(
                "delivery_manual_retry_rejected",
                extra={
                    "event": "delivery_manual_retry_rejected",
                    "component": "delivery_retry",
                    "tenant_id": tenant_id,
                    "attempt_id": attempt_id,
                    "status": attempt.status.value,
                },
            )
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
            logger.exception(
                "delivery_manual_retry_enqueue_failed",
                extra={
                    "event": "delivery_manual_retry_enqueue_failed",
                    "component": "delivery_retry",
                    "tenant_id": tenant_id,
                    "attempt_id": attempt_id,
                },
            )
            self.repository.update(original_attempt, tenant_id)
            raise DeliveryFailedError(
                "Manual delivery retry could not be queued.",
                context={
                    "attempt_id": attempt_id,
                    "tenant_id": tenant_id,
                },
            ) from exc
        logger.info(
            "delivery_manual_retry_queued",
            extra={
                "event": "delivery_manual_retry_queued",
                "component": "delivery_retry",
                "tenant_id": tenant_id,
                "attempt_id": attempt_id,
                "status": persisted_attempt.status.value,
            },
        )
        return persisted_attempt
