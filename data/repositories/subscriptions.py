"""Django implementation of the subscription repository contract."""

import hashlib
from typing import Sequence

from django.db import IntegrityError

from data.models.models import Subscription as SubscriptionModel
from data.models.models import Tenant
from data.security import DjangoSubscriptionSecretCipher
from domain.entities import Subscription
from domain.exceptions import SubscriptionNotFoundError


class DjangoSubscriptionRepository:
    """Tenant-scoped subscription persistence using the Django ORM."""

    def __init__(self, *, secret_cipher=None) -> None:
        self.secret_cipher = secret_cipher or DjangoSubscriptionSecretCipher()

    def create(self, subscription: Subscription) -> Subscription:
        self._ensure_tenant_exists(subscription.tenant_id)
        raw_secret = self._normalize_raw_secret(subscription.secret)
        try:
            model = SubscriptionModel.objects.create(
                id=subscription.id,
                tenant_id=subscription.tenant_id,
                event_type=subscription.event_type,
                target_url=subscription.target_url,
                active=subscription.active,
                secret_hash=self._hash_secret(raw_secret),
                secret_encrypted=self.secret_cipher.encrypt(raw_secret),
            )
        except IntegrityError as exc:
            raise ValueError("subscription violates a persistence constraint") from exc
        return self._to_domain(model, secret=raw_secret)

    def get_by_id(self, subscription_id: str, tenant_id: str) -> Subscription:
        return self._to_domain(self._get_model(subscription_id, tenant_id), reveal_secret=True)

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
        update_fields = [
            "event_type",
            "target_url",
            "active",
            "updated_at",
        ]
        if subscription.secret:
            raw_secret = self._normalize_raw_secret(subscription.secret)
            model.secret_hash = self._hash_secret(raw_secret)
            model.secret_encrypted = self.secret_cipher.encrypt(raw_secret)
            update_fields.extend(["secret_hash", "secret_encrypted"])
        model.save(update_fields=update_fields)
        return self._to_domain(model, secret=subscription.secret, reveal_secret=bool(subscription.secret))

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

    def _to_domain(
        self,
        model: SubscriptionModel,
        *,
        secret: str = "",
        reveal_secret: bool = False,
    ) -> Subscription:
        resolved_secret = secret
        if reveal_secret and not resolved_secret and model.secret_encrypted:
            resolved_secret = self.secret_cipher.decrypt(model.secret_encrypted)
        return Subscription(
            id=str(model.id),
            tenant_id=str(model.tenant_id),
            event_type=model.event_type,
            target_url=model.target_url,
            active=model.active,
            secret=resolved_secret,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _hash_secret(raw_secret: str) -> str:
        return hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_raw_secret(raw_secret: str) -> str:
        normalized_secret = (raw_secret or "").strip()
        if not normalized_secret:
            raise ValueError("subscription.secret is required")
        return normalized_secret
