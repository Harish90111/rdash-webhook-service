"""Celery task wrappers for outbox dispatch, fan-out, and delivery."""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from data.gateways import HttpxWebhookGateway
from data.repositories import (
    DEFAULT_FANOUT_TASK_NAME,
    DjangoCircuitBreaker,
    DjangoDeliveryAttemptRepository,
    DjangoEventRepository,
    DjangoOutboxRepository,
    DjangoSubscriptionRepository,
)
from interface.use_cases import (
    DeliverWebhook,
    FanOutEvent,
    RecoverOverdueDeliveryRetries,
    delivery_task_id,
    tenant_queue_name,
)
from domain.services import calculate_retry_delay


logger = logging.getLogger("webhook.tasks")


def _task_request_context(task) -> dict:
    """Return common Celery request metadata for structured logs."""
    request = getattr(task, "request", None)
    return {
        "task_id": getattr(request, "id", None),
        "task_name": getattr(task, "name", None),
        "hostname": getattr(request, "hostname", None),
        "retries": getattr(request, "retries", None),
    }


@shared_task(name="interface.tasks.dispatch_outbox_batch", bind=True, ignore_result=True)
def dispatch_outbox_batch(self, limit=None, locked_by=None):
    """Publish pending outbox messages to Celery and mark them published."""
    limit = limit or int(getattr(settings, "WEBHOOK_OUTBOX_DISPATCH_BATCH_SIZE", 100))
    locked_by = locked_by or getattr(self.request, "hostname", "webhook-dispatcher")
    stale_after_seconds = int(getattr(settings, "WEBHOOK_OUTBOX_STALE_LOCK_SECONDS", 300))

    logger.info(
        "outbox_dispatch_batch_started",
        extra={
            "event": "outbox_dispatch_batch_started",
            "component": "outbox_dispatcher",
            "limit": limit,
            "locked_by": locked_by,
            "stale_after_seconds": stale_after_seconds,
            **_task_request_context(self),
        },
    )

    outbox_repository = DjangoOutboxRepository()
    messages = outbox_repository.lock_pending_batch(
        locked_by=locked_by,
        limit=limit,
        stale_after_seconds=stale_after_seconds,
    )

    logger.info(
        "outbox_dispatch_batch_locked",
        extra={
            "event": "outbox_dispatch_batch_locked",
            "component": "outbox_dispatcher",
            "locked_count": len(messages),
            "limit": limit,
            "locked_by": locked_by,
            **_task_request_context(self),
        },
    )

    published_count = 0
    failed_count = 0
    retry_count = 0

    for message in messages:
        queue_name = message.queue_name or "webhooks.fanout"
        task_id = f"fanout:{message.id}"

        logger.info(
            "outbox_message_dispatch_started",
            extra={
                "event": "outbox_message_dispatch_started",
                "component": "outbox_dispatcher",
                "outbox_message_id": str(message.id),
                "tenant_id": str(message.tenant_id),
                "task_name": message.task_name,
                "queue_name": queue_name,
                "celery_task_id": task_id,
                "attempts": message.attempts,
                **_task_request_context(self),
            },
        )

        try:
            if message.task_name != DEFAULT_FANOUT_TASK_NAME:
                raise ValueError(f"Unsupported outbox task: {message.task_name}")
            fanout_event.apply_async(
                kwargs=message.payload,
                queue=queue_name,
                task_id=task_id,
            )
            outbox_repository.mark_published(str(message.id), str(message.tenant_id))
            published_count += 1
            logger.info(
                "outbox_message_published",
                extra={
                    "event": "outbox_message_published",
                    "component": "outbox_dispatcher",
                    "outbox_message_id": str(message.id),
                    "tenant_id": str(message.tenant_id),
                    "queue_name": queue_name,
                    "celery_task_id": task_id,
                    **_task_request_context(self),
                },
            )
        except ValueError as exc:
            failed_count += 1
            logger.exception(
                "outbox_dispatch_permanent_failure",
                extra={
                    "event": "outbox_dispatch_permanent_failure",
                    "component": "outbox_dispatcher",
                    "outbox_message_id": str(message.id),
                    "tenant_id": str(message.tenant_id),
                    "task_name": message.task_name,
                    "error_type": exc.__class__.__name__,
                    "error_message": str(exc),
                    **_task_request_context(self),
                },
            )
            outbox_repository.mark_failed(str(message.id), str(message.tenant_id), str(exc))
        except Exception as exc:
            failed_count += 1
            logger.exception(
                "outbox_dispatch_failed",
                extra={
                    "event": "outbox_dispatch_failed",
                    "component": "outbox_dispatcher",
                    "outbox_message_id": str(message.id),
                    "tenant_id": str(message.tenant_id),
                    "task_name": message.task_name,
                    "error_type": exc.__class__.__name__,
                    "error_message": str(exc),
                    **_task_request_context(self),
                },
            )
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
            retry_count += 1
            logger.info(
                "outbox_message_released_for_retry",
                extra={
                    "event": "outbox_message_released_for_retry",
                    "component": "outbox_dispatcher",
                    "outbox_message_id": str(message.id),
                    "tenant_id": str(message.tenant_id),
                    "retry_delay_seconds": delay,
                    "attempts": message.attempts,
                    **_task_request_context(self),
                },
            )

    logger.info(
        "outbox_dispatch_batch_completed",
        extra={
            "event": "outbox_dispatch_batch_completed",
            "component": "outbox_dispatcher",
            "locked_count": len(messages),
            "published_count": published_count,
            "failed_count": failed_count,
            "retry_count": retry_count,
            "limit": limit,
            "locked_by": locked_by,
            **_task_request_context(self),
        },
    )


