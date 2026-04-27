from domain.exceptions import (
    DeliveryAttemptNotFoundError,
    DeliveryFailedError,
    DeliveryRetryNotAllowedError,
    DuplicateEventError,
    DuplicateSubscriptionError,
    EventNotFoundError,
    SignatureVerificationError,
    SubscriptionNotFoundError,
    WebhookDomainError,
)


def test_domain_errors_are_framework_neutral_and_serializable():
    error = WebhookDomainError(context={"tenant_id": "tenant-1"})

    assert str(error) == "A webhook domain error occurred."
    assert error.to_dict() == {
        "error_code": "webhook_domain_error",
        "message": "A webhook domain error occurred.",
        "context": {"tenant_id": "tenant-1"},
    }


def test_domain_error_accepts_custom_message_and_copies_context():
    context = {"event_id": "event-1"}
    error = DeliveryFailedError("Endpoint timed out.", context=context)
    context["event_id"] = "changed"

    assert str(error) == "Endpoint timed out."
    assert error.to_dict() == {
        "error_code": "delivery_failed",
        "message": "Endpoint timed out.",
        "context": {"event_id": "event-1"},
    }


def test_specific_domain_errors_have_stable_codes():
    expected = {
        SubscriptionNotFoundError: "subscription_not_found",
        DuplicateSubscriptionError: "duplicate_subscription",
        EventNotFoundError: "event_not_found",
        DeliveryAttemptNotFoundError: "delivery_attempt_not_found",
        DuplicateEventError: "duplicate_event",
        DeliveryFailedError: "delivery_failed",
        DeliveryRetryNotAllowedError: "delivery_retry_not_allowed",
        SignatureVerificationError: "signature_verification_failed",
    }

    for error_type, error_code in expected.items():
        error = error_type()
        assert isinstance(error, WebhookDomainError)
        assert error.error_code == error_code
        assert error.to_dict()["message"] == error.safe_message
