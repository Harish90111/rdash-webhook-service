from datetime import UTC, datetime, timedelta

from domain.entities import DeliveryAttempt, DeliveryStatus, Subscription, WebhookEvent
from domain.interfaces import CircuitBreakerDecision, HttpResponse
from domain.services import (
    SIGNATURE_HEADER_NAME,
    SIGNATURE_VERSION,
    SIGNATURE_VERSION_HEADER_NAME,
    TIMESTAMP_HEADER_NAME,
    verify_signature_headers,
)
from interface.use_cases.delivery_tasks import (
    DeliverWebhook,
    FanOutEvent,
    delivery_task_id,
    tenant_queue_name,
)


class MemoryEventRepository:
    def __init__(self, events):
        self.events = {event.id: event for event in events}
        self.processed = []

    def create(self, event):
        self.events[event.id] = event
        return event

    def get_by_id(self, event_id, tenant_id):
        return self.events[event_id]

    def get_by_idempotency_key(self, tenant_id, idempotency_key):
        return None

    def mark_processed(self, event_id, tenant_id):
        self.processed.append((event_id, tenant_id))
        self.events[event_id].mark_processed()


class MemorySubscriptionRepository:
    def __init__(self, subscriptions):
        self.subscriptions = {subscription.id: subscription for subscription in subscriptions}

    def create(self, subscription):
        self.subscriptions[subscription.id] = subscription
        return subscription

    def get_by_id(self, subscription_id, tenant_id):
        return self.subscriptions[subscription_id]

    def list_by_tenant(self, tenant_id):
        return list(self.subscriptions.values())

    def list_active_by_tenant(self, tenant_id):
        return [
            subscription
            for subscription in self.subscriptions.values()
            if subscription.tenant_id == tenant_id and subscription.active
        ]

    def update(self, subscription):
        self.subscriptions[subscription.id] = subscription
        return subscription

    def delete(self, subscription_id, tenant_id):
        del self.subscriptions[subscription_id]


class MemoryDeliveryAttemptRepository:
    def __init__(self):
        self.attempts = {}

    def create(self, attempt, tenant_id):
        self.attempts[(attempt.event_id, attempt.subscription_id)] = attempt
        return attempt

    def get_by_id(self, attempt_id, tenant_id):
        return next(attempt for attempt in self.attempts.values() if attempt.id == attempt_id)

    def claim_for_delivery(self, attempt_id, tenant_id):
        attempt = self.get_by_id(attempt_id, tenant_id)
        if attempt.status in {
            DeliveryStatus.IN_PROGRESS,
            DeliveryStatus.SUCCESS,
            DeliveryStatus.DEAD_LETTER,
        }:
            return None
        if attempt.status == DeliveryStatus.RETRYING and attempt.next_retry_at:
            if attempt.next_retry_at > datetime.now(UTC):
                return None
        attempt.mark_in_progress()
        return self.update(attempt, tenant_id)

    def find_by_event_and_subscription(self, event_id, subscription_id, tenant_id):
        return self.attempts.get((event_id, subscription_id))

    def list_for_event(self, event_id, tenant_id):
        return [attempt for attempt in self.attempts.values() if attempt.event_id == event_id]

    def list_by_tenant(
        self,
        tenant_id,
        *,
        status=None,
        event_id=None,
        subscription_id=None,
    ):
        attempts = list(self.attempts.values())
        if status is not None:
            attempts = [attempt for attempt in attempts if attempt.status.value == status]
        if event_id is not None:
            attempts = [attempt for attempt in attempts if attempt.event_id == event_id]
        if subscription_id is not None:
            attempts = [
                attempt
                for attempt in attempts
                if attempt.subscription_id == subscription_id
            ]
        return attempts

    def update(self, attempt, tenant_id):
        self.attempts[(attempt.event_id, attempt.subscription_id)] = attempt
        return attempt


class StaticHttpGateway:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def post(self, request):
        self.requests.append(request)
        return self.response


