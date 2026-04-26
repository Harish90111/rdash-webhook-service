"""DRF authentication for tenant API key principals."""

from dataclasses import dataclass
from typing import Optional

from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from data.repositories import DjangoTenantAPIKeyRepository


@dataclass(frozen=True)
class APIKeyPrincipal:
    """Authenticated API principal derived from a tenant API key."""

    tenant_id: str
    api_key_id: str
    api_key_name: str
    api_key_prefix: str
    tenant_name: str
    tenant_slug: str
    is_authenticated: bool = True


class APIKeyAuthentication(BaseAuthentication):
    """Authenticate incoming requests with tenant-scoped API keys."""

    keyword = "Api-Key"
    repository_class = DjangoTenantAPIKeyRepository
    api_key_header = "HTTP_X_API_KEY"

    def authenticate(self, request):
        raw_key = self._extract_api_key(request)
        if raw_key is None:
            return None

        authenticated_key = self.repository_class().authenticate(raw_key)
        if authenticated_key is None:
            raise AuthenticationFailed("Invalid or inactive API key.")

        principal = APIKeyPrincipal(
            tenant_id=authenticated_key.tenant_id,
            api_key_id=authenticated_key.id,
            api_key_name=authenticated_key.name,
            api_key_prefix=authenticated_key.key_prefix,
            tenant_name=authenticated_key.tenant_name,
            tenant_slug=authenticated_key.tenant_slug,
        )
        return principal, None

    def authenticate_header(self, request) -> str:
        return self.keyword

    def _extract_api_key(self, request) -> Optional[str]:
        explicit_key = request.META.get(self.api_key_header, "").strip()
        if explicit_key:
            return explicit_key

        authorization_header = get_authorization_header(request).decode("utf-8").strip()
        if not authorization_header:
            return None

        parts = authorization_header.split(None, 1)
        if parts[0].lower() != self.keyword.lower():
            return None
        if len(parts) != 2 or not parts[1].strip():
            raise AuthenticationFailed(
                "Authorization header must be in the format 'Api-Key <token>'."
            )
        return parts[1].strip()
