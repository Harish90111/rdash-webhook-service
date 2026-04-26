from types import SimpleNamespace

from rest_framework import status
from rest_framework.test import APIRequestFactory

from interface.views.events import EventIngestionView


class MemoryEventRepository:
    events = {}

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


def persist_with_outbox(event):
    return MemoryEventRepository().create(event)


class TestEventIngestionView(EventIngestionView):
    event_repository_class = MemoryEventRepository
    persist_event_with_outbox = staticmethod(persist_with_outbox)


def authenticated_request(data):
    factory = APIRequestFactory()
    request = factory.post("/api/events/", data=data, format="json")
    request.user = SimpleNamespace(is_authenticated=True, tenant_id="tenant-1")
    return request


def test_event_ingestion_creates_event_from_principal_tenant():
    MemoryEventRepository.events = {}
    view = TestEventIngestionView.as_view()
    request = authenticated_request(
        {
            "event_type": "po.created",
            "payload": {"id": "PO-1"},
            "idempotency_key": "key-1",
        }
    )

    response = view(request)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["data"]["tenant_id"] == "tenant-1"
    assert response.data["meta"]["idempotent_replay"] is False


def test_event_ingestion_returns_200_for_duplicate_submission():
    MemoryEventRepository.events = {}
    view = TestEventIngestionView.as_view()
    payload = {
        "event_type": "po.created",
        "payload": {"id": "PO-1"},
        "idempotency_key": "key-1",
    }

    first_response = view(authenticated_request(payload))
    second_response = view(authenticated_request(payload))

    assert first_response.status_code == status.HTTP_201_CREATED
    assert second_response.status_code == status.HTTP_200_OK
    assert second_response.data["data"]["id"] == first_response.data["data"]["id"]
    assert second_response.data["meta"]["idempotent_replay"] is True


def test_event_ingestion_rejects_body_tenant_id():
    view = TestEventIngestionView.as_view()
    request = authenticated_request(
        {
            "tenant_id": "attacker",
            "event_type": "po.created",
            "payload": {"id": "PO-1"},
        }
    )

    response = view(request)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
