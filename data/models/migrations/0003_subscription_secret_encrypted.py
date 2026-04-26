"""Add encrypted secret storage for webhook subscriptions."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("webhook_data", "0002_outbox_message"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscription",
            name="secret_encrypted",
            field=models.TextField(blank=True, default=""),
        ),
    ]
