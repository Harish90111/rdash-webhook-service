"""Django persistence for tenant API keys and authentication lookups."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone

from data.models.models import Tenant, TenantAPIKey
from domain.services import generate_api_key, get_api_key_prefix, hash_api_key


logger = logging.getLogger("webhook.security")


@dataclass(frozen=True)
class IssuedTenantAPIKey:
    """One-time API key issuance payload."""

    id: str
    tenant_id: str
    name: str
    key_prefix: str
    raw_key: str
    expires_at: Optional[datetime]
    created_at: datetime


@dataclass(frozen=True)
class AuthenticatedTenantAPIKey:
    """Tenant-scoped principal metadata resolved from an API key."""

    id: str
    tenant_id: str
    tenant_name: str
    tenant_slug: str
    name: str
    key_prefix: str
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]


class DjangoTenantAPIKeyRepository:
    """Issue and verify tenant API keys using the Django ORM."""

    def issue_for_tenant(
        self,
        tenant_id: str,
        name: str,
        *,
        expires_at: Optional[datetime] = None,
        max_attempts: int = 5,
    ) -> IssuedTenantAPIKey:
        tenant = self._get_active_tenant(tenant_id)
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("name is required")
        if max_attempts < 1:
            raise ValueError("max_attempts must be greater than zero")

        for _ in range(max_attempts):
            raw_key = generate_api_key()
            try:
                model = TenantAPIKey.objects.create(
                    tenant=tenant,
                    name=normalized_name,
                    key_prefix=get_api_key_prefix(raw_key),
                    key_hash=hash_api_key(raw_key),
                    expires_at=expires_at,
                )
                issued_key = IssuedTenantAPIKey(
                    id=str(model.id),
                    tenant_id=str(model.tenant_id),
                    name=model.name,
                    key_prefix=model.key_prefix,
                    raw_key=raw_key,
                    expires_at=model.expires_at,
                    created_at=model.created_at,
                )
                logger.info(
                    "tenant_api_key_persisted",
                    extra={
                        "event": "tenant_api_key_persisted",
                        "component": "tenant_api_key_repository",
                        "tenant_id": issued_key.tenant_id,
                        "api_key_id": issued_key.id,
                        "api_key_name": issued_key.name,
                        "api_key_prefix": issued_key.key_prefix,
                        "expires_at": issued_key.expires_at,
                    },
                )
                return issued_key
            except IntegrityError:
                continue

        raise ValueError("Could not allocate a unique API key prefix.")

    def authenticate(self, raw_key: str) -> Optional[AuthenticatedTenantAPIKey]:
        normalized_key = raw_key.strip()
        if not normalized_key:
            return None

        now = timezone.now()
        model = (
            TenantAPIKey.objects.select_related("tenant")
            .filter(
                key_hash=hash_api_key(normalized_key),
                is_active=True,
                tenant__is_active=True,
            )
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
            .first()
        )
        if model is None:
            return None

        TenantAPIKey.objects.filter(id=model.id).update(last_used_at=now)
        model.last_used_at = now
        authenticated_key = AuthenticatedTenantAPIKey(
            id=str(model.id),
            tenant_id=str(model.tenant_id),
            tenant_name=model.tenant.name,
            tenant_slug=model.tenant.slug,
            name=model.name,
            key_prefix=model.key_prefix,
            expires_at=model.expires_at,
            last_used_at=model.last_used_at,
        )
        logger.info(
            "tenant_api_key_authenticated",
            extra={
                "event": "tenant_api_key_authenticated",
                "component": "tenant_api_key_repository",
                "tenant_id": authenticated_key.tenant_id,
                "api_key_id": authenticated_key.id,
                "api_key_name": authenticated_key.name,
                "api_key_prefix": authenticated_key.key_prefix,
                "last_used_at": authenticated_key.last_used_at,
            },
        )
        return authenticated_key

    @staticmethod
    def _get_active_tenant(tenant_id: str) -> Tenant:
        try:
            return Tenant.objects.get(id=tenant_id, is_active=True)
        except Tenant.DoesNotExist as exc:
            raise ValueError("tenant_id must reference an active tenant") from exc
