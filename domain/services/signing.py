"""Pure HMAC-SHA256 signing helpers for outgoing webhook requests."""

import hashlib
import hmac
from typing import Mapping, Union


SIGNATURE_PREFIX = "sha256="
SIGNATURE_VERSION = "v1"
SIGNATURE_HEADER_NAME = "X-Signature"
SIGNATURE_VERSION_HEADER_NAME = "X-Signature-Version"
TIMESTAMP_HEADER_NAME = "X-Timestamp"


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


def build_signature_headers(
    secret: str,
    timestamp: str,
    body: Union[str, bytes],
) -> Mapping[str, str]:
    """Build the canonical outbound signature headers for webhook delivery."""
    return {
        TIMESTAMP_HEADER_NAME: timestamp,
        SIGNATURE_HEADER_NAME: generate_signature(secret, timestamp, body),
        SIGNATURE_VERSION_HEADER_NAME: SIGNATURE_VERSION,
    }


def verify_signature_headers(
    secret: str,
    body: Union[str, bytes],
    headers: Mapping[str, str],
) -> bool:
    """Verify a signed webhook request from its headers and body."""
    normalized_headers = {
        str(key).lower(): str(value)
        for key, value in headers.items()
    }
    if normalized_headers.get(SIGNATURE_VERSION_HEADER_NAME.lower()) != SIGNATURE_VERSION:
        return False

    timestamp = normalized_headers.get(TIMESTAMP_HEADER_NAME.lower(), "")
    signature = normalized_headers.get(SIGNATURE_HEADER_NAME.lower(), "")
    return verify_signature(secret, timestamp, body, signature)
