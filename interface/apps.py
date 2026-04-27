from importlib.util import find_spec

from django.apps import AppConfig


class InterfaceConfig(AppConfig):
    """Configuration for the Interface layer."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'interface'
    verbose_name = 'Webhook Interface Layer'

    def ready(self) -> None:
        """Register optional schema/auth integrations after app loading."""
        if find_spec("drf_spectacular") is not None:
            import interface.schema  # noqa: F401
