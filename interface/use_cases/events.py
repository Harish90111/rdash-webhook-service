"""Event ingestion use cases."""

from dataclasses import dataclass
from typing import Callable, Mapping, Optional

from domain.entities import WebhookEvent
from domain.exceptions import DuplicateEventError
from domain.interfaces import EventRepository
from domain.services import build_idempotency_key, normalize_idempotency_key


PersistEventWithOutbox = Callable[[WebhookEvent], WebhookEvent]


@dataclass(frozen=True)
class IngestEventResult:
    """Event ingestion result."""

    event: WebhookEvent
    created: bool


class IngestEvent:
    """
    Persist an event before queueing fan-out intent.

    Duplicate submissions return the existing event and never create another
    outbox row.
    """

    def __init__(
        self,
        event_repository: EventRepository,
        persist_event_with_outbox: PersistEventWithOutbox,
    ):
        self.event_repository = event_repository
        self.persist_event_with_outbox = persist_event_with_outbox

    def __call__(
        self,
        *,
        tenant_id: str,
        event_type: str,
        payload: Mapping[str, object],
        idempotency_key: Optional[str] = None,
    ) -> IngestEventResult:
        normalized_key = normalize_idempotency_key(idempotency_key)
        if normalized_key is None:
            normalized_key = build_idempotency_key(tenant_id, event_type, payload)

        existing_event = self.event_repository.get_by_idempotency_key(
            tenant_id,
            normalized_key,
        )
        if existing_event is not None:
            return IngestEventResult(event=existing_event, created=False)

        event = WebhookEvent(
            tenant_id=tenant_id,
            event_type=event_type,
            payload=dict(payload),
            idempotency_key=normalized_key,
        )

        try:
            persisted_event = self.persist_event_with_outbox(event)
        except DuplicateEventError:
            existing_event = self.event_repository.get_by_idempotency_key(
                tenant_id,
                normalized_key,
            )
            if existing_event is not None:
                return IngestEventResult(event=existing_event, created=False)
            raise

        return IngestEventResult(event=persisted_event, created=True)
