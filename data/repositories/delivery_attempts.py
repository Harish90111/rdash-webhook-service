"""Django implementation of the delivery attempt repository contract."""

from typing import Optional, Sequence

from django.db import IntegrityError

from data.models.models import DeliveryAttempt as DeliveryAttemptModel
from data.models.models import Subscription as SubscriptionModel
from data.models.models import WebhookEvent as WebhookEventModel
from domain.entities import DeliveryAttempt, DeliveryStatus
from domain.exceptions import (
    DeliveryAttemptNotFoundError,
    DuplicateEventError,
    EventNotFoundError,
    SubscriptionNotFoundError,
)


class DjangoDeliveryAttemptRepository:
    """Tenant-scoped delivery attempt persistence using the Django ORM."""

    def create(self, attempt: DeliveryAttempt, tenant_id: str) -> DeliveryAttempt:
        self._ensure_event_exists(attempt.event_id, tenant_id)
        self._ensure_subscription_exists(attempt.subscription_id, tenant_id)
        try:
            model = DeliveryAttemptModel.objects.create(
                id=attempt.id,
                event_id=attempt.event_id,
                subscription_id=attempt.subscription_id,
                status=attempt.status.value,
                attempt_number=attempt.attempt_number,
                status_code=attempt.status_code,
                response_body=attempt.response_body,
                error_message=attempt.error_message,
                next_retry_at=attempt.next_retry_at,
                completed_at=attempt.completed_at,
            )
        except IntegrityError as exc:
            raise DuplicateEventError(
                "Delivery attempt already exists for this event/subscription pair.",
                context={
                    "event_id": attempt.event_id,
                    "subscription_id": attempt.subscription_id,
                    "tenant_id": tenant_id,
                },
            ) from exc
        return self._to_domain(model)

    def get_by_id(self, attempt_id: str, tenant_id: str) -> DeliveryAttempt:
        return self._to_domain(self._get_model(attempt_id, tenant_id))

    def find_by_event_and_subscription(
        self,
        event_id: str,
        subscription_id: str,
        tenant_id: str,
    ) -> Optional[DeliveryAttempt]:
        model = self._tenant_scoped_queryset(tenant_id).filter(
            event_id=event_id,
            subscription_id=subscription_id,
        ).first()
        return self._to_domain(model) if model else None

    def list_for_event(self, event_id: str, tenant_id: str) -> Sequence[DeliveryAttempt]:
        queryset = self._tenant_scoped_queryset(tenant_id).filter(event_id=event_id)
        return [self._to_domain(model) for model in queryset]

    def update(self, attempt: DeliveryAttempt, tenant_id: str) -> DeliveryAttempt:
        model = self._get_model(attempt.id, tenant_id)
        model.status = attempt.status.value
        model.attempt_number = attempt.attempt_number
        model.status_code = attempt.status_code
        model.response_body = attempt.response_body
        model.error_message = attempt.error_message
        model.next_retry_at = attempt.next_retry_at
        model.completed_at = attempt.completed_at
        model.save(
            update_fields=[
                "status",
                "attempt_number",
                "status_code",
                "response_body",
                "error_message",
                "next_retry_at",
                "completed_at",
                "updated_at",
            ]
        )
        return self._to_domain(model)

    @staticmethod
    def _ensure_event_exists(event_id: str, tenant_id: str) -> None:
        if not WebhookEventModel.objects.filter(id=event_id, tenant_id=tenant_id).exists():
            raise EventNotFoundError(context={"event_id": event_id, "tenant_id": tenant_id})

    @staticmethod
    def _ensure_subscription_exists(subscription_id: str, tenant_id: str) -> None:
        if not SubscriptionModel.objects.filter(
            id=subscription_id,
            tenant_id=tenant_id,
        ).exists():
            raise SubscriptionNotFoundError(
                context={"subscription_id": subscription_id, "tenant_id": tenant_id}
            )

    @staticmethod
    def _tenant_scoped_queryset(tenant_id: str):
        return DeliveryAttemptModel.objects.select_related("event", "subscription").filter(
            event__tenant_id=tenant_id,
            subscription__tenant_id=tenant_id,
        )

    def _get_model(self, attempt_id: str, tenant_id: str) -> DeliveryAttemptModel:
        try:
            return self._tenant_scoped_queryset(tenant_id).get(id=attempt_id)
        except DeliveryAttemptModel.DoesNotExist as exc:
            raise DeliveryAttemptNotFoundError(
                context={"attempt_id": attempt_id, "tenant_id": tenant_id}
            ) from exc

    @staticmethod
    def _to_domain(model: DeliveryAttemptModel) -> DeliveryAttempt:
        return DeliveryAttempt(
            id=str(model.id),
            event_id=str(model.event_id),
            subscription_id=str(model.subscription_id),
            status=DeliveryStatus(model.status),
            attempt_number=model.attempt_number,
            status_code=model.status_code,
            response_body=model.response_body,
            error_message=model.error_message,
            next_retry_at=model.next_retry_at,
            created_at=model.created_at,
            completed_at=model.completed_at,
        )