@shared_task(name="interface.tasks.recover_delivery_retries", bind=True, ignore_result=True)
def recover_delivery_retries(self, limit=None):
    """Re-enqueue overdue retrying attempts in case a delayed retry task was lost."""
    limit = limit or int(getattr(settings, "WEBHOOK_DELIVERY_RECOVERY_BATCH_SIZE", 100))

    logger.info(
        "delivery_retry_recovery_started",
        extra={
            "event": "delivery_retry_recovery_started",
            "component": "delivery_recovery",
            "limit": limit,
            **_task_request_context(self),
        },
    )

    def enqueue_delivery(attempt, tenant_id: str) -> None:
        queue_name = _delivery_queue(tenant_id)
        task_id = delivery_task_id(attempt.id)
        logger.info(
            "delivery_retry_recovery_enqueue_started",
            extra={
                "event": "delivery_retry_recovery_enqueue_started",
                "component": "delivery_recovery",
                "attempt_id": attempt.id,
                "tenant_id": tenant_id,
                "queue_name": queue_name,
                "celery_task_id": task_id,
                **_task_request_context(self),
            },
        )
        deliver_webhook.apply_async(
            kwargs={"attempt_id": attempt.id, "tenant_id": tenant_id},
            queue=queue_name,
            task_id=task_id,
        )

    try:
        recovered_count = RecoverOverdueDeliveryRetries(
            delivery_attempt_repository=DjangoDeliveryAttemptRepository(),
            enqueue_delivery=enqueue_delivery,
        )(limit=limit)
    except Exception as exc:
        logger.exception(
            "delivery_retry_recovery_failed",
            extra={
                "event": "delivery_retry_recovery_failed",
                "component": "delivery_recovery",
                "limit": limit,
                "error_type": exc.__class__.__name__,
                "error_message": str(exc),
                **_task_request_context(self),
            },
        )
        raise

    logger.info(
        "delivery_retry_recovery_completed",
        extra={
            "event": "delivery_retry_recovery_completed",
            "component": "delivery_recovery",
            "limit": limit,
            "recovered_count": recovered_count,
            **_task_request_context(self),
        },
    )


@shared_task(name="interface.tasks.fanout_event", bind=True, ignore_result=True)
def fanout_event(self, event_id: str, tenant_id: str):
    """Fan out one event into per-subscription delivery attempts."""

    logger.info(
        "fanout_event_started",
        extra={
            "event": "fanout_event_started",
            "component": "fanout_worker",
            "event_id": event_id,
            "tenant_id": tenant_id,
            **_task_request_context(self),
        },
    )

    def enqueue_delivery(attempt, scoped_tenant_id: str) -> None:
        queue_name = _delivery_queue(scoped_tenant_id)
        task_id = delivery_task_id(attempt.id)
        logger.info(
            "delivery_attempt_enqueue_started",
            extra={
                "event": "delivery_attempt_enqueue_started",
                "component": "fanout_worker",
                "event_id": event_id,
                "tenant_id": scoped_tenant_id,
                "attempt_id": attempt.id,
                "queue_name": queue_name,
                "celery_task_id": task_id,
                **_task_request_context(self),
            },
        )
        deliver_webhook.apply_async(
            kwargs={"attempt_id": attempt.id, "tenant_id": scoped_tenant_id},
            queue=queue_name,
            task_id=task_id,
        )
        logger.info(
            "delivery_attempt_enqueued",
            extra={
                "event": "delivery_attempt_enqueued",
                "component": "fanout_worker",
                "event_id": event_id,
                "tenant_id": scoped_tenant_id,
                "attempt_id": attempt.id,
                "queue_name": queue_name,
                "celery_task_id": task_id,
                **_task_request_context(self),
            },
        )

    try:
        enqueued_count = FanOutEvent(
            event_repository=DjangoEventRepository(),
            subscription_repository=DjangoSubscriptionRepository(),
            delivery_attempt_repository=DjangoDeliveryAttemptRepository(),
            enqueue_delivery=enqueue_delivery,
        )(event_id=event_id, tenant_id=tenant_id)
    except Exception as exc:
        logger.exception(
            "fanout_event_failed",
            extra={
                "event": "fanout_event_failed",
                "component": "fanout_worker",
                "event_id": event_id,
                "tenant_id": tenant_id,
                "error_type": exc.__class__.__name__,
                "error_message": str(exc),
                **_task_request_context(self),
            },
        )
        raise

    logger.info(
        "fanout_event_completed",
        extra={
            "event": "fanout_event_completed",
            "component": "fanout_worker",
            "event_id": event_id,
            "tenant_id": tenant_id,
            "enqueued_count": enqueued_count,
            **_task_request_context(self),
        },
    )


