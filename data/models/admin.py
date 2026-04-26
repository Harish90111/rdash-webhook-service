"""Django admin configuration for webhook data models."""

import hashlib

from django import forms
from django.contrib import admin, messages

from data.models.models import (
    DeliveryAttempt,
    OutboxMessage,
    Subscription,
    Tenant,
    TenantAPIKey,
    WebhookEvent,
)
from data.repositories import DjangoTenantAPIKeyRepository
from data.security import DjangoSubscriptionSecretCipher


def _normalize_secret(raw_secret: str) -> str:
    normalized_secret = (raw_secret or "").strip()
    if not normalized_secret:
        raise ValueError("signing_secret is required")
    return normalized_secret


def _hash_secret(raw_secret: str) -> str:
    return hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()


class SubscriptionAdminForm(forms.ModelForm):
    """Admin form that accepts plain-text signing secret input."""

    signing_secret = forms.CharField(
        label="Signing secret",
        required=False,
        strip=True,
        widget=forms.PasswordInput(render_value=True),
        help_text=(
            "Required when creating a subscription. Leave blank while editing "
            "to keep the current signing secret."
        ),
    )

    class Meta:
        model = Subscription
        fields = ("tenant", "event_type", "target_url", "active", "signing_secret")

    def clean(self):
        cleaned_data = super().clean()
        signing_secret = (cleaned_data.get("signing_secret") or "").strip()
        if not self.instance.pk and not signing_secret:
            self.add_error("signing_secret", "A signing secret is required.")
        cleaned_data["signing_secret"] = signing_secret
        return cleaned_data


class TenantAPIKeyAdminForm(forms.ModelForm):
    """Admin form that generates raw API keys on creation."""

    class Meta:
        model = TenantAPIKey
        fields = ("tenant", "name", "is_active", "expires_at")


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    ordering = ("name",)
    readonly_fields = ("id", "created_at", "updated_at")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(TenantAPIKey)
class TenantAPIKeyAdmin(admin.ModelAdmin):
    form = TenantAPIKeyAdminForm
    list_display = ("name", "tenant", "key_prefix", "is_active", "expires_at", "last_used_at")
    list_filter = ("is_active", "tenant")
    search_fields = ("name", "key_prefix", "tenant__name", "tenant__slug")
    autocomplete_fields = ("tenant",)
    readonly_fields = (
        "id",
        "key_prefix",
        "key_hash",
        "last_used_at",
        "created_at",
        "updated_at",
    )

    def get_fields(self, request, obj=None):
        if obj is None:
            return ("tenant", "name", "expires_at")
        return (
            "id",
            "tenant",
            "name",
            "is_active",
            "expires_at",
            "key_prefix",
            "key_hash",
            "last_used_at",
            "created_at",
            "updated_at",
        )

    def save_model(self, request, obj, form, change):
        if change:
            super().save_model(request, obj, form, change)
            return

        issued_key = DjangoTenantAPIKeyRepository().issue_for_tenant(
            str(form.cleaned_data["tenant"].id),
            form.cleaned_data["name"],
            expires_at=form.cleaned_data.get("expires_at"),
        )
        created_key = TenantAPIKey.objects.select_related("tenant").get(id=issued_key.id)
        obj.pk = created_key.pk
        obj.id = created_key.id
        obj.tenant = created_key.tenant
        obj.name = created_key.name
        obj.is_active = created_key.is_active
        obj.expires_at = created_key.expires_at
        obj.key_prefix = created_key.key_prefix
        obj.key_hash = created_key.key_hash
        obj.last_used_at = created_key.last_used_at
        obj.created_at = created_key.created_at
        obj.updated_at = created_key.updated_at
        obj._state.adding = False

        self.message_user(
            request,
            (
                "Raw API key for {name}: {raw_key}. Store it now because it "
                "will not be shown again."
            ).format(name=created_key.name, raw_key=issued_key.raw_key),
            level=messages.SUCCESS,
        )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    form = SubscriptionAdminForm
    list_display = ("event_type", "tenant", "target_url", "active", "created_at")
    list_filter = ("active", "tenant", "event_type")
    search_fields = ("event_type", "target_url", "tenant__name", "tenant__slug")
    autocomplete_fields = ("tenant",)
    readonly_fields = ("id", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        signing_secret = form.cleaned_data.get("signing_secret") or ""
        if signing_secret:
            normalized_secret = _normalize_secret(signing_secret)
            obj.secret_hash = _hash_secret(normalized_secret)
            obj.secret_encrypted = DjangoSubscriptionSecretCipher().encrypt(normalized_secret)
        super().save_model(request, obj, form, change)


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "tenant", "processed", "received_at", "processed_at")
    list_filter = ("processed", "tenant", "event_type")
    search_fields = (
        "id",
        "event_type",
        "idempotency_key",
        "tenant__name",
        "tenant__slug",
    )
    autocomplete_fields = ("tenant",)
    readonly_fields = ("id", "created_at", "updated_at", "received_at")


@admin.register(DeliveryAttempt)
class DeliveryAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "event",
        "subscription",
        "status",
        "attempt_number",
        "status_code",
        "next_retry_at",
        "completed_at",
    )
    list_filter = ("status", "subscription__tenant")
    search_fields = (
        "id",
        "event__id",
        "subscription__id",
        "subscription__target_url",
        "subscription__tenant__slug",
    )
    autocomplete_fields = ("event", "subscription")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(OutboxMessage)
class OutboxMessageAdmin(admin.ModelAdmin):
    list_display = ("task_name", "tenant", "event", "status", "attempts", "available_at")
    list_filter = ("status", "tenant", "task_name")
    search_fields = ("id", "task_name", "event__id", "tenant__name", "tenant__slug")
    autocomplete_fields = ("tenant", "event")
    readonly_fields = ("id", "created_at", "updated_at", "published_at")
