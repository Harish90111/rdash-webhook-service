"""Domain interface contracts."""

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
    "DeliveryAttemptRepository",
    "EventRepository",
    "HttpGateway",
    "HttpRequest",
    "HttpResponse",
    "HttpTimeouts",
    "SubscriptionRepository",
]
