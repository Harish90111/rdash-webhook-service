"""Add per-tenant target circuit breaker state."""

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
    dependencies = [
        ("webhook_data", "0003_subscription_secret_encrypted"),
    ]

    operations = [
        migrations.CreateModel(
            name="CircuitBreakerState",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "target_url",
                    models.URLField(max_length=2048),
                ),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("closed", "Closed"),
                            ("open", "Open"),
                            ("half_open", "Half open"),
                        ],
                        default="closed",
                        max_length=16,
                    ),
                ),
                ("consecutive_failures", models.PositiveIntegerField(default=0)),
                ("opened_at", models.DateTimeField(blank=True, null=True)),
                ("last_failure_at", models.DateTimeField(blank=True, null=True)),
                ("last_success_at", models.DateTimeField(blank=True, null=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="circuit_breakers",
                        to="webhook_data.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "webhook_circuit_breaker",
                "ordering": ["tenant_id", "target_url"],
            },
        ),
        migrations.AddIndex(
            model_name="circuitbreakerstate",
            index=models.Index(fields=["tenant", "state"], name="circuit_tenant_state_idx"),
        ),
        migrations.AddIndex(
            model_name="circuitbreakerstate",
            index=models.Index(fields=["state", "opened_at"], name="circuit_state_opened_idx"),
        ),
        migrations.AddConstraint(
            model_name="circuitbreakerstate",
            constraint=models.UniqueConstraint(
                fields=("tenant", "target_url"),
                name="uniq_circuit_tenant_target",
            ),
        ),
        migrations.AddConstraint(
            model_name="circuitbreakerstate",
            constraint=positive_check_constraint(
                query=Q(("consecutive_failures__gte", 0)),
                name="circuit_failures_non_negative",
            ),
        ),
    ]
