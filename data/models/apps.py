from django.apps import AppConfig
from django.db import connections
from django.db.backends.signals import connection_created


class DataModelsConfig(AppConfig):
    """Configuration for the Data layer models."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'data.models'
    label = 'webhook_data'
    verbose_name = 'Webhook Data Models'

    def ready(self) -> None:
        """Register database-specific compatibility hooks after app loading."""
        from data.models.sqlite import register_sqlite_json_functions

        connection_created.connect(
            register_sqlite_json_functions,
            dispatch_uid="webhook_data.sqlite_json_functions",
        )
        for connection in connections.all(initialized_only=True):
            register_sqlite_json_functions(connection=connection)
