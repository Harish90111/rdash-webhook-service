"""Django ORM models for the webhook delivery service."""

import inspect
import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone


CHECK_CONSTRAINT_ARGUMENT = (
    "condition"
    if "condition" in inspect.signature(models.CheckConstraint.__init__).parameters
    else "check"
)


def positive_check_constraint(*, query: Q, name: str) -> models.CheckConstraint:
    """Build a CheckConstraint compatible with supported Django versions."""

    return models.CheckConstraint(name=name, **{CHECK_CONSTRAINT_ARGUMENT: query})


class TimestampedModel(models.Model):
    """Shared audit timestamps for data-layer records."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Tenant(TimestampedModel):
    """Organization boundary used for hard tenant isolation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "webhook_tenant"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug"], name="tenant_slug_idx"),
            models.Index(fields=["is_active"], name="tenant_active_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class TenantAPIKey(TimestampedModel):
    """
    Hashed API key material for principal-based tenant authentication.

    Key generation and verification live in the security phase. The data model
    stores only lookup-safe metadata and a hash, never the raw API key.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        related_name="api_keys",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    key_prefix = models.CharField(max_length=16)
    key_hash = models.CharField(max_length=128, unique=True)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "webhook_tenant_api_key"
        ordering = ["tenant_id", "name"]
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="api_key_tenant_active_idx"),
            models.Index(fields=["key_prefix"], name="api_key_prefix_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "key_prefix"],
                name="uniq_api_key_prefix_per_tenant",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.name}"


class Subscription(TimestampedModel):
    """Subscriber endpoint registration for one tenant and event pattern."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        related_name="subscriptions",
        on_delete=models.CASCADE,
    )
    event_type = models.CharField(max_length=255)
    target_url = models.URLField(max_length=2048)
    active = models.BooleanField(default=True)
    secret_hash = models.CharField(max_length=128)
    secret_encrypted = models.TextField(blank=True, default="")

    class Meta:
        db_table = "webhook_subscription"
        ordering = ["tenant_id", "event_type", "target_url"]
        indexes = [
            models.Index(fields=["tenant", "active"], name="subscription_tenant_active_idx"),
            models.Index(fields=["tenant", "event_type"], name="subscription_tenant_event_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "event_type", "target_url"],
                name="uniq_subscription_target_event",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.event_type}->{self.target_url}"


class WebhookEvent(TimestampedModel):
    """Persisted inbound event before fan-out."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        related_name="events",
        on_delete=models.CASCADE,
    )
    event_type = models.CharField(max_length=255)
    payload = models.JSONField(default=dict)
    idempotency_key = models.CharField(max_length=255, null=True, blank=True)
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "webhook_event"
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["tenant", "event_type"], name="event_tenant_type_idx"),
            models.Index(fields=["tenant", "processed"], name="event_tenant_processed_idx"),
            models.Index(fields=["received_at"], name="event_received_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "idempotency_key"],
                condition=Q(idempotency_key__isnull=False),
                name="uniq_event_idempotency_per_tenant",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.event_type}:{self.id}"


class DeliveryStatus(models.TextChoices):
    """Database values mirroring domain delivery status."""

    PENDING = "pending", "Pending"
    IN_PROGRESS = "in_progress", "In progress"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    RETRYING = "retrying", "Retrying"
    DEAD_LETTER = "dead_letter", "Dead letter"


class DeliveryAttempt(TimestampedModel):
    """Current delivery state for one event/subscription pair."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        WebhookEvent,
        related_name="delivery_attempts",
        on_delete=models.CASCADE,
    )
    subscription = models.ForeignKey(
        Subscription,
        related_name="delivery_attempts",
        on_delete=models.CASCADE,
    )
    status = models.CharField(
        max_length=32,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
    )
    attempt_number = models.PositiveIntegerField(default=1)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    response_body = models.TextField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "webhook_delivery_attempt"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event", "subscription"], name="delivery_event_sub_idx"),
            models.Index(fields=["status", "next_retry_at"], name="delivery_status_retry_idx"),
            models.Index(fields=["subscription", "status"], name="delivery_sub_status_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "subscription"],
                name="uniq_delivery_event_subscription",
            ),
            positive_check_constraint(
                query=Q(attempt_number__gte=1),
                name="delivery_attempt_number_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event_id}->{self.subscription_id}:{self.status}"


class OutboxStatus(models.TextChoices):
    """Database values for durable broker-publish intent."""

    PENDING = "pending", "Pending"
    IN_PROGRESS = "in_progress", "In progress"
    PUBLISHED = "published", "Published"
    FAILED = "failed", "Failed"


class OutboxMessage(TimestampedModel):
    """
    Durable task intent written in the same transaction as a webhook event.

    A separate dispatcher can later publish pending rows to Celery. This keeps
    event ingestion reliable when Redis or workers are temporarily unavailable.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        related_name="outbox_messages",
        on_delete=models.CASCADE,
    )
    event = models.ForeignKey(
        WebhookEvent,
        related_name="outbox_messages",
        on_delete=models.CASCADE,
    )
    task_name = models.CharField(max_length=255)
    queue_name = models.CharField(max_length=120, blank=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=32,
        choices=OutboxStatus.choices,
        default=OutboxStatus.PENDING,
    )
    attempts = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.CharField(max_length=255, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        db_table = "webhook_outbox_message"
        ordering = ["available_at", "created_at"]
        indexes = [
            models.Index(fields=["status", "available_at"], name="outbox_status_available_idx"),
            models.Index(fields=["tenant", "status"], name="outbox_tenant_status_idx"),
            models.Index(fields=["event", "task_name"], name="outbox_event_task_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "task_name"],
                name="uniq_outbox_event_task",
            ),
            positive_check_constraint(
                query=Q(attempts__gte=0),
                name="outbox_attempts_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event_id}:{self.task_name}:{self.status}"
