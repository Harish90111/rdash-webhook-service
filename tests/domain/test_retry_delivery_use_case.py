from domain.entities import DeliveryAttempt, DeliveryStatus
from domain.exceptions import DeliveryFailedError, DeliveryRetryNotAllowedError
from interface.use_cases.deliveries import RetryDeliveryAttempt


class MemoryDeliveryAttemptRepository:
    def __init__(self, attempts):
        self.attempts = {attempt.id: attempt for attempt in attempts}

    def get_by_id(self, attempt_id, tenant_id):
        return self.attempts[attempt_id]

    def update(self, attempt, tenant_id):
        self.attempts[attempt.id] = attempt
        return attempt


def test_retry_delivery_attempt_requeues_dead_letter_attempt():
    attempt = DeliveryAttempt(
        id="attempt-1",
        event_id="event-1",
        subscription_id="subscription-1",
        status=DeliveryStatus.DEAD_LETTER,
        attempt_number=5,
        error_message="endpoint unavailable",
    )
    queued = []
    repository = MemoryDeliveryAttemptRepository([attempt])

    result = RetryDeliveryAttempt(
        repository,
        enqueue_retry=lambda persisted_attempt, tenant_id: queued.append(
            (persisted_attempt.id, tenant_id)
        ),
    )(tenant_id="tenant-1", attempt_id=attempt.id)

    assert result.status == DeliveryStatus.RETRYING
    assert result.attempt_number == 5
    assert result.next_retry_at is not None
    assert result.completed_at is None
    assert queued == [("attempt-1", "tenant-1")]


def test_retry_delivery_attempt_rejects_non_terminal_attempts():
    attempt = DeliveryAttempt(
        id="attempt-1",
        event_id="event-1",
        subscription_id="subscription-1",
        status=DeliveryStatus.RETRYING,
    )
    repository = MemoryDeliveryAttemptRepository([attempt])

    try:
        RetryDeliveryAttempt(repository, enqueue_retry=lambda *_: None)(
            tenant_id="tenant-1",
            attempt_id=attempt.id,
        )
    except DeliveryRetryNotAllowedError as exc:
        assert exc.context["status"] == DeliveryStatus.RETRYING.value
    else:
        raise AssertionError("Expected DeliveryRetryNotAllowedError")


def test_retry_delivery_attempt_restores_original_state_when_enqueue_fails():
    attempt = DeliveryAttempt(
        id="attempt-1",
        event_id="event-1",
        subscription_id="subscription-1",
        status=DeliveryStatus.DEAD_LETTER,
        error_message="timed out",
    )
    repository = MemoryDeliveryAttemptRepository([attempt])

    try:
        RetryDeliveryAttempt(
            repository,
            enqueue_retry=lambda *_: (_ for _ in ()).throw(RuntimeError("broker down")),
        )(tenant_id="tenant-1", attempt_id=attempt.id)
    except DeliveryFailedError:
        restored = repository.get_by_id("attempt-1", "tenant-1")
        assert restored.status == DeliveryStatus.DEAD_LETTER
        assert restored.error_message == "timed out"
    else:
        raise AssertionError("Expected DeliveryFailedError")
