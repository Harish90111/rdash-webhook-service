"""Use cases used by webhook Celery tasks."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Callable, Optional

from domain.entities import DeliveryAttempt, DeliveryStatus
from domain.exceptions import DeliveryFailedError, DuplicateEventError
from domain.interfaces import (
    DeliveryAttemptRepository,
    EventRepository,
    HttpGateway,
    HttpRequest,
    HttpTimeouts,
    SubscriptionRepository,
)
from domain.services import build_signature_headers, get_next_retry_time, matches_wildcard, should_retry


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
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
        self.max_retry_delay = max_retry_delay
        self.retry_jitter = retry_jitter
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout

    def __call__(self, *, attempt_id: str, tenant_id: str) -> DeliveryAttempt:
        attempt = self.delivery_attempt_repository.claim_for_delivery(attempt_id, tenant_id)
        if attempt is None:
            return self.delivery_attempt_repository.get_by_id(attempt_id, tenant_id)

        event = self.event_repository.get_by_id(attempt.event_id, tenant_id)
        subscription = self.subscription_repository.get_by_id(attempt.subscription_id, tenant_id)

        body = self._build_body(event)
        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
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
                attempt.mark_success(response.status_code, response.body)
                return self.delivery_attempt_repository.update(attempt, tenant_id)

            error_message = f"Webhook endpoint returned HTTP {response.status_code}."
            return self._record_failure(
                attempt,
                tenant_id,
                error_message,
                status_code=response.status_code,
                response_body=response.body,
            )
        except Exception as exc:
            return self._record_failure(attempt, tenant_id, str(exc) or exc.__class__.__name__)

    def _record_failure(
        self,
        attempt: DeliveryAttempt,
        tenant_id: str,
        error_message: str,
        *,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
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
            attempt.mark_retrying(next_retry_at)
            persisted_attempt = self.delivery_attempt_repository.update(attempt, tenant_id)
            countdown_seconds = max(0.0, (next_retry_at - datetime.utcnow()).total_seconds())
            self.enqueue_retry(persisted_attempt, tenant_id, countdown_seconds)
            return persisted_attempt

        attempt.mark_dead_letter(safe_error_message)
        return self.delivery_attempt_repository.update(attempt, tenant_id)

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
            "X-Webhook-Event": event_id,
            "X-Webhook-Event-Type": event_type,
        }
        headers.update(build_signature_headers(signing_secret, timestamp, body))
        return headers