class RecordingCircuitBreaker:
    def __init__(self, decision=None):
        self.decision = decision or CircuitBreakerDecision(allowed=True, state="closed")
        self.successes = []
        self.failures = []

    def before_request(self, *, tenant_id, target_url):
        return self.decision

    def record_success(self, *, tenant_id, target_url):
        self.successes.append((tenant_id, target_url))

    def record_failure(self, *, tenant_id, target_url):
        self.failures.append((tenant_id, target_url))


def test_tenant_queue_name_is_stable_and_bucketed():
    assert tenant_queue_name("tenant-1", buckets=4) == tenant_queue_name("tenant-1", buckets=4)
    assert tenant_queue_name("tenant-1", buckets=4).startswith("webhooks.delivery.tenant-")
    assert delivery_task_id("attempt-1") == "webhook-delivery:attempt-1"


def test_fanout_creates_attempts_only_for_matching_active_subscriptions():
    event = WebhookEvent(id="event-1", tenant_id="tenant-1", event_type="po.created")
    subscriptions = [
        Subscription(id="sub-1", tenant_id="tenant-1", event_type="po.*", target_url="https://a.test/webhook"),
        Subscription(id="sub-2", tenant_id="tenant-1", event_type="invoice.*", target_url="https://b.test/webhook"),
    ]
    attempts = MemoryDeliveryAttemptRepository()
    enqueued = []

    count = FanOutEvent(
        event_repository=MemoryEventRepository([event]),
        subscription_repository=MemorySubscriptionRepository(subscriptions),
        delivery_attempt_repository=attempts,
        enqueue_delivery=lambda attempt, tenant_id: enqueued.append((attempt.id, tenant_id)),
    )(event_id="event-1", tenant_id="tenant-1")

    assert count == 1
    assert len(attempts.attempts) == 1
    assert enqueued[0][1] == "tenant-1"
    assert event.processed is True


def test_fanout_rerun_reuses_existing_attempt_without_duplicate_creation():
    event = WebhookEvent(id="event-1", tenant_id="tenant-1", event_type="po.created")
    subscription = Subscription(
        id="sub-1",
        tenant_id="tenant-1",
        event_type="po.*",
        target_url="https://a.test/webhook",
    )
    attempts = MemoryDeliveryAttemptRepository()
    attempts.create(
        DeliveryAttempt(id="attempt-1", event_id=event.id, subscription_id=subscription.id),
        "tenant-1",
    )
    enqueued = []

    count = FanOutEvent(
        event_repository=MemoryEventRepository([event]),
        subscription_repository=MemorySubscriptionRepository([subscription]),
        delivery_attempt_repository=attempts,
        enqueue_delivery=lambda attempt, tenant_id: enqueued.append((attempt.id, tenant_id)),
    )(event_id="event-1", tenant_id="tenant-1")

    assert count == 1
    assert len(attempts.attempts) == 1
    assert enqueued == [("attempt-1", "tenant-1")]


def test_deliver_webhook_marks_success_and_sends_signature_headers():
    event = WebhookEvent(id="event-1", tenant_id="tenant-1", event_type="po.created", payload={"id": "PO-1"})
    subscription = Subscription(
        id="sub-1",
        tenant_id="tenant-1",
        event_type="po.*",
        target_url="https://a.test/webhook",
        secret="secret",
    )
    attempts = MemoryDeliveryAttemptRepository()
    attempt = attempts.create(DeliveryAttempt(id="attempt-1", event_id=event.id, subscription_id=subscription.id), "tenant-1")
    gateway = StaticHttpGateway(HttpResponse(status_code=204, body="ok"))
    breaker = RecordingCircuitBreaker()

    result = DeliverWebhook(
        event_repository=MemoryEventRepository([event]),
        subscription_repository=MemorySubscriptionRepository([subscription]),
        delivery_attempt_repository=attempts,
        http_gateway=gateway,
        enqueue_retry=lambda attempt, tenant_id, countdown: None,
        circuit_breaker=breaker,
        max_retries=3,
        base_retry_delay=1,
        max_retry_delay=60,
        retry_jitter=0,
        connect_timeout=5,
        read_timeout=15,
    )(attempt_id=attempt.id, tenant_id="tenant-1")

    assert result.status == DeliveryStatus.SUCCESS
    assert gateway.requests[0].headers[SIGNATURE_HEADER_NAME].startswith("sha256=")
    assert gateway.requests[0].headers[SIGNATURE_VERSION_HEADER_NAME] == SIGNATURE_VERSION
    assert gateway.requests[0].headers[TIMESTAMP_HEADER_NAME]
    assert verify_signature_headers(
        "secret",
        gateway.requests[0].body,
        gateway.requests[0].headers,
    ) is True
    assert breaker.successes == [("tenant-1", "https://a.test/webhook")]
    assert breaker.failures == []


