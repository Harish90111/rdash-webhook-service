from django.db import transaction
from django.test import TestCase

from data.models.models import OutboxMessage, OutboxStatus, Tenant
from data.repositories import (
    DEFAULT_FANOUT_TASK_NAME,
    DjangoOutboxRepository,
    DuplicateOutboxMessageError,
    create_event_with_outbox,
)
from domain.entities import WebhookEvent


class OutboxPatternTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Acme", slug="acme")
        self.outbox = DjangoOutboxRepository()

    def test_create_event_with_outbox_persists_event_and_pending_message_atomically(self):
        event = WebhookEvent(
            tenant_id=str(self.tenant.id),
            event_type="po.created",
            payload={"id": "PO-1"},
            idempotency_key="key-1",
        )

        persisted_event = create_event_with_outbox(event)

        message = OutboxMessage.objects.get(event_id=persisted_event.id)
        assert message.tenant_id == self.tenant.id
        assert message.task_name == DEFAULT_FANOUT_TASK_NAME
        assert message.status == OutboxStatus.PENDING
        assert message.payload == {
            "event_id": persisted_event.id,
            "tenant_id": str(self.tenant.id),
        }

    def test_create_for_event_rejects_duplicate_task_for_event(self):
        event = create_event_with_outbox(
            WebhookEvent(
                tenant_id=str(self.tenant.id),
                event_type="po.created",
                payload={"id": "PO-1"},
            )
        )

        with self.assertRaises(DuplicateOutboxMessageError):
            with transaction.atomic():
                self.outbox.create_for_event(event)

    def test_outbox_state_transitions_are_tenant_scoped(self):
        event = create_event_with_outbox(
            WebhookEvent(
                tenant_id=str(self.tenant.id),
                event_type="po.created",
                payload={"id": "PO-1"},
            )
        )
        message = OutboxMessage.objects.get(event_id=event.id)

        self.outbox.mark_published(str(message.id), str(self.tenant.id))

        message.refresh_from_db()
        assert message.status == OutboxStatus.PUBLISHED
        assert message.published_at is not None

    def test_lock_pending_batch_marks_messages_in_progress(self):
        create_event_with_outbox(
            WebhookEvent(
                tenant_id=str(self.tenant.id),
                event_type="po.created",
                payload={"id": "PO-1"},
            )
        )

        locked = self.outbox.lock_pending_batch(locked_by="worker-1", limit=10)

        assert len(locked) == 1
        message = OutboxMessage.objects.get(id=locked[0].id)
        assert message.status == OutboxStatus.IN_PROGRESS
        assert message.attempts == 1
        assert message.locked_by == "worker-1"
