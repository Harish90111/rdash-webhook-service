"""Add durable outbox messages for reliable broker publishing."""

import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("webhook_data", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="OutboxMessage",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("task_name", models.CharField(max_length=255)),
                ("queue_name", models.CharField(blank=True, max_length=120)),
                ("payload", models.JSONField(default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("in_progress", "In progress"),
                            ("published", "Published"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=32,
                    ),
                ),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("available_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("locked_at", models.DateTimeField(blank=True, null=True)),
                ("locked_by", models.CharField(blank=True, max_length=255)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="outbox_messages",
                        to="webhook_data.webhookevent",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="outbox_messages",
                        to="webhook_data.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "webhook_outbox_message",
                "ordering": ["available_at", "created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="outboxmessage",
            index=models.Index(fields=["status", "available_at"], name="outbox_status_available_idx"),
        ),
        migrations.AddIndex(
            model_name="outboxmessage",
            index=models.Index(fields=["tenant", "status"], name="outbox_tenant_status_idx"),
        ),
        migrations.AddIndex(
            model_name="outboxmessage",
            index=models.Index(fields=["event", "task_name"], name="outbox_event_task_idx"),
        ),
        migrations.AddConstraint(
            model_name="outboxmessage",
            constraint=models.UniqueConstraint(
                fields=("event", "task_name"),
                name="uniq_outbox_event_task",
            ),
        ),
        migrations.AddConstraint(
            model_name="outboxmessage",
            constraint=models.CheckConstraint(
                check=Q(("attempts__gte", 0)),
                name="outbox_attempts_non_negative",
            ),
        ),
    ]
