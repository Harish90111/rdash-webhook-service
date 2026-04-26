from interface.use_cases.events import IngestEvent


class MemoryEventRepository:
    def __init__(self):
        self.events = {}

    def create(self, event):
        self.events[(event.tenant_id, event.idempotency_key)] = event
        return event

    def get_by_id(self, event_id, tenant_id):
        return next(
            event
            for event in self.events.values()
            if event.id == event_id and event.tenant_id == tenant_id
        )

    def get_by_idempotency_key(self, tenant_id, idempotency_key):
        return self.events.get((tenant_id, idempotency_key))

    def mark_processed(self, event_id, tenant_id):
        self.get_by_id(event_id, tenant_id).mark_processed()


def test_ingest_event_persists_new_event_with_outbox_callback():
    repository = MemoryEventRepository()
    outbox_calls = []

    def persist_with_outbox(event):
        outbox_calls.append(event.id)
        return repository.create(event)

    result = IngestEvent(repository, persist_with_outbox)(
        tenant_id="tenant-1",
        event_type="po.created",
        payload={"id": "PO-1"},
        idempotency_key="key-1",
    )

    assert result.created is True
    assert result.event.idempotency_key == "key-1"
    assert outbox_calls == [result.event.id]


def test_ingest_event_returns_existing_event_for_duplicate_key_without_outbox_call():
    repository = MemoryEventRepository()
    outbox_calls = []

    def persist_with_outbox(event):
        outbox_calls.append(event.id)
        return repository.create(event)

    first = IngestEvent(repository, persist_with_outbox)(
        tenant_id="tenant-1",
        event_type="po.created",
        payload={"id": "PO-1"},
        idempotency_key="key-1",
    )
    second = IngestEvent(repository, persist_with_outbox)(
        tenant_id="tenant-1",
        event_type="po.created",
        payload={"id": "PO-1"},
        idempotency_key="key-1",
    )

    assert first.created is True
    assert second.created is False
    assert second.event.id == first.event.id
    assert outbox_calls == [first.event.id]


def test_ingest_event_builds_fallback_idempotency_key_when_missing():
    repository = MemoryEventRepository()

    def persist_with_outbox(event):
        return repository.create(event)

    first = IngestEvent(repository, persist_with_outbox)(
        tenant_id="tenant-1",
        event_type="po.created",
        payload={"id": "PO-1"},
    )
    second = IngestEvent(repository, persist_with_outbox)(
        tenant_id="tenant-1",
        event_type="po.created",
        payload={"id": "PO-1"},
    )

    assert first.event.idempotency_key
    assert second.created is False
