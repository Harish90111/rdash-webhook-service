"""DRF exception handling for interface adapters."""

import logging
from typing import Type

from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    ParseError,
    PermissionDenied,
    Throttled,
    UnsupportedMediaType,
    ValidationError,
)
from rest_framework.views import exception_handler as drf_exception_handler

from domain.exceptions import (
    DeliveryAttemptNotFoundError,
    DeliveryFailedError,
    DeliveryRetryNotAllowedError,
    DuplicateEventError,
    EventNotFoundError,
    SignatureVerificationError,
    SubscriptionNotFoundError,
    WebhookDomainError,
)
from interface.responses import error_response


logger = logging.getLogger("webhook.api")


DOMAIN_ERROR_STATUS = {
    SubscriptionNotFoundError: status.HTTP_404_NOT_FOUND,
    EventNotFoundError: status.HTTP_404_NOT_FOUND,
    DeliveryAttemptNotFoundError: status.HTTP_404_NOT_FOUND,
    DeliveryRetryNotAllowedError: status.HTTP_409_CONFLICT,
    DuplicateEventError: status.HTTP_409_CONFLICT,
    DeliveryFailedError: status.HTTP_502_BAD_GATEWAY,
    SignatureVerificationError: status.HTTP_401_UNAUTHORIZED,
    WebhookDomainError: status.HTTP_400_BAD_REQUEST,
}

API_ERROR_DETAILS = {
    ValidationError: {
        "code": "validation_error",
        "message": "Request validation failed.",
    },
    AuthenticationFailed: {
        "code": "authentication_failed",
        "message": "Authentication failed.",
    },
    NotAuthenticated: {
        "code": "authentication_required",
        "message": "Authentication is required.",
    },
    PermissionDenied: {
        "code": "permission_denied",
        "message": "You do not have permission to perform this action.",
    },
    NotFound: {
        "code": "resource_not_found",
        "message": "Requested resource was not found.",
    },
    MethodNotAllowed: {
        "code": "method_not_allowed",
        "message": "HTTP method is not allowed for this endpoint.",
    },
    ParseError: {
        "code": "parse_error",
        "message": "Request body could not be parsed.",
    },
    UnsupportedMediaType: {
        "code": "unsupported_media_type",
        "message": "Request media type is not supported.",
    },
    Throttled: {
        "code": "throttled",
        "message": "Request was throttled.",
    },
    APIException: {
        "code": "api_error",
        "message": "Request could not be completed.",
    },
}


def custom_exception_handler(exc, context):
    """Translate domain and DRF exceptions into one stable response envelope."""
    if isinstance(exc, WebhookDomainError):
        return error_response(
            error_code=exc.error_code,
            message=exc.message,
            status_code=_status_for_domain_error(type(exc)),
            context=exc.context,
        )

    drf_response = drf_exception_handler(exc, context)
    if drf_response is not None and isinstance(exc, APIException):
        error_details = _details_for_api_exception(exc)
        response_context = {"details": error_details}
        if isinstance(exc, Throttled) and exc.wait is not None:
            response_context["retry_after_seconds"] = exc.wait
        mapped_error = _mapped_api_error(type(exc))
        return error_response(
            error_code=mapped_error["code"],
            message=mapped_error["message"],
            status_code=drf_response.status_code,
            context=response_context,
        )

    logger.exception(
        "api_unhandled_exception",
        extra={
            "event": "api_unhandled_exception",
            "component": "exception_handler",
            "view": _view_name_from_context(context),
        },
    )
    return error_response(
        error_code="internal_server_error",
        message="The server could not complete the request.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        context={},
    )


def _status_for_domain_error(error_type: Type[WebhookDomainError]) -> int:
    for candidate in error_type.__mro__:
        if candidate in DOMAIN_ERROR_STATUS:
            return DOMAIN_ERROR_STATUS[candidate]
    return status.HTTP_400_BAD_REQUEST


def _mapped_api_error(error_type: Type[APIException]) -> dict:
    for candidate in error_type.__mro__:
        if candidate in API_ERROR_DETAILS:
            return API_ERROR_DETAILS[candidate]
    return API_ERROR_DETAILS[APIException]


def _details_for_api_exception(exc: APIException):
    if hasattr(exc, "get_full_details"):
        return _normalize_detail(exc.get_full_details())
    return _normalize_detail(getattr(exc, "detail", str(exc)))


def _normalize_detail(value):
    if isinstance(value, dict):
        if set(value.keys()) == {"message", "code"}:
            return {
                "message": str(value["message"]),
                "code": str(value["code"]),
            }
        return {str(key): _normalize_detail(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_detail(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_detail(item) for item in value]
    if hasattr(value, "code") and hasattr(value, "__str__"):
        return {
            "message": str(value),
            "code": getattr(value, "code", ""),
        }
    return value


def _view_name_from_context(context) -> str:
    view = (context or {}).get("view")
    return view.__class__.__name__ if view is not None else ""
