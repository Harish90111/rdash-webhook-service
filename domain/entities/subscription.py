"""Pure domain entity for webhook subscriptions."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse
import uuid


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass
class Subscription:
    """
    Represents a webhook subscription.
    
    Attributes:
        id: Unique identifier (UUID)
        tenant_id: The tenant/organization that owns this subscription
        event_type: Event type pattern (supports wildcards like 'po.*')
        target_url: Destination URL for webhook delivery
        active: Whether the subscription is active
        secret: Secret for HMAC signing (should be stored hashed)
        created_at: Timestamp when created
        updated_at: Timestamp when last updated
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    event_type: str = ""
    target_url: str = ""
    active: bool = True
    secret: str = ""
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    
    def __post_init__(self):
        """Validate the subscription after initialization."""
        self.id = self.id.strip()
        self.tenant_id = self.tenant_id.strip()
        self.event_type = self.event_type.strip()
        self.target_url = self.target_url.strip()

        if not self.id:
            raise ValueError("id is required")
        if not self.tenant_id:
            raise ValueError("tenant_id is required")
        if not self.event_type:
            raise ValueError("event_type is required")
        if not self.target_url:
            raise ValueError("target_url is required")
        if not self._has_supported_target_url_scheme(self.target_url):
            raise ValueError("target_url must be an http or https URL")
    
    def deactivate(self) -> None:
        """Deactivate this subscription."""
        self.active = False
        self.updated_at = utc_now()
    
    def activate(self) -> None:
        """Activate this subscription."""
        self.active = True
        self.updated_at = utc_now()

    def rotate_secret(self, new_secret: str) -> None:
        """Replace the signing secret carried by this entity."""
        if not new_secret:
            raise ValueError("new_secret is required")
        self.secret = new_secret
        self.updated_at = utc_now()

    @staticmethod
    def _has_supported_target_url_scheme(target_url: str) -> bool:
        parsed = urlparse(target_url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    
    def to_dict(self) -> dict:
        """Convert to dictionary (excludes secret for security)."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "event_type": self.event_type,
            "target_url": self.target_url,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def to_dict_with_secret(self) -> dict:
        """Convert to dictionary including secret (use only on creation)."""
        result = self.to_dict()
        result["secret"] = self.secret
        return result
