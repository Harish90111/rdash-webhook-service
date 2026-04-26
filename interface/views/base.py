"""Base classes for thin DRF views."""

from typing import Any, Callable

from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView


class PrincipalTenantMixin:
    """
    Resolve tenant identity from the authenticated principal.

    Views must not accept tenant identity from request bodies or query strings.
    Authentication will attach the tenant in the security phase.
    """

    tenant_attribute_names = ("tenant_id", "tenant")

    def get_tenant_id(self) -> str:
        user = getattr(self.request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            raise PermissionDenied("Authentication is required.")

        for attribute_name in self.tenant_attribute_names:
            value = getattr(user, attribute_name, None)
            tenant_id = getattr(value, "id", value)
            if tenant_id:
                return str(tenant_id)

        raise PermissionDenied("Authenticated principal is missing tenant identity.")


class ThinAPIView(PrincipalTenantMixin, APIView):
    """
    Base view that keeps HTTP translation separate from use-case execution.

    Concrete views should validate serializers, call use cases through
    run_use_case(), and shape the HTTP response.
    """

    def run_use_case(self, use_case: Callable[..., Any], *args, **kwargs) -> Any:
        return use_case(*args, **kwargs)
