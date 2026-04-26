"""Pure idempotency helpers for duplicate event detection."""

import hashlib
import json
from typing import Any, Iterable, Mapping, Optional


def normalize_idempotency_key(key: Optional[str]) -> Optional[str]:
    """Normalize a user-supplied idempotency key."""
    if key is None:
        return None
    normalized = key.strip()
    return normalized or None


def build_idempotency_key(
    tenant_id: str,
    event_type: str,
    payload: Mapping[str, Any],
) -> str:
    """
    Build a deterministic fallback idempotency key for an event submission.

    API clients should normally send an idempotency key. This helper gives the
    domain layer a stable fingerprint when a producer cannot provide one.
    """
    if not tenant_id:
        raise ValueError("tenant_id is required")
    if not event_type:
        raise ValueError("event_type is required")

    canonical_payload = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    material = f"{tenant_id}:{event_type}:{canonical_payload}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def is_duplicate_submission(idempotency_key: Optional[str], existing_keys: Iterable[str]) -> bool:
    """Return True when the normalized key already exists."""
    normalized_key = normalize_idempotency_key(idempotency_key)
    if normalized_key is None:
        return False

    normalized_existing = {
        existing_key
        for existing_key in (normalize_idempotency_key(key) for key in existing_keys)
        if existing_key is not None
    }
    return normalized_key in normalized_existing
