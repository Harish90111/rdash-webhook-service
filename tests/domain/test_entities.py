from datetime import datetime, timedelta, timezone

import pytest

from domain.entities import (
    DeliveryAttempt,
    DeliveryStatus,
    MAX_RESPONSE_BODY_LENGTH,
    Subscription,
    WebhookEvent,
)


def test_subscription_validates_required_fields_and_http_url():
    with pytest.raises(ValueError, match="tenant_id"):
        Subscription(event_type="po.created", target_url="https://example.test/webhook")

    with pytest.raises(ValueError, match="target_url"):
        Subscription(
            tenant_id="tenant-1",
            event_type="po.created",
            target_url="ftp://example.test/webhook",
        )


def test_subscription_excludes_secret_from_default_dict():
    subscription = Subscription(
        tenant_id=" tenant-1 ",
        event_type=" po.created ",
        target_url=" https://example.test/webhook ",
        secret="plain-secret",
    )

    assert subscription.tenant_id == "tenant-1"
    assert subscription.event_type == "po.created"
    assert subscription.target_url == "https://example.test/webhook"
    assert "secret" not in subscription.to_dict()
    assert subscription.to_dict_with_secret()["secret"] == "plain-secret"


def test_subscription_activation_updates_timestamp():
    subscription = Subscription(
        tenant_id="tenant-1",
        event_type="po.created",
        target_url="https://example.test/webhook",
    )
    original_updated_at = subscription.updated_at

    subscription.deactivate()

    assert subscription.active is False
    assert subscription.updated_at >= original_updated_at


def test_webhook_event_copies_payload_and_marks_processed():
    payload = {"po_id": "PO-1"}
    event = WebhookEvent(
        tenant_id="tenant-1",
        event_type="po.created",
        payload=payload,
        idempotency_key=" key-1 ",
    )
    payload["po_id"] = "changed"

    assert event.payload == {"po_id": "PO-1"}
    assert event.idempotency_key == "key-1"
    assert event.processed is False

    event.mark_processed()

    assert event.processed is True
    assert event.to_dict()["payload"] == {"po_id": "PO-1"}


def test_delivery_attempt_state_transitions_and_truncation():
    attempt = DeliveryAttempt(event_id="event-1", subscription_id="subscription-1")

    attempt.mark_in_progress()
    assert attempt.status == DeliveryStatus.IN_PROGRESS
    assert attempt.completed_at is None

    attempt.mark_failed(
        "HTTP 500",
        status_code=500,
        response_body="x" * (MAX_RESPONSE_BODY_LENGTH + 10),
    )
    assert attempt.status == DeliveryStatus.FAILED
    assert attempt.status_code == 500
    assert len(attempt.response_body) == MAX_RESPONSE_BODY_LENGTH
    assert attempt.completed_at is not None

    retry_at = datetime.now(timezone.utc) + timedelta(seconds=30)
    attempt.mark_retrying(retry_at)
    assert attempt.status == DeliveryStatus.RETRYING
    assert attempt.next_retry_at == retry_at
    assert attempt.attempt_number == 2
    assert attempt.completed_at is None

    attempt.mark_success(204, response_body="ok")
    assert attempt.status == DeliveryStatus.SUCCESS
    assert attempt.response_body == "ok"
    assert attempt.error_message is None
    assert attempt.is_terminal is True


def test_delivery_attempt_rejects_invalid_attempt_number():
    with pytest.raises(ValueError, match="attempt_number"):
        DeliveryAttempt(
            event_id="event-1",
            subscription_id="subscription-1",
            attempt_number=0,
        )
