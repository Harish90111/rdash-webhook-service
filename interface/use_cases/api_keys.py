"""Application use cases for tenant API key management."""

from datetime import datetime
from typing import Optional


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
        return self.repository.issue_for_tenant(
            tenant_id,
            name,
            expires_at=expires_at,
        )
