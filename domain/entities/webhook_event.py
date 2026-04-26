"""Pure domain entity for incoming webhook events."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional
import uuid


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass
class WebhookEvent:
    """
    Represents an incoming webhook event.
    
    Attributes:
        id: Unique identifier (UUID)
        tenant_id: The tenant/organization that owns this event
        event_type: The type of event (e.g., 'po.created', 'po.approved')
        payload: The event payload/data
        idempotency_key: Key for duplicate detection
        timestamp: When the event was received
        processed: Whether the event has been processed by fan-out
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    event_type: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)
    idempotency_key: Optional[str] = None
    timestamp: datetime = field(default_factory=utc_now)
    processed: bool = False
    
    def __post_init__(self):
        """Validate the event after initialization."""
        self.id = self.id.strip()
        self.tenant_id = self.tenant_id.strip()
        self.event_type = self.event_type.strip()
        self.payload = dict(self.payload)
        self.idempotency_key = (
            self.idempotency_key.strip() if self.idempotency_key else None
        )

        if not self.id:
            raise ValueError("id is required")
        if not self.tenant_id:
            raise ValueError("tenant_id is required")
        if not self.event_type:
            raise ValueError("event_type is required")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be a mapping")
    
    def mark_processed(self) -> None:
        """Mark this event as processed."""
        self.processed = True
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "idempotency_key": self.idempotency_key,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "processed": self.processed,
        }
