"""Pure HMAC-SHA256 signing helpers for outgoing webhook requests."""

import hashlib
import hmac
from typing import Union


SIGNATURE_PREFIX = "sha256="


def generate_signature(secret: str, timestamp: str, body: Union[str, bytes]) -> str:
    """
    Generate a webhook signature over "{timestamp}.{body}".

    The returned value includes the algorithm prefix, for example:
    "sha256=<hex digest>".
    """
    if not secret:
        raise ValueError("secret is required")
    if not timestamp:
        raise ValueError("timestamp is required")

    body_bytes = body if isinstance(body, bytes) else body.encode("utf-8")
    signed_payload = timestamp.encode("utf-8") + b"." + body_bytes
    digest = hmac.new(
        secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    return f"{SIGNATURE_PREFIX}{digest}"


def verify_signature(
    secret: str,
    timestamp: str,
    body: Union[str, bytes],
    signature: str,
) -> bool:
    """Verify a webhook signature using constant-time comparison."""
    if not signature:
        return False
    expected_signature = generate_signature(secret, timestamp, body)
    return hmac.compare_digest(expected_signature, signature)
