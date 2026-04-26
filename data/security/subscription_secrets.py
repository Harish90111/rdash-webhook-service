"""Encryption helpers for subscriber signing secrets."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class DjangoSubscriptionSecretCipher:
    """Encrypt and decrypt subscription signing secrets for the data layer."""

    def __init__(self, *, key_material: str = "") -> None:
        resolved_key_material = (key_material or self._default_key_material()).strip()
        if not resolved_key_material:
            raise ValueError("key_material is required")
        self._fernet = Fernet(self._derive_fernet_key(resolved_key_material))

    def encrypt(self, raw_secret: str) -> str:
        normalized_secret = self._normalize_secret(raw_secret)
        return self._fernet.encrypt(normalized_secret.encode("utf-8")).decode("utf-8")

    def decrypt(self, encrypted_secret: str) -> str:
        normalized_secret = self._normalize_secret(encrypted_secret, field_name="encrypted_secret")
        try:
            return self._fernet.decrypt(normalized_secret.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("encrypted_secret could not be decrypted") from exc

    @staticmethod
    def _derive_fernet_key(key_material: str) -> bytes:
        digest = hashlib.sha256(key_material.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    @staticmethod
    def _default_key_material() -> str:
        return getattr(settings, "WEBHOOK_SECRET_ENCRYPTION_KEY", "") or settings.SECRET_KEY

    @staticmethod
    def _normalize_secret(secret: str, *, field_name: str = "raw_secret") -> str:
        if secret is None:
            raise ValueError("{field_name} is required".format(field_name=field_name))
        normalized_secret = secret.strip()
        if not normalized_secret:
            raise ValueError("{field_name} is required".format(field_name=field_name))
        return normalized_secret
