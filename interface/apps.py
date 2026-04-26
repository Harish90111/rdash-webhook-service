from django.apps import AppConfig


class InterfaceConfig(AppConfig):
    """Configuration for the Interface layer."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'interface'
    verbose_name = 'Webhook Interface Layer'