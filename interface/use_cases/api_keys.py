"""Application use cases for tenant API key management."""

import logging
from datetime import datetime
from typing import Optional


logger = logging.getLogger("webhook.security")


class IssueTenantAPIKey:
    """Issue a one-time raw API key for a tenant principal."""

    def __init__(self, repository):
        self.repository = repository

    def __call__(
        self,
        *,
        tenant_id: str,
        name: str,
        expires_at: Optional[datetime] = None,
    ):
        issued_key = self.repository.issue_for_tenant(
            tenant_id,
            name,
            expires_at=expires_at,
        )
        logger.info(
            "tenant_api_key_issued",
            extra={
                "event": "tenant_api_key_issued",
                "component": "tenant_api_key_management",
                "tenant_id": tenant_id,
                "api_key_id": issued_key.id,
                "api_key_name": issued_key.name,
                "api_key_prefix": issued_key.key_prefix,
                "expires_at": issued_key.expires_at,
            },
        )
        return issued_key
