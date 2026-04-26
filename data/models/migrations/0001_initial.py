"""Initial webhook data model schema."""

import inspect
import django.db.models.deletion
import uuid
from django.db import migrations, models
from django.db.models import Q


CHECK_CONSTRAINT_ARGUMENT = (
    "condition"
    if "condition" in inspect.signature(models.CheckConstraint.__init__).parameters
    else "check"
)


def positive_check_constraint(*, query: Q, name: str) -> models.CheckConstraint:
    return models.CheckConstraint(name=name, **{CHECK_CONSTRAINT_ARGUMENT: query})


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Tenant",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("slug", models.SlugField(max_length=120, unique=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "db_table": "webhook_tenant",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("event_type", models.CharField(max_length=255)),
                ("target_url", models.URLField(max_length=2048)),
                ("active", models.BooleanField(default=True)),
                ("secret_hash", models.CharField(max_length=128)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscriptions",
                        to="webhook_data.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "webhook_subscription",
                "ordering": ["tenant_id", "event_type", "target_url"],
            },
        ),
        migrations.CreateModel(
            name="TenantAPIKey",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("key_prefix", models.CharField(max_length=16)),
                ("key_hash", models.CharField(max_length=128, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="api_keys",
                        to="webhook_data.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "webhook_tenant_api_key",
                "ordering": ["tenant_id", "name"],
            },
        ),
        migrations.CreateModel(
            name="WebhookEvent",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("event_type", models.CharField(max_length=255)),
                ("payload", models.JSONField(default=dict)),
                ("idempotency_key", models.CharField(blank=True, max_length=255, null=True)),
                ("processed", models.BooleanField(default=False)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="webhook_data.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "webhook_event",
                "ordering": ["-received_at"],
            },
        ),
        migrations.CreateModel(
            name="DeliveryAttempt",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("in_progress", "In progress"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                            ("retrying", "Retrying"),
                            ("dead_letter", "Dead letter"),
                        ],
                        default="pending",
                        max_length=32,
                    ),
                ),
                ("attempt_number", models.PositiveIntegerField(default=1)),
                ("status_code", models.PositiveIntegerField(blank=True, null=True)),
                ("response_body", models.TextField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True, null=True)),
                ("next_retry_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="delivery_attempts",
                        to="webhook_data.webhookevent",
                    ),
                ),
                (
                    "subscription",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="delivery_attempts",
                        to="webhook_data.subscription",
                    ),
                ),
            ],
            options={
                "db_table": "webhook_delivery_attempt",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="tenant",
            index=models.Index(fields=["slug"], name="tenant_slug_idx"),
        ),
        migrations.AddIndex(
            model_name="tenant",
            index=models.Index(fields=["is_active"], name="tenant_active_idx"),
        ),
        migrations.AddIndex(
            model_name="subscription",
            index=models.Index(fields=["tenant", "active"], name="subscription_tenant_active_idx"),
        ),
        migrations.AddIndex(
            model_name="subscription",
            index=models.Index(fields=["tenant", "event_type"], name="subscription_tenant_event_idx"),
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.UniqueConstraint(
                fields=("tenant", "event_type", "target_url"),
                name="uniq_subscription_target_event",
            ),
        ),
        migrations.AddIndex(
            model_name="tenantapikey",
            index=models.Index(fields=["tenant", "is_active"], name="api_key_tenant_active_idx"),
        ),
        migrations.AddIndex(
            model_name="tenantapikey",
            index=models.Index(fields=["key_prefix"], name="api_key_prefix_idx"),
        ),
        migrations.AddConstraint(
            model_name="tenantapikey",
            constraint=models.UniqueConstraint(
                fields=("tenant", "key_prefix"),
                name="uniq_api_key_prefix_per_tenant",
            ),
        ),
        migrations.AddIndex(
            model_name="webhookevent",
            index=models.Index(fields=["tenant", "event_type"], name="event_tenant_type_idx"),
        ),
        migrations.AddIndex(
            model_name="webhookevent",
            index=models.Index(fields=["tenant", "processed"], name="event_tenant_processed_idx"),
        ),
        migrations.AddIndex(
            model_name="webhookevent",
            index=models.Index(fields=["received_at"], name="event_received_idx"),
        ),
        migrations.AddConstraint(
            model_name="webhookevent",
            constraint=models.UniqueConstraint(
                condition=Q(("idempotency_key__isnull", False)),
                fields=("tenant", "idempotency_key"),
                name="uniq_event_idempotency_per_tenant",
            ),
        ),
        migrations.AddIndex(
            model_name="deliveryattempt",
            index=models.Index(fields=["event", "subscription"], name="delivery_event_sub_idx"),
        ),
        migrations.AddIndex(
            model_name="deliveryattempt",
            index=models.Index(fields=["status", "next_retry_at"], name="delivery_status_retry_idx"),
        ),
        migrations.AddIndex(
            model_name="deliveryattempt",
            index=models.Index(fields=["subscription", "status"], name="delivery_sub_status_idx"),
        ),
        migrations.AddConstraint(
            model_name="deliveryattempt",
            constraint=models.UniqueConstraint(
                fields=("event", "subscription"),
                name="uniq_delivery_event_subscription",
            ),
        ),
        migrations.AddConstraint(
            model_name="deliveryattempt",
            constraint=positive_check_constraint(
                query=Q(("attempt_number__gte", 1)),
                name="delivery_attempt_number_positive",
            ),
        ),
    ]
