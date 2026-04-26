from django.apps import AppConfig


class DataModelsConfig(AppConfig):
    """Configuration for the Data layer models."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'data.models'
    label = 'webhook_data'
    verbose_name = 'Webhook Data Models'
