"""Django implementation of the subscription repository contract."""

from typing import Sequence

from django.db import IntegrityError

from data.models.models import Subscription as SubscriptionModel
from data.models.models import Tenant
from domain.entities import Subscription
from domain.exceptions import SubscriptionNotFoundError


class DjangoSubscriptionRepository:
    """Tenant-scoped subscription persistence using the Django ORM."""

    def create(self, subscription: Subscription) -> Subscription:
        self._ensure_tenant_exists(subscription.tenant_id)
        try:
            model = SubscriptionModel.objects.create(
                id=subscription.id,
                tenant_id=subscription.tenant_id,
                event_type=subscription.event_type,
                target_url=subscription.target_url,
                active=subscription.active,
                secret_hash=subscription.secret,
            )
        except IntegrityError as exc:
            raise ValueError("subscription violates a persistence constraint") from exc
        return self._to_domain(model, secret=subscription.secret)

    def get_by_id(self, subscription_id: str, tenant_id: str) -> Subscription:
        return self._to_domain(self._get_model(subscription_id, tenant_id))

    def list_by_tenant(self, tenant_id: str) -> Sequence[Subscription]:
        queryset = SubscriptionModel.objects.filter(tenant_id=tenant_id).order_by(
            "event_type",
            "target_url",
        )
        return [self._to_domain(model) for model in queryset]

    def list_active_by_tenant(self, tenant_id: str) -> Sequence[Subscription]:
        queryset = SubscriptionModel.objects.filter(
            tenant_id=tenant_id,
            active=True,
        ).order_by("event_type", "target_url")
        return [self._to_domain(model) for model in queryset]

    def update(self, subscription: Subscription) -> Subscription:
        model = self._get_model(subscription.id, subscription.tenant_id)
        model.event_type = subscription.event_type
        model.target_url = subscription.target_url
        model.active = subscription.active
        if subscription.secret:
            model.secret_hash = subscription.secret
        model.save(
            update_fields=[
                "event_type",
                "target_url",
                "active",
                "secret_hash",
                "updated_at",
            ]
        )
        return self._to_domain(model, secret=subscription.secret)

    def delete(self, subscription_id: str, tenant_id: str) -> None:
        deleted_count, _ = SubscriptionModel.objects.filter(
            id=subscription_id,
            tenant_id=tenant_id,
        ).delete()
        if deleted_count == 0:
            raise SubscriptionNotFoundError(
                context={"subscription_id": subscription_id, "tenant_id": tenant_id}
            )

    @staticmethod
    def _ensure_tenant_exists(tenant_id: str) -> None:
        if not Tenant.objects.filter(id=tenant_id, is_active=True).exists():
            raise SubscriptionNotFoundError(context={"tenant_id": tenant_id})

    @staticmethod
    def _get_model(subscription_id: str, tenant_id: str) -> SubscriptionModel:
        try:
            return SubscriptionModel.objects.get(id=subscription_id, tenant_id=tenant_id)
        except SubscriptionModel.DoesNotExist as exc:
            raise SubscriptionNotFoundError(
                context={"subscription_id": subscription_id, "tenant_id": tenant_id}
            ) from exc

    @staticmethod
    def _to_domain(model: SubscriptionModel, secret: str = "") -> Subscription:
        return Subscription(
            id=str(model.id),
            tenant_id=str(model.tenant_id),
            event_type=model.event_type,
            target_url=model.target_url,
            active=model.active,
            secret=secret,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
