"""Use cases used by webhook Celery tasks."""

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from domain.entities import DeliveryAttempt, DeliveryStatus
from domain.exceptions import DeliveryFailedError, DuplicateEventError
from domain.interfaces import (
    CircuitBreaker,
    DeliveryAttemptRepository,
    EventRepository,
    HttpGateway,
    HttpRequest,
    HttpTimeouts,
    SubscriptionRepository,
)
from domain.services import build_signature_headers, get_next_retry_time, matches_wildcard, should_retry


logger = logging.getLogger("webhook.delivery")


def tenant_queue_name(tenant_id: str, *, buckets: int = 16) -> str:
    """Return a stable per-tenant delivery queue bucket."""
    if buckets <= 0:
        raise ValueError("buckets must be greater than zero")
    digest = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % buckets
    return f"webhooks.delivery.tenant-{bucket:02d}"


def delivery_task_id(attempt_id: str) -> str:
    """Return a deterministic Celery task id for a delivery attempt."""
    return f"webhook-delivery:{attempt_id}"


class FanOutEvent:
    """Create delivery attempts for matching active subscriptions."""

    def __init__(
        self,
        *,
        event_repository: EventRepository,
        subscription_repository: SubscriptionRepository,
        delivery_attempt_repository: DeliveryAttemptRepository,
        enqueue_delivery: Callable[[DeliveryAttempt, str], None],
    ) -> None:
        self.event_repository = event_repository
        self.subscription_repository = subscription_repository
        self.delivery_attempt_repository = delivery_attempt_repository
        self.enqueue_delivery = enqueue_delivery

    def __call__(self, *, event_id: str, tenant_id: str) -> int:
        event = self.event_repository.get_by_id(event_id, tenant_id)
        matching_subscriptions = [
            subscription
            for subscription in self.subscription_repository.list_active_by_tenant(tenant_id)
            if matches_wildcard(event.event_type, subscription.event_type)
        ]
        logger.info(
            "fanout_event_prepared",
            extra={
                "event": "fanout_event_prepared",
                "component": "fanout_worker",
                "tenant_id": tenant_id,
                "event_id": event_id,
                "event_type": event.event_type,
                "matched_count": len(matching_subscriptions),
            },
        )

        enqueued_count = 0
        for subscription in matching_subscriptions:
            attempt = self.delivery_attempt_repository.find_by_event_and_subscription(
                event.id,
                subscription.id,
                tenant_id,
            )
            if attempt is None:
                try:
                    attempt = self.delivery_attempt_repository.create(
                        DeliveryAttempt(event_id=event.id, subscription_id=subscription.id),
                        tenant_id,
                    )
                except DuplicateEventError:
                    attempt = self.delivery_attempt_repository.find_by_event_and_subscription(
                        event.id,
                        subscription.id,
                        tenant_id,
                    )
                    if attempt is None:
                        raise
            if attempt.status in {
                DeliveryStatus.PENDING,
                DeliveryStatus.FAILED,
                DeliveryStatus.RETRYING,
            }:
                self.enqueue_delivery(attempt, tenant_id)
                enqueued_count += 1
            else:
                logger.debug(
                    "fanout_delivery_attempt_skipped",
                    extra={
                        "event": "fanout_delivery_attempt_skipped",
                        "component": "fanout_worker",
                        "tenant_id": tenant_id,
                        "event_id": event.id,
                        "subscription_id": subscription.id,
                        "attempt_id": attempt.id,
                        "status": attempt.status.value,
                    },
                )

        self.event_repository.mark_processed(event.id, tenant_id)
        return enqueued_count


