"""Domain interface contracts."""

from domain.interfaces.circuit_breaker import CircuitBreaker, CircuitBreakerDecision
from domain.interfaces.http_gateway import (
    HttpGateway,
    HttpRequest,
    HttpResponse,
    HttpTimeouts,
)
from domain.interfaces.repositories import (
    DeliveryAttemptRepository,
    EventRepository,
    SubscriptionRepository,
)

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerDecision",
    "DeliveryAttemptRepository",
    "EventRepository",
    "HttpGateway",
    "HttpRequest",
    "HttpResponse",
    "HttpTimeouts",
    "SubscriptionRepository",
]
