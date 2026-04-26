"""Django repository implementations for domain persistence contracts."""

from data.repositories.delivery_attempts import DjangoDeliveryAttemptRepository
from data.repositories.events import DjangoEventRepository
from data.repositories.outbox import (
    DEFAULT_FANOUT_TASK_NAME,
    DjangoOutboxRepository,
    DuplicateOutboxMessageError,
    OutboxMessageNotFoundError,
    create_event_with_outbox,
)
from data.repositories.subscriptions import DjangoSubscriptionRepository

__all__ = [
    "DEFAULT_FANOUT_TASK_NAME",
    "DjangoDeliveryAttemptRepository",
    "DjangoEventRepository",
    "DjangoOutboxRepository",
    "DjangoSubscriptionRepository",
    "DuplicateOutboxMessageError",
    "OutboxMessageNotFoundError",
    "create_event_with_outbox",
]