class DeliverWebhook:
    """Deliver one event/subscription attempt and update retry state."""

    def __init__(
        self,
        *,
        event_repository: EventRepository,
        subscription_repository: SubscriptionRepository,
        delivery_attempt_repository: DeliveryAttemptRepository,
        http_gateway: HttpGateway,
        enqueue_retry: Callable[[DeliveryAttempt, str, float], None],
        circuit_breaker: Optional[CircuitBreaker] = None,
        max_retries: int,
        base_retry_delay: float,
        max_retry_delay: float,
        retry_jitter: float,
        connect_timeout: float,
        read_timeout: float,
    ) -> None:
        self.event_repository = event_repository
        self.subscription_repository = subscription_repository
        self.delivery_attempt_repository = delivery_attempt_repository
        self.http_gateway = http_gateway
        self.enqueue_retry = enqueue_retry
        self.circuit_breaker = circuit_breaker
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
        self.max_retry_delay = max_retry_delay
        self.retry_jitter = retry_jitter
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout

    def __call__(self, *, attempt_id: str, tenant_id: str) -> DeliveryAttempt:
        attempt = self.delivery_attempt_repository.claim_for_delivery(attempt_id, tenant_id)
        if attempt is None:
            existing_attempt = self.delivery_attempt_repository.get_by_id(attempt_id, tenant_id)
            logger.info(
                "delivery_attempt_claim_skipped",
                extra={
                    "event": "delivery_attempt_claim_skipped",
                    "component": "delivery_worker",
                    "tenant_id": tenant_id,
                    "attempt_id": attempt_id,
                    "status": existing_attempt.status.value,
                },
            )
            return existing_attempt

        event = self.event_repository.get_by_id(attempt.event_id, tenant_id)
        subscription = self.subscription_repository.get_by_id(attempt.subscription_id, tenant_id)

        body = self._build_body(event)
        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        if self.circuit_breaker is not None:
            breaker_decision = self.circuit_breaker.before_request(
                tenant_id=tenant_id,
                target_url=subscription.target_url,
            )
            if not breaker_decision.allowed:
                logger.warning(
                    "delivery_blocked_by_circuit_breaker",
                    extra={
                        "event": "delivery_blocked_by_circuit_breaker",
                        "component": "delivery_worker",
                        "tenant_id": tenant_id,
                        "attempt_id": attempt_id,
                        "subscription_id": subscription.id,
                        "target_url": subscription.target_url,
                        "retry_after_seconds": breaker_decision.retry_after_seconds,
                    },
                )
                return self._record_failure(
                    attempt,
                    tenant_id,
                    "Circuit breaker open for target URL.",
                    retry_delay_seconds=breaker_decision.retry_after_seconds,
                )
        try:
            signing_secret = self._subscription_signing_secret(subscription)
            response = self.http_gateway.post(
                HttpRequest(
                    url=subscription.target_url,
                    body=body,
                    headers=self._build_request_headers(
                        signing_secret,
                        event.id,
                        event.event_type,
                        timestamp,
                        body,
                    ),
                    timeouts=HttpTimeouts(
                        connect_seconds=self.connect_timeout,
                        read_seconds=self.read_timeout,
                    ),
                    metadata={"event_id": event.id, "subscription_id": subscription.id},
                )
            )
            if response.is_success:
                if self.circuit_breaker is not None:
                    self.circuit_breaker.record_success(
                        tenant_id=tenant_id,
                        target_url=subscription.target_url,
                    )
                attempt.mark_success(response.status_code, response.body)
                return self.delivery_attempt_repository.update(attempt, tenant_id)

            if self.circuit_breaker is not None:
                self.circuit_breaker.record_failure(
                    tenant_id=tenant_id,
                    target_url=subscription.target_url,
                )
            error_message = f"Webhook endpoint returned HTTP {response.status_code}."
            logger.warning(
                "delivery_attempt_http_failure",
                extra={
                    "event": "delivery_attempt_http_failure",
                    "component": "delivery_worker",
                    "tenant_id": tenant_id,
                    "attempt_id": attempt_id,
                    "subscription_id": subscription.id,
                    "target_url": subscription.target_url,
                    "status_code": response.status_code,
                },
            )
            return self._record_failure(
                attempt,
                tenant_id,
                error_message,
                status_code=response.status_code,
                response_body=response.body,
            )
        except Exception as exc:
            if self.circuit_breaker is not None:
                self.circuit_breaker.record_failure(
                    tenant_id=tenant_id,
                    target_url=subscription.target_url,
                )
            logger.warning(
                "delivery_attempt_transport_failure",
                extra={
                    "event": "delivery_attempt_transport_failure",
                    "component": "delivery_worker",
                    "tenant_id": tenant_id,
                    "attempt_id": attempt_id,
                    "subscription_id": subscription.id,
                    "target_url": subscription.target_url,
                    "error": str(exc) or exc.__class__.__name__,
                },
            )
            return self._record_failure(attempt, tenant_id, str(exc) or exc.__class__.__name__)

    def _record_failure(
        self,
        attempt: DeliveryAttempt,
        tenant_id: str,
        error_message: str,
        *,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        retry_delay_seconds: Optional[float] = None,
    ) -> DeliveryAttempt:
        safe_error_message = error_message or "Webhook delivery failed."
        attempt.mark_failed(safe_error_message, status_code=status_code, response_body=response_body)
        if should_retry(attempt.attempt_number, self.max_retries):
            next_retry_at = get_next_retry_time(
                attempt.attempt_number,
                base_delay=self.base_retry_delay,
                max_delay=self.max_retry_delay,
                jitter_factor=self.retry_jitter,
            )
            if retry_delay_seconds is not None:
                circuit_retry_at = datetime.now(timezone.utc) + timedelta(
                    seconds=max(0.0, retry_delay_seconds)
                )
                if circuit_retry_at > next_retry_at:
                    next_retry_at = circuit_retry_at
            attempt.mark_retrying(next_retry_at)
            persisted_attempt = self.delivery_attempt_repository.update(attempt, tenant_id)
            countdown_seconds = max(
                0.0,
                (next_retry_at - datetime.now(timezone.utc)).total_seconds(),
            )
            self.enqueue_retry(persisted_attempt, tenant_id, countdown_seconds)
            logger.warning(
                "delivery_attempt_retry_scheduled",
                extra={
                    "event": "delivery_attempt_retry_scheduled",
                    "component": "delivery_worker",
                    "tenant_id": tenant_id,
                    "attempt_id": attempt.id,
                    "status_code": status_code,
                    "attempt_number": persisted_attempt.attempt_number,
                    "next_retry_at": next_retry_at,
                    "countdown_seconds": countdown_seconds,
                    "error_message": safe_error_message,
                },
            )
            return persisted_attempt

        attempt.mark_dead_letter(safe_error_message)
        dead_letter_attempt = self.delivery_attempt_repository.update(attempt, tenant_id)
        logger.error(
            "delivery_attempt_dead_lettered",
            extra={
                "event": "delivery_attempt_dead_lettered",
                "component": "delivery_worker",
                "tenant_id": tenant_id,
                "attempt_id": attempt.id,
                "status_code": status_code,
                "attempt_number": dead_letter_attempt.attempt_number,
                "error_message": safe_error_message,
            },
        )
        return dead_letter_attempt

    @staticmethod
    def _build_body(event) -> str:
        return json.dumps(
            {
                "id": event.id,
                "tenant_id": event.tenant_id,
                "event_type": event.event_type,
                "payload": event.payload,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    @staticmethod
    def _subscription_signing_secret(subscription) -> str:
        if not subscription.secret:
            raise DeliveryFailedError(
                "Subscription signing secret is unavailable.",
                context={"subscription_id": subscription.id},
            )
        return subscription.secret

    @staticmethod
    def _build_request_headers(
        signing_secret: str,
        event_id: str,
        event_type: str,
        timestamp: str,
        body: str,
    ):
        headers = {
            "Content-Type": "application/json",
            "X-Event-Id": event_id,
            "X-Event-Type": event_type,
        }
        headers.update(build_signature_headers(signing_secret, timestamp, body))
        return headers


class RecoverOverdueDeliveryRetries:
    """Re-enqueue retrying attempts whose retry window has already elapsed."""

    def __init__(
        self,
        *,
        delivery_attempt_repository: DeliveryAttemptRepository,
        enqueue_delivery: Callable[[DeliveryAttempt, str], None],
    ) -> None:
        self.delivery_attempt_repository = delivery_attempt_repository
        self.enqueue_delivery = enqueue_delivery

    def __call__(self, *, limit: int) -> int:
        overdue_attempts = self.delivery_attempt_repository.list_overdue_retrying(limit=limit)
        for attempt, tenant_id in overdue_attempts:
            self.enqueue_delivery(attempt, tenant_id)
        return len(overdue_attempts)
