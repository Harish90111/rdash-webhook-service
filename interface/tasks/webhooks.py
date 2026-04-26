"""Celery task wrappers for outbox dispatch, fan-out, and delivery."""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from data.gateways import HttpxWebhookGateway
from data.repositories import (
    DEFAULT_FANOUT_TASK_NAME,
    DjangoDeliveryAttemptRepository,
    DjangoEventRepository,
    DjangoOutboxRepository,
    DjangoSubscriptionRepository,
)
from interface.use_cases import (
    DeliverWebhook,
    FanOutEvent,
    delivery_task_id,
    tenant_queue_name,
)
from domain.services import calculate_retry_delay


logger = logging.getLogger("webhook.tasks")


@shared_task(name="interface.tasks.dispatch_outbox_batch", bind=True, ignore_result=True)
def dispatch_outbox_batch(self, limit=None, locked_by=None):
    """Publish pending outbox messages to Celery and mark them published."""
    limit = limit or int(getattr(settings, "WEBHOOK_OUTBOX_DISPATCH_BATCH_SIZE", 100))
    locked_by = locked_by or getattr(self.request, "hostname", "webhook-dispatcher")
    outbox_repository = DjangoOutboxRepository()
    messages = outbox_repository.lock_pending_batch(
        locked_by=locked_by,
        limit=limit,
        stale_after_seconds=int(getattr(settings, "WEBHOOK_OUTBOX_STALE_LOCK_SECONDS", 300)),
    )

    for message in messages:
        try:
            if message.task_name != DEFAULT_FANOUT_TASK_NAME:
                raise ValueError(f"Unsupported outbox task: {message.task_name}")
            fanout_event.apply_async(
                kwargs=message.payload,
                queue=message.queue_name or "webhooks.fanout",
                task_id=f"fanout:{message.id}",
            )
            outbox_repository.mark_published(str(message.id), str(message.tenant_id))
        except ValueError as exc:
            logger.exception("outbox_dispatch_permanent_failure", extra={"outbox_message_id": str(message.id)})
            outbox_repository.mark_failed(str(message.id), str(message.tenant_id), str(exc))
        except Exception as exc:
            logger.exception("outbox_dispatch_failed", extra={"outbox_message_id": str(message.id)})
            delay = calculate_retry_delay(
                message.attempts,
                base_delay=float(getattr(settings, "WEBHOOK_OUTBOX_BASE_RETRY_DELAY", 1.0)),
                max_delay=float(getattr(settings, "WEBHOOK_OUTBOX_MAX_RETRY_DELAY", 60.0)),
                jitter_factor=float(getattr(settings, "WEBHOOK_RETRY_JITTER", 0.1)),
            )
            outbox_repository.release_for_retry(
                str(message.id),
                str(message.tenant_id),
                str(exc) or exc.__class__.__name__,
                available_at=timezone.now() + timedelta(seconds=delay),
            )


@shared_task(name="interface.tasks.fanout_event", bind=True, ignore_result=True)
def fanout_event(self, event_id: str, tenant_id: str):
    """Fan out one event into per-subscription delivery attempts."""

    def enqueue_delivery(attempt, scoped_tenant_id: str) -> None:
        deliver_webhook.apply_async(
            kwargs={"attempt_id": attempt.id, "tenant_id": scoped_tenant_id},
            queue=_delivery_queue(scoped_tenant_id),
            task_id=delivery_task_id(attempt.id),
        )

    enqueued_count = FanOutEvent(
        event_repository=DjangoEventRepository(),
        subscription_repository=DjangoSubscriptionRepository(),
        delivery_attempt_repository=DjangoDeliveryAttemptRepository(),
        enqueue_delivery=enqueue_delivery,
    )(event_id=event_id, tenant_id=tenant_id)
    logger.info(
        "fanout_event_completed",
        extra={"event_id": event_id, "tenant_id": tenant_id, "enqueued_count": enqueued_count},
    )


@shared_task(name="interface.tasks.deliver_webhook", bind=True, ignore_result=True)
def deliver_webhook(self, attempt_id: str, tenant_id: str):
    """Deliver one webhook attempt and schedule domain-driven retries."""

    def enqueue_retry(attempt, scoped_tenant_id: str, countdown_seconds: float) -> None:
        deliver_webhook.apply_async(
            kwargs={"attempt_id": attempt.id, "tenant_id": scoped_tenant_id},
            countdown=countdown_seconds,
            queue=_delivery_queue(scoped_tenant_id),
            task_id=delivery_task_id(attempt.id),
        )

    with HttpxWebhookGateway() as gateway:
        attempt = DeliverWebhook(
            event_repository=DjangoEventRepository(),
            subscription_repository=DjangoSubscriptionRepository(),
            delivery_attempt_repository=DjangoDeliveryAttemptRepository(),
            http_gateway=gateway,
            enqueue_retry=enqueue_retry,
            max_retries=int(getattr(settings, "WEBHOOK_MAX_RETRIES", 5)),
            base_retry_delay=float(getattr(settings, "WEBHOOK_BASE_RETRY_DELAY", 1.0)),
            max_retry_delay=float(getattr(settings, "WEBHOOK_MAX_RETRY_DELAY", 60.0)),
            retry_jitter=float(getattr(settings, "WEBHOOK_RETRY_JITTER", 0.1)),
            connect_timeout=float(getattr(settings, "WEBHOOK_CONNECT_TIMEOUT", 5)),
            read_timeout=float(getattr(settings, "WEBHOOK_READ_TIMEOUT", 15)),
        )(attempt_id=attempt_id, tenant_id=tenant_id)
    logger.info(
        "deliver_webhook_completed",
        extra={"attempt_id": attempt_id, "tenant_id": tenant_id, "status": attempt.status.value},
    )


def _delivery_queue(tenant_id: str) -> str:
    buckets = int(getattr(settings, "WEBHOOK_TENANT_QUEUE_BUCKETS", 16))
    return tenant_queue_name(tenant_id, buckets=buckets)
