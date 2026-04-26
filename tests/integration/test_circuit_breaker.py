from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from data.models.models import CircuitBreakerState, CircuitBreakerStatus, Tenant
from data.repositories import DjangoCircuitBreaker


class DjangoCircuitBreakerTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Acme", slug="acme")
        self.other_tenant = Tenant.objects.create(name="Globex", slug="globex")
        self.target_url = "https://example.test/webhook"
        self.breaker = DjangoCircuitBreaker(
            failure_threshold=2,
            recovery_timeout_seconds=30,
        )

    def test_circuit_breaker_opens_after_threshold_and_allows_half_open_probe_after_cooldown(self):
        first = self.breaker.before_request(
            tenant_id=str(self.tenant.id),
            target_url=self.target_url,
        )
        assert first.allowed is True
        assert first.state == CircuitBreakerStatus.CLOSED

        self.breaker.record_failure(
            tenant_id=str(self.tenant.id),
            target_url=self.target_url,
        )
        second = self.breaker.before_request(
            tenant_id=str(self.tenant.id),
            target_url=self.target_url,
        )
        assert second.allowed is True

        self.breaker.record_failure(
            tenant_id=str(self.tenant.id),
            target_url=self.target_url,
        )
        blocked = self.breaker.before_request(
            tenant_id=str(self.tenant.id),
            target_url=self.target_url,
        )

        assert blocked.allowed is False
        assert blocked.state == CircuitBreakerStatus.OPEN
        assert blocked.retry_after_seconds > 0

        state = CircuitBreakerState.objects.get(
            tenant_id=self.tenant.id,
            target_url=self.target_url,
        )
        state.opened_at = timezone.now() - timedelta(seconds=31)
        state.save(update_fields=["opened_at", "updated_at"])

        half_open = self.breaker.before_request(
            tenant_id=str(self.tenant.id),
            target_url=self.target_url,
        )

        assert half_open.allowed is True
        assert half_open.state == CircuitBreakerStatus.HALF_OPEN

    def test_circuit_breaker_success_resets_failures_and_state(self):
        self.breaker.record_failure(
            tenant_id=str(self.tenant.id),
            target_url=self.target_url,
        )
        self.breaker.record_failure(
            tenant_id=str(self.tenant.id),
            target_url=self.target_url,
        )

        state = CircuitBreakerState.objects.get(
            tenant_id=self.tenant.id,
            target_url=self.target_url,
        )
        assert state.state == CircuitBreakerStatus.OPEN

        self.breaker.record_success(
            tenant_id=str(self.tenant.id),
            target_url=self.target_url,
        )

        state.refresh_from_db()
        assert state.state == CircuitBreakerStatus.CLOSED
        assert state.consecutive_failures == 0
        assert state.opened_at is None
        assert state.last_success_at is not None

    def test_circuit_breaker_is_tenant_scoped_for_same_target_url(self):
        self.breaker.record_failure(
            tenant_id=str(self.tenant.id),
            target_url=self.target_url,
        )
        self.breaker.record_failure(
            tenant_id=str(self.tenant.id),
            target_url=self.target_url,
        )

        tenant_decision = self.breaker.before_request(
            tenant_id=str(self.tenant.id),
            target_url=self.target_url,
        )
        other_tenant_decision = self.breaker.before_request(
            tenant_id=str(self.other_tenant.id),
            target_url=self.target_url,
        )

        assert tenant_decision.allowed is False
        assert other_tenant_decision.allowed is True