def test_deliver_webhook_skips_already_in_progress_attempt():
    event = WebhookEvent(id="event-1", tenant_id="tenant-1", event_type="po.created")
    subscription = Subscription(
        id="sub-1",
        tenant_id="tenant-1",
        event_type="po.*",
        target_url="https://a.test/webhook",
        secret="secret",
    )
    attempts = MemoryDeliveryAttemptRepository()
    attempt = DeliveryAttempt(id="attempt-1", event_id=event.id, subscription_id=subscription.id)
    attempt.mark_in_progress()
    attempts.create(attempt, "tenant-1")
    gateway = StaticHttpGateway(HttpResponse(status_code=204, body="ok"))

    result = DeliverWebhook(
        event_repository=MemoryEventRepository([event]),
        subscription_repository=MemorySubscriptionRepository([subscription]),
        delivery_attempt_repository=attempts,
        http_gateway=gateway,
        enqueue_retry=lambda attempt, tenant_id, countdown: None,
        max_retries=3,
        base_retry_delay=1,
        max_retry_delay=60,
        retry_jitter=0,
        connect_timeout=5,
        read_timeout=15,
    )(attempt_id=attempt.id, tenant_id="tenant-1")

    assert result.status == DeliveryStatus.IN_PROGRESS
    assert gateway.requests == []


def test_deliver_webhook_waits_for_future_retry_window():
    event = WebhookEvent(id="event-1", tenant_id="tenant-1", event_type="po.created")
    subscription = Subscription(
        id="sub-1",
        tenant_id="tenant-1",
        event_type="po.*",
        target_url="https://a.test/webhook",
        secret="secret",
    )
    attempts = MemoryDeliveryAttemptRepository()
    attempt = DeliveryAttempt(id="attempt-1", event_id=event.id, subscription_id=subscription.id)
    attempt.mark_retrying(datetime.now(UTC) + timedelta(seconds=60))
    attempts.create(attempt, "tenant-1")
    gateway = StaticHttpGateway(HttpResponse(status_code=204, body="ok"))

    result = DeliverWebhook(
        event_repository=MemoryEventRepository([event]),
        subscription_repository=MemorySubscriptionRepository([subscription]),
        delivery_attempt_repository=attempts,
        http_gateway=gateway,
        enqueue_retry=lambda attempt, tenant_id, countdown: None,
        max_retries=3,
        base_retry_delay=1,
        max_retry_delay=60,
        retry_jitter=0,
        connect_timeout=5,
        read_timeout=15,
    )(attempt_id=attempt.id, tenant_id="tenant-1")

    assert result.status == DeliveryStatus.RETRYING
    assert gateway.requests == []


