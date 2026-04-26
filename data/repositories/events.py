"""Django implementation of the webhook event repository contract."""

from typing import Optional

from django.db import IntegrityError
from django.utils import timezone

from data.models.models import Tenant
from data.models.models import WebhookEvent as WebhookEventModel
from domain.entities import WebhookEvent
from domain.exceptions import DuplicateEventError, EventNotFoundError


class DjangoEventRepository:
    """Tenant-scoped event persistence using the Django ORM."""

    def create(self, event: WebhookEvent) -> WebhookEvent:
        self._ensure_tenant_exists(event.tenant_id)
        try:
            model = WebhookEventModel.objects.create(
                id=event.id,
                tenant_id=event.tenant_id,
                event_type=event.event_type,
                payload=dict(event.payload),
                idempotency_key=event.idempotency_key,
                processed=event.processed,
                processed_at=timezone.now() if event.processed else None,
            )
        except IntegrityError as exc:
            raise DuplicateEventError(
                context={
                    "tenant_id": event.tenant_id,
                    "idempotency_key": event.idempotency_key,
                }
            ) from exc
        return self._to_domain(model)

    def get_by_id(self, event_id: str, tenant_id: str) -> WebhookEvent:
        return self._to_domain(self._get_model(event_id, tenant_id))

    def get_by_idempotency_key(
        self,
        tenant_id: str,
        idempotency_key: str,
    ) -> Optional[WebhookEvent]:
        if not idempotency_key:
            return None
        model = WebhookEventModel.objects.filter(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
        ).first()
        return self._to_domain(model) if model else None

    def mark_processed(self, event_id: str, tenant_id: str) -> None:
        updated_count = WebhookEventModel.objects.filter(
            id=event_id,
            tenant_id=tenant_id,
        ).update(processed=True, processed_at=timezone.now())
        if updated_count == 0:
            raise EventNotFoundError(context={"event_id": event_id, "tenant_id": tenant_id})

    @staticmethod
    def _ensure_tenant_exists(tenant_id: str) -> None:
        if not Tenant.objects.filter(id=tenant_id, is_active=True).exists():
            raise EventNotFoundError(context={"tenant_id": tenant_id})

    @staticmethod
    def _get_model(event_id: str, tenant_id: str) -> WebhookEventModel:
        try:
            return WebhookEventModel.objects.get(id=event_id, tenant_id=tenant_id)
        except WebhookEventModel.DoesNotExist as exc:
            raise EventNotFoundError(
                context={"event_id": event_id, "tenant_id": tenant_id}
            ) from exc

    @staticmethod
    def _to_domain(model: WebhookEventModel) -> WebhookEvent:
        return WebhookEvent(
            id=str(model.id),
            tenant_id=str(model.tenant_id),
            event_type=model.event_type,
            payload=dict(model.payload),
            idempotency_key=model.idempotency_key,
            timestamp=model.received_at,
            processed=model.processed,
        )
