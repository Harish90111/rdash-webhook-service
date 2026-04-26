"""Pure domain entity for webhook delivery state."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import uuid


MAX_RESPONSE_BODY_LENGTH = 500


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(timezone.utc)


class DeliveryStatus(str, Enum):
    """Status of a delivery attempt."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"


@dataclass
class DeliveryAttempt:
    """
    Represents an attempt to deliver a webhook event to a subscription.
    
    Attributes:
        id: Unique identifier (UUID)
        event_id: The WebhookEvent being delivered
        subscription_id: The Subscription being delivered to
        status: Current status of the delivery
        attempt_number: Which attempt this is (1 = first try)
        status_code: HTTP response status code (if available)
        response_body: Truncated response body (if available)
        error_message: Error message if failed
        next_retry_at: When to retry (if scheduled)
        created_at: When this attempt was created
        completed_at: When this attempt finished
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str = ""
    subscription_id: str = ""
    status: DeliveryStatus = DeliveryStatus.PENDING
    attempt_number: int = 1
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    next_retry_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=utc_now)
    completed_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate the delivery attempt after initialization."""
        self.id = self.id.strip()
        self.event_id = self.event_id.strip()
        self.subscription_id = self.subscription_id.strip()
        self.status = DeliveryStatus(self.status)

        if not self.id:
            raise ValueError("id is required")
        if not self.event_id:
            raise ValueError("event_id is required")
        if not self.subscription_id:
            raise ValueError("subscription_id is required")
        if self.attempt_number < 1:
            raise ValueError("attempt_number must be greater than zero")
    
    def mark_in_progress(self) -> None:
        """Mark this attempt as in progress."""
        self.status = DeliveryStatus.IN_PROGRESS
        self.next_retry_at = None
        self.completed_at = None
    
    def mark_success(self, status_code: int, response_body: Optional[str] = None) -> None:
        """Mark this attempt as successful."""
        self.status = DeliveryStatus.SUCCESS
        self.status_code = status_code
        self.response_body = self._truncate_response_body(response_body)
        self.error_message = None
        self.next_retry_at = None
        self.completed_at = utc_now()
    
    def mark_failed(
        self,
        error_message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
    ) -> None:
        """Mark this attempt as failed."""
        if not error_message:
            raise ValueError("error_message is required")
        self.status = DeliveryStatus.FAILED
        self.error_message = error_message
        self.status_code = status_code
        self.response_body = self._truncate_response_body(response_body)
        self.completed_at = utc_now()
    
    def mark_retrying(self, next_retry_at: datetime) -> None:
        """Mark this attempt as retrying."""
        self.status = DeliveryStatus.RETRYING
        self.next_retry_at = next_retry_at
        self.attempt_number += 1
        self.completed_at = None
    
    def mark_dead_letter(self, error_message: str) -> None:
        """Mark this attempt as dead letter (no more retries)."""
        if not error_message:
            raise ValueError("error_message is required")
        self.status = DeliveryStatus.DEAD_LETTER
        self.error_message = error_message
        self.next_retry_at = None
        self.completed_at = utc_now()

    @property
    def is_terminal(self) -> bool:
        """Return True when no more worker processing is expected."""
        return self.status in {DeliveryStatus.SUCCESS, DeliveryStatus.DEAD_LETTER}

    @staticmethod
    def _truncate_response_body(response_body: Optional[str]) -> Optional[str]:
        if response_body is None:
            return None
        return response_body[:MAX_RESPONSE_BODY_LENGTH]
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "event_id": self.event_id,
            "subscription_id": self.subscription_id,
            "status": self.status.value,
            "attempt_number": self.attempt_number,
            "status_code": self.status_code,
            "response_body": self.response_body,
            "error_message": self.error_message,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
