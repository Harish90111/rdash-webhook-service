from types import SimpleNamespace

from rest_framework import status

from domain.exceptions import DuplicateEventError, SubscriptionNotFoundError
from interface.exceptions import custom_exception_handler
from interface.responses import error_response, success_response
from interface.views.base import PrincipalTenantMixin


def test_success_response_uses_consistent_envelope():
    response = success_response({"ok": True}, meta={"page": 1})

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"data": {"ok": True}, "meta": {"page": 1}}


def test_error_response_uses_consistent_envelope():
    response = error_response(
        error_code="duplicate_event",
        message="Duplicate.",
        status_code=status.HTTP_409_CONFLICT,
        context={"idempotency_key": "key-1"},
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["error"]["code"] == "duplicate_event"


def test_custom_exception_handler_maps_domain_errors():
    duplicate_response = custom_exception_handler(DuplicateEventError(), {})
    not_found_response = custom_exception_handler(SubscriptionNotFoundError(), {})

    assert duplicate_response.status_code == status.HTTP_409_CONFLICT
    assert not_found_response.status_code == status.HTTP_404_NOT_FOUND


def test_principal_tenant_mixin_uses_authenticated_principal_only():
    view = PrincipalTenantMixin()
    view.request = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=True, tenant_id="tenant-1")
    )

    assert view.get_tenant_id() == "tenant-1"
