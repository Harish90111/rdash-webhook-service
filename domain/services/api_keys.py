"""Pure helpers for tenant API key generation and hashing."""

import hashlib
import secrets


API_KEY_SCHEME = "rdwh"
API_KEY_PUBLIC_ID_LENGTH = 10
API_KEY_SECRET_BYTES = 32


def generate_api_key() -> str:
    """Return a one-time raw API key for a tenant principal."""
    public_id = secrets.token_hex(API_KEY_PUBLIC_ID_LENGTH // 2)
    secret = secrets.token_urlsafe(API_KEY_SECRET_BYTES)
    return "{scheme}_{public_id}_{secret}".format(
        scheme=API_KEY_SCHEME,
        public_id=public_id,
        secret=secret,
    )


def get_api_key_prefix(raw_key: str) -> str:
    """Return the stable display prefix for a raw API key."""
    normalized_key = _normalize_raw_key(raw_key)
    parts = normalized_key.split("_", 2)
    if len(parts) != 3 or parts[0] != API_KEY_SCHEME or not parts[1] or not parts[2]:
        raise ValueError("raw_key must be a valid API key")
    return "{scheme}_{public_id}".format(scheme=parts[0], public_id=parts[1])


def hash_api_key(raw_key: str) -> str:
    """Hash a raw API key before persistence or comparison."""
    normalized_key = _normalize_raw_key(raw_key)
    return hashlib.sha256(normalized_key.encode("utf-8")).hexdigest()


def _normalize_raw_key(raw_key: str) -> str:
    if raw_key is None:
        raise ValueError("raw_key is required")
    normalized_key = raw_key.strip()
    if not normalized_key:
        raise ValueError("raw_key is required")
    return normalized_key
