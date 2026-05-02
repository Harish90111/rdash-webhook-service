"""Django-backed circuit breaker state for outbound target protection."""

from datetime import timedelta
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from data.models.models import CircuitBreakerState, CircuitBreakerStatus
from domain.interfaces import CircuitBreaker, CircuitBreakerDecision


logger = logging.getLogger("webhook.delivery")


class DjangoCircuitBreaker(CircuitBreaker):
    """Tenant-safe circuit breaker persisted in the database."""

    def __init__(
        self,
        *,
        failure_threshold: int = None,
        recovery_timeout_seconds: int = None,
    ) -> None:
        self.failure_threshold = int(
            failure_threshold
            if failure_threshold is not None
            else getattr(settings, "WEBHOOK_CIRCUIT_BREAKER_FAILURE_THRESHOLD", 5)
        )
        self.recovery_timeout_seconds = int(
            recovery_timeout_seconds
            if recovery_timeout_seconds is not None
            else getattr(settings, "WEBHOOK_CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS", 60)
        )
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if self.recovery_timeout_seconds < 1:
            raise ValueError("recovery_timeout_seconds must be at least 1")

    def before_request(self, *, tenant_id: str, target_url: str) -> CircuitBreakerDecision:
        now = timezone.now()
        with transaction.atomic():
            state = self._get_or_create_locked(tenant_id, target_url)
            if state.state == CircuitBreakerStatus.OPEN:
                retry_after_seconds = self._retry_after_seconds(state, now)
                if retry_after_seconds > 0:
                    logger.warning(
                        "circuit_breaker_open_blocked",
                        extra={
                            "event": "circuit_breaker_open_blocked",
                            "component": "circuit_breaker",
                            "tenant_id": tenant_id,
                            "target_url": target_url,
                            "retry_after_seconds": retry_after_seconds,
                            "consecutive_failures": state.consecutive_failures,
                        },
                    )
                    return CircuitBreakerDecision(
                        allowed=False,
                        state=CircuitBreakerStatus.OPEN,
                        retry_after_seconds=retry_after_seconds,
                    )
                state.state = CircuitBreakerStatus.HALF_OPEN
                state.save(update_fields=["state", "updated_at"])
                logger.info(
                    "circuit_breaker_half_open_probe_allowed",
                    extra={
                        "event": "circuit_breaker_half_open_probe_allowed",
                        "component": "circuit_breaker",
                        "tenant_id": tenant_id,
                        "target_url": target_url,
                        "consecutive_failures": state.consecutive_failures,
                    },
                )
                return CircuitBreakerDecision(
                    allowed=True,
                    state=CircuitBreakerStatus.HALF_OPEN,
                )
            if state.state == CircuitBreakerStatus.HALF_OPEN:
                logger.warning(
                    "circuit_breaker_half_open_blocked",
                    extra={
                        "event": "circuit_breaker_half_open_blocked",
                        "component": "circuit_breaker",
                        "tenant_id": tenant_id,
                        "target_url": target_url,
                        "retry_after_seconds": float(self.recovery_timeout_seconds),
                        "consecutive_failures": state.consecutive_failures,
                    },
                )
                return CircuitBreakerDecision(
                    allowed=False,
                    state=CircuitBreakerStatus.HALF_OPEN,
                    retry_after_seconds=float(self.recovery_timeout_seconds),
                )
            return CircuitBreakerDecision(
                allowed=True,
                state=CircuitBreakerStatus.CLOSED,
            )

    def record_success(self, *, tenant_id: str, target_url: str) -> None:
        now = timezone.now()
        with transaction.atomic():
            state = self._get_or_create_locked(tenant_id, target_url)
            previous_state = state.state
            previous_failures = state.consecutive_failures
            state.state = CircuitBreakerStatus.CLOSED
            state.consecutive_failures = 0
            state.opened_at = None
            state.last_success_at = now
            state.save(
                update_fields=[
                    "state",
                    "consecutive_failures",
                    "opened_at",
                    "last_success_at",
                    "updated_at",
                ]
            )
            if previous_state != CircuitBreakerStatus.CLOSED or previous_failures:
                logger.info(
                    "circuit_breaker_closed",
                    extra={
                        "event": "circuit_breaker_closed",
                        "component": "circuit_breaker",
                        "tenant_id": tenant_id,
                        "target_url": target_url,
                        "previous_state": str(previous_state),
                        "previous_failures": previous_failures,
                    },
                )

    def record_failure(self, *, tenant_id: str, target_url: str) -> None:
        now = timezone.now()
        with transaction.atomic():
            state = self._get_or_create_locked(tenant_id, target_url)
            previous_state = state.state
            state.last_failure_at = now
            if state.state == CircuitBreakerStatus.HALF_OPEN:
                state.state = CircuitBreakerStatus.OPEN
                state.opened_at = now
                state.consecutive_failures = max(
                    state.consecutive_failures,
                    self.failure_threshold,
                )
            else:
                state.consecutive_failures += 1
                if state.consecutive_failures >= self.failure_threshold:
                    state.state = CircuitBreakerStatus.OPEN
                    state.opened_at = now
                else:
                    state.state = CircuitBreakerStatus.CLOSED
                    state.opened_at = None
            state.save(
                update_fields=[
                    "state",
                    "consecutive_failures",
                    "opened_at",
                    "last_failure_at",
                    "updated_at",
                ]
            )
            if state.state == CircuitBreakerStatus.OPEN:
                logger.warning(
                    "circuit_breaker_opened",
                    extra={
                        "event": "circuit_breaker_opened",
                        "component": "circuit_breaker",
                        "tenant_id": tenant_id,
                        "target_url": target_url,
                        "previous_state": str(previous_state),
                        "consecutive_failures": state.consecutive_failures,
                        "failure_threshold": self.failure_threshold,
                    },
                )

    def _get_or_create_locked(self, tenant_id: str, target_url: str) -> CircuitBreakerState:
        try:
            return (
                CircuitBreakerState.objects.select_for_update()
                .get(tenant_id=tenant_id, target_url=target_url)
            )
        except CircuitBreakerState.DoesNotExist:
            try:
                return CircuitBreakerState.objects.create(
                    tenant_id=tenant_id,
                    target_url=target_url,
                )
            except IntegrityError:
                return (
                    CircuitBreakerState.objects.select_for_update()
                    .get(tenant_id=tenant_id, target_url=target_url)
                )

    def _retry_after_seconds(self, state: CircuitBreakerState, now) -> float:
        opened_at = state.opened_at or now
        retry_at = opened_at + timedelta(seconds=self.recovery_timeout_seconds)
        return max(0.0, (retry_at - now).total_seconds())
