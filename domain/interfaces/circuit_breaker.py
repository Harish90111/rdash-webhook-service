"""Circuit breaker contract for outbound webhook delivery."""

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class CircuitBreakerDecision:
    """Result of checking whether a target may be called right now."""

    allowed: bool
    state: str
    retry_after_seconds: Optional[float] = None


@runtime_checkable
class CircuitBreaker(Protocol):
    """Policy boundary for target-level circuit breaking."""

    def before_request(self, *, tenant_id: str, target_url: str) -> CircuitBreakerDecision:
        ...

    def record_success(self, *, tenant_id: str, target_url: str) -> None:
        ...

    def record_failure(self, *, tenant_id: str, target_url: str) -> None:
        ...