@shared_task(name="interface.tasks.deliver_webhook", bind=True, ignore_result=True)
def deliver_webhook(self, attempt_id: str, tenant_id: str):
    """Deliver one webhook attempt and schedule domain-driven retries."""

    logger.info(
        "deliver_webhook_started",
        extra={
            "event": "deliver_webhook_started",
            "component": "delivery_worker",
            "attempt_id": attempt_id,
            "tenant_id": tenant_id,
            **_task_request_context(self),
        },
    )

    def enqueue_retry(attempt, scoped_tenant_id: str, countdown_seconds: float) -> None:
        queue_name = _delivery_queue(scoped_tenant_id)
        task_id = delivery_task_id(attempt.id)
        logger.info(
            "delivery_retry_enqueue_started",
            extra={
                "event": "delivery_retry_enqueue_started",
                "component": "delivery_worker",
                "attempt_id": attempt.id,
                "tenant_id": scoped_tenant_id,
                "queue_name": queue_name,
                "celery_task_id": task_id,
                "countdown_seconds": countdown_seconds,
                **_task_request_context(self),
            },
        )
        deliver_webhook.apply_async(
            kwargs={"attempt_id": attempt.id, "tenant_id": scoped_tenant_id},
            countdown=countdown_seconds,
            queue=queue_name,
            task_id=task_id,
        )
        logger.info(
            "delivery_retry_enqueued",
            extra={
                "event": "delivery_retry_enqueued",
                "component": "delivery_worker",
                "attempt_id": attempt.id,
                "tenant_id": scoped_tenant_id,
                "queue_name": queue_name,
                "celery_task_id": task_id,
                "countdown_seconds": countdown_seconds,
                **_task_request_context(self),
            },
        )

    try:
        with HttpxWebhookGateway() as gateway:
            attempt = DeliverWebhook(
                event_repository=DjangoEventRepository(),
                subscription_repository=DjangoSubscriptionRepository(),
                delivery_attempt_repository=DjangoDeliveryAttemptRepository(),
                http_gateway=gateway,
                enqueue_retry=enqueue_retry,
                circuit_breaker=DjangoCircuitBreaker(),
                max_retries=int(getattr(settings, "WEBHOOK_MAX_RETRIES", 5)),
                base_retry_delay=float(getattr(settings, "WEBHOOK_BASE_RETRY_DELAY", 1.0)),
                max_retry_delay=float(getattr(settings, "WEBHOOK_MAX_RETRY_DELAY", 60.0)),
                retry_jitter=float(getattr(settings, "WEBHOOK_RETRY_JITTER", 0.1)),
                connect_timeout=float(getattr(settings, "WEBHOOK_CONNECT_TIMEOUT", 5)),
                read_timeout=float(getattr(settings, "WEBHOOK_READ_TIMEOUT", 15)),
            )(attempt_id=attempt_id, tenant_id=tenant_id)
    except Exception as exc:
        logger.exception(
            "deliver_webhook_failed",
            extra={
                "event": "deliver_webhook_failed",
                "component": "delivery_worker",
                "attempt_id": attempt_id,
                "tenant_id": tenant_id,
                "error_type": exc.__class__.__name__,
                "error_message": str(exc),
                **_task_request_context(self),
            },
        )
        raise

    logger.info(
        "deliver_webhook_completed",
        extra={
            "event": "deliver_webhook_completed",
            "component": "delivery_worker",
            "attempt_id": attempt_id,
            "tenant_id": tenant_id,
            "status": attempt.status.value,
            **_task_request_context(self),
        },
    )


def _delivery_queue(tenant_id: str) -> str:
    buckets = int(getattr(settings, "WEBHOOK_TENANT_QUEUE_BUCKETS", 16))
    queue_name = tenant_queue_name(tenant_id, buckets=buckets)
    logger.debug(
        "delivery_queue_resolved",
        extra={
            "event": "delivery_queue_resolved",
            "component": "queue_resolver",
            "tenant_id": tenant_id,
            "buckets": buckets,
            "queue_name": queue_name,
        },
    )
    return queue_name
