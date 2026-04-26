"""Django outbox repository and atomic event persistence helper."""

from typing import Mapping, Optional, Sequence

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from data.models.models import OutboxMessage, OutboxStatus
from data.models.models import WebhookEvent as WebhookEventModel
from data.repositories.events import DjangoEventRepository
from domain.entities import WebhookEvent
from domain.exceptions import DuplicateEventError, EventNotFoundError, WebhookDomainError


DEFAULT_FANOUT_TASK_NAME = "interface.tasks.fanout_event"


class OutboxMessageNotFoundError(WebhookDomainError):
    """Raised when an outbox message cannot be found for a tenant."""

    error_code = "outbox_message_not_found"
    safe_message = "Outbox message was not found."


class DuplicateOutboxMessageError(WebhookDomainError):
    """Raised when an outbox row already exists for an event/task pair."""

    error_code = "duplicate_outbox_message"
    safe_message = "Outbox message already exists for this event and task."


class DjangoOutboxRepository:
    """Persistence for durable task-publish intent rows."""

    def create_for_event(
        self,
        event: WebhookEvent,
        *,
        task_name: str = DEFAULT_FANOUT_TASK_NAME,
        queue_name: str = "",
        payload: Optional[Mapping[str, object]] = None,
    ) -> OutboxMessage:
        self._ensure_event_exists(event.id, event.tenant_id)
        try:
            return OutboxMessage.objects.create(
                tenant_id=event.tenant_id,
                event_id=event.id,
                task_name=task_name,
                queue_name=queue_name,
                payload=dict(payload or {"event_id": event.id, "tenant_id": event.tenant_id}),
            )
        except IntegrityError as exc:
            raise DuplicateOutboxMessageError(
                context={
                    "event_id": event.id,
                    "tenant_id": event.tenant_id,
                    "task_name": task_name,
                }
            ) from exc

    def list_pending(self, *, limit: int = 100) -> Sequence[OutboxMessage]:
        queryset = OutboxMessage.objects.filter(
            status=OutboxStatus.PENDING,
            available_at__lte=timezone.now(),
        ).order_by("available_at", "created_at")
        return list(queryset[:limit])

    def lock_pending_batch(
        self,
        *,
        locked_by: str,
        limit: int = 100,
    ) -> Sequence[OutboxMessage]:
        now = timezone.now()
        with transaction.atomic():
            queryset = (
                OutboxMessage.objects.select_for_update(skip_locked=True)
                .filter(status=OutboxStatus.PENDING, available_at__lte=now)
                .order_by("available_at", "created_at")[:limit]
            )
            messages = list(queryset)
            message_ids = [message.id for message in messages]
            if message_ids:
                OutboxMessage.objects.filter(id__in=message_ids).update(
                    status=OutboxStatus.IN_PROGRESS,
                    attempts=F("attempts") + 1,
                    locked_at=now,
                    locked_by=locked_by,
                )
            return list(OutboxMessage.objects.filter(id__in=message_ids))

    def mark_published(self, message_id: str, tenant_id: str) -> None:
        updated_count = OutboxMessage.objects.filter(
            id=message_id,
            tenant_id=tenant_id,
        ).update(
            status=OutboxStatus.PUBLISHED,
            published_at=timezone.now(),
            locked_at=None,
            locked_by="",
            last_error="",
        )
        if updated_count == 0:
            raise OutboxMessageNotFoundError(
                context={"message_id": message_id, "tenant_id": tenant_id}
            )

    def mark_failed(
        self,
        message_id: str,
        tenant_id: str,
        error_message: str,
        *,
        available_at=None,
    ) -> None:
        updated_count = OutboxMessage.objects.filter(
            id=message_id,
            tenant_id=tenant_id,
        ).update(
            status=OutboxStatus.FAILED,
            available_at=available_at or timezone.now(),
            locked_at=None,
            locked_by="",
            last_error=error_message[:2000],
        )
        if updated_count == 0:
            raise OutboxMessageNotFoundError(
                context={"message_id": message_id, "tenant_id": tenant_id}
            )

    @staticmethod
    def _ensure_event_exists(event_id: str, tenant_id: str) -> None:
        if not WebhookEventModel.objects.filter(id=event_id, tenant_id=tenant_id).exists():
            raise EventNotFoundError(context={"event_id": event_id, "tenant_id": tenant_id})


def create_event_with_outbox(
    event: WebhookEvent,
    *,
    event_repository: Optional[DjangoEventRepository] = None,
    outbox_repository: Optional[DjangoOutboxRepository] = None,
    task_name: str = DEFAULT_FANOUT_TASK_NAME,
    queue_name: str = "",
) -> WebhookEvent:
    """
    Persist an event and its broker-publish intent in one database transaction.

    If Redis/Celery is unavailable after commit, the outbox row remains pending
    for a dispatcher to publish later.
    """
    event_repository = event_repository or DjangoEventRepository()
    outbox_repository = outbox_repository or DjangoOutboxRepository()

    with transaction.atomic():
        persisted_event = event_repository.create(event)
        try:
            outbox_repository.create_for_event(
                persisted_event,
                task_name=task_name,
                queue_name=queue_name,
            )
        except DuplicateOutboxMessageError as exc:
            raise DuplicateEventError(
                "Outbox message already exists for this event.",
                context={
                    "event_id": persisted_event.id,
                    "tenant_id": persisted_event.tenant_id,
                    "task_name": task_name,
                },
            ) from exc
        return persisted_event
