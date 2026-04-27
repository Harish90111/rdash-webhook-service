from types import SimpleNamespace

from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    ValidationError,
)

from domain.exceptions import (
    DuplicateEventError,
    DuplicateSubscriptionError,
    SubscriptionNotFoundError,
)
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
    duplicate_subscription_response = custom_exception_handler(
        DuplicateSubscriptionError(),
        {},
    )
    not_found_response = custom_exception_handler(SubscriptionNotFoundError(), {})

    assert duplicate_response.status_code == status.HTTP_409_CONFLICT
    assert duplicate_subscription_response.status_code == status.HTTP_409_CONFLICT
    assert not_found_response.status_code == status.HTTP_404_NOT_FOUND
    assert duplicate_response.data["error"]["code"] == "duplicate_event"
    assert duplicate_subscription_response.data["error"]["code"] == "duplicate_subscription"
    assert not_found_response.data["error"]["code"] == "subscription_not_found"


def test_custom_exception_handler_maps_validation_errors_to_stable_shape():
    response = custom_exception_handler(
        ValidationError({"tenant_id": ["tenant_id must come from authentication."]}),
        {},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["error"]["code"] == "validation_error"
    assert response.data["error"]["message"] == "Request validation failed."
    assert response.data["error"]["context"]["details"]["tenant_id"][0] == {
        "message": "tenant_id must come from authentication.",
        "code": "invalid",
    }


def test_custom_exception_handler_maps_authentication_errors_to_stable_shape():
    response = custom_exception_handler(AuthenticationFailed("Invalid key."), {})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["error"]["code"] == "authentication_failed"
    assert response.data["error"]["message"] == "Authentication failed."
    assert response.data["error"]["context"]["details"] == {
        "message": "Invalid key.",
        "code": "authentication_failed",
    }


def test_custom_exception_handler_maps_not_authenticated_errors_to_stable_shape():
    response = custom_exception_handler(NotAuthenticated(), {})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["error"]["code"] == "authentication_required"
    assert response.data["error"]["message"] == "Authentication is required."


def test_custom_exception_handler_maps_method_not_allowed_errors_to_stable_shape():
    response = custom_exception_handler(MethodNotAllowed("POST"), {})

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert response.data["error"]["code"] == "method_not_allowed"
    assert response.data["error"]["message"] == "HTTP method is not allowed for this endpoint."


def test_custom_exception_handler_maps_unhandled_errors_to_stable_shape():
    response = custom_exception_handler(RuntimeError("boom"), {})

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.data["error"]["code"] == "internal_server_error"
    assert response.data["error"]["message"] == "The server could not complete the request."


def test_principal_tenant_mixin_uses_authenticated_principal_only():
    view = PrincipalTenantMixin()
    view.request = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=True, tenant_id="tenant-1")
    )

    assert view.get_tenant_id() == "tenant-1"
