"""Domain-specific exception hierarchy."""

from typing import Any, Mapping, Optional


class WebhookDomainError(Exception):
    """
    Base class for domain errors.

    The domain layer keeps errors framework-neutral. Interface adapters can
    translate error_code values into HTTP responses without importing DRF here.
    """

    error_code = "webhook_domain_error"
    safe_message = "A webhook domain error occurred."

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        context: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self.message = message or self.safe_message
        self.context = dict(context or {})
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Return a serializable, framework-neutral error payload."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
        }


class SubscriptionNotFoundError(WebhookDomainError):
    """Raised when a subscription cannot be found for a tenant."""

    error_code = "subscription_not_found"
    safe_message = "Subscription was not found."


class EventNotFoundError(WebhookDomainError):
    """Raised when a webhook event cannot be found for a tenant."""

    error_code = "event_not_found"
    safe_message = "Webhook event was not found."


class DeliveryAttemptNotFoundError(WebhookDomainError):
    """Raised when a delivery attempt cannot be found."""

    error_code = "delivery_attempt_not_found"
    safe_message = "Delivery attempt was not found."


class DuplicateEventError(WebhookDomainError):
    """Raised when an idempotency key has already been processed."""

    error_code = "duplicate_event"
    safe_message = "A webhook event with this idempotency key already exists."


class DeliveryFailedError(WebhookDomainError):
    """Raised when webhook delivery fails."""

    error_code = "delivery_failed"
    safe_message = "Webhook delivery failed."


class SignatureVerificationError(WebhookDomainError):
    """Raised when a request signature cannot be verified."""

    error_code = "signature_verification_failed"
    safe_message = "Webhook signature verification failed."


__all__ = [
    "DeliveryAttemptNotFoundError",
    "DeliveryFailedError",
    "DuplicateEventError",
    "EventNotFoundError",
    "SignatureVerificationError",
    "SubscriptionNotFoundError",
    "WebhookDomainError",
]
