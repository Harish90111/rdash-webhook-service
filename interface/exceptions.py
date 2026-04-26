"""DRF exception handling for interface adapters."""

from typing import Type

from rest_framework import status
from rest_framework.views import exception_handler as drf_exception_handler

from domain.exceptions import (
    DeliveryAttemptNotFoundError,
    DeliveryFailedError,
    DuplicateEventError,
    EventNotFoundError,
    SignatureVerificationError,
    SubscriptionNotFoundError,
    WebhookDomainError,
)
from interface.responses import error_response


DOMAIN_ERROR_STATUS = {
    SubscriptionNotFoundError: status.HTTP_404_NOT_FOUND,
    EventNotFoundError: status.HTTP_404_NOT_FOUND,
    DeliveryAttemptNotFoundError: status.HTTP_404_NOT_FOUND,
    DuplicateEventError: status.HTTP_409_CONFLICT,
    DeliveryFailedError: status.HTTP_502_BAD_GATEWAY,
    SignatureVerificationError: status.HTTP_401_UNAUTHORIZED,
    WebhookDomainError: status.HTTP_400_BAD_REQUEST,
}


def custom_exception_handler(exc, context):
    """Translate domain exceptions before falling back to DRF defaults."""
    if isinstance(exc, WebhookDomainError):
        return error_response(
            error_code=exc.error_code,
            message=exc.message,
            status_code=_status_for_domain_error(type(exc)),
            context=exc.context,
        )

    return drf_exception_handler(exc, context)


def _status_for_domain_error(error_type: Type[WebhookDomainError]) -> int:
    for candidate in error_type.__mro__:
        if candidate in DOMAIN_ERROR_STATUS:
            return DOMAIN_ERROR_STATUS[candidate]
    return status.HTTP_400_BAD_REQUEST