def test_deliver_webhook_schedules_retry_for_failed_response():
    event = WebhookEvent(id="event-1", tenant_id="tenant-1", event_type="po.created")
    subscription = Subscription(
        id="sub-1",
        tenant_id="tenant-1",
        event_type="po.*",
        target_url="https://a.test/webhook",
        secret="secret",
    )
    attempts = MemoryDeliveryAttemptRepository()
    attempt = attempts.create(DeliveryAttempt(id="attempt-1", event_id=event.id, subscription_id=subscription.id), "tenant-1")
    retries = []
    breaker = RecordingCircuitBreaker()

    result = DeliverWebhook(
        event_repository=MemoryEventRepository([event]),
        subscription_repository=MemorySubscriptionRepository([subscription]),
        delivery_attempt_repository=attempts,
        http_gateway=StaticHttpGateway(HttpResponse(status_code=503, body="unavailable")),
        enqueue_retry=lambda attempt, tenant_id, countdown: retries.append((attempt.id, tenant_id, countdown)),
        circuit_breaker=breaker,
        max_retries=3,
        base_retry_delay=1,
        max_retry_delay=60,
        retry_jitter=0,
        connect_timeout=5,
        read_timeout=15,
    )(attempt_id=attempt.id, tenant_id="tenant-1")

    assert result.status == DeliveryStatus.RETRYING
    assert result.attempt_number == 2
    assert retries
    assert breaker.failures == [("tenant-1", "https://a.test/webhook")]


def test_deliver_webhook_short_circuits_when_circuit_breaker_is_open():
    event = WebhookEvent(id="event-1", tenant_id="tenant-1", event_type="po.created")
    subscription = Subscription(
        id="sub-1",
        tenant_id="tenant-1",
        event_type="po.*",
        target_url="https://a.test/webhook",
        secret="secret",
    )
    attempts = MemoryDeliveryAttemptRepository()
    attempt = attempts.create(
        DeliveryAttempt(id="attempt-1", event_id=event.id, subscription_id=subscription.id),
        "tenant-1",
    )
    gateway = StaticHttpGateway(HttpResponse(status_code=204, body="ok"))
    retries = []
    breaker = RecordingCircuitBreaker(
        CircuitBreakerDecision(
            allowed=False,
            state="open",
            retry_after_seconds=30.0,
        )
    )

    result = DeliverWebhook(
        event_repository=MemoryEventRepository([event]),
        subscription_repository=MemorySubscriptionRepository([subscription]),
        delivery_attempt_repository=attempts,
        http_gateway=gateway,
        enqueue_retry=lambda attempt, tenant_id, countdown: retries.append((attempt.id, tenant_id, countdown)),
        circuit_breaker=breaker,
        max_retries=3,
        base_retry_delay=1,
        max_retry_delay=60,
        retry_jitter=0,
        connect_timeout=5,
        read_timeout=15,
    )(attempt_id=attempt.id, tenant_id="tenant-1")

    assert result.status == DeliveryStatus.RETRYING
    assert gateway.requests == []
    assert retries[0][2] >= 30.0


def test_deliver_webhook_dead_letters_after_retry_budget_is_exhausted():
    event = WebhookEvent(id="event-1", tenant_id="tenant-1", event_type="po.created")
    subscription = Subscription(
        id="sub-1",
        tenant_id="tenant-1",
        event_type="po.*",
        target_url="https://a.test/webhook",
        secret="secret",
    )
    attempts = MemoryDeliveryAttemptRepository()
    attempt = attempts.create(
        DeliveryAttempt(
            id="attempt-1",
            event_id=event.id,
            subscription_id=subscription.id,
            attempt_number=3,
        ),
        "tenant-1",
    )
    retries = []

    result = DeliverWebhook(
        event_repository=MemoryEventRepository([event]),
        subscription_repository=MemorySubscriptionRepository([subscription]),
        delivery_attempt_repository=attempts,
        http_gateway=StaticHttpGateway(HttpResponse(status_code=503, body="unavailable")),
        enqueue_retry=lambda attempt, tenant_id, countdown: retries.append((attempt.id, tenant_id, countdown)),
        max_retries=3,
        base_retry_delay=1,
        max_retry_delay=60,
        retry_jitter=0,
        connect_timeout=5,
        read_timeout=15,
    )(attempt_id=attempt.id, tenant_id="tenant-1")

    assert result.status == DeliveryStatus.DEAD_LETTER
    assert retries == []
