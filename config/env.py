"""Typed environment parsing helpers for deployment-oriented settings."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


DEFAULT_DEV_SECRET_KEY = "django-insecure-dev-key-change-in-production"
TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
FALSE_VALUES = {"0", "false", "f", "no", "n", "off"}
VALID_APP_ENVS = ("development", "test", "production")


def env_str(name: str, default: str = "", *, required: bool = False) -> str:
    """Return a stripped string environment value."""
    raw_value = os.getenv(name)
    value = default if raw_value is None else raw_value
    normalized_value = str(value).strip()
    if required and not normalized_value:
        raise ImproperlyConfigured(f"{name} is required.")
    return normalized_value


def env_bool(name: str, default: bool = False) -> bool:
    """Return a boolean environment value."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return bool(default)
    normalized_value = raw_value.strip().lower()
    if normalized_value in TRUE_VALUES:
        return True
    if normalized_value in FALSE_VALUES:
        return False
    raise ImproperlyConfigured(f"{name} must be a boolean value.")


def env_int(name: str, default: int = 0, *, minimum: int = None) -> int:
    """Return an integer environment value."""
    raw_value = os.getenv(name)
    candidate = default if raw_value is None or not raw_value.strip() else raw_value.strip()
    try:
        parsed_value = int(candidate)
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(f"{name} must be an integer value.") from exc
    if minimum is not None and parsed_value < minimum:
        raise ImproperlyConfigured(f"{name} must be at least {minimum}.")
    return parsed_value


def env_float(name: str, default: float = 0.0, *, minimum: float = None) -> float:
    """Return a floating-point environment value."""
    raw_value = os.getenv(name)
    candidate = default if raw_value is None or not raw_value.strip() else raw_value.strip()
    try:
        parsed_value = float(candidate)
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(f"{name} must be a numeric value.") from exc
    if minimum is not None and parsed_value < minimum:
        raise ImproperlyConfigured(f"{name} must be at least {minimum}.")
    return parsed_value


def env_list(name: str, default=None):
    """Return a comma-separated environment value as a normalized list."""
    if default is None:
        default = []
    raw_value = os.getenv(name)
    if raw_value is None:
        if isinstance(default, (list, tuple)):
            return [str(item).strip() for item in default if str(item).strip()]
        raw_value = str(default)
    return [item.strip() for item in str(raw_value).split(",") if item.strip()]


def env_choice(name: str, default: str, *, choices) -> str:
    """Return a constrained string environment value."""
    normalized_default = str(default).strip()
    normalized_choices = {str(choice).strip() for choice in choices}
    value = env_str(name, normalized_default)
    if value not in normalized_choices:
        allowed = ", ".join(sorted(normalized_choices))
        raise ImproperlyConfigured(f"{name} must be one of: {allowed}.")
    return value


def validate_runtime_settings(*, app_env: str, secret_key: str, allowed_hosts) -> None:
    """Fail fast on production settings that would be unsafe to deploy."""
    if app_env != "production":
        return
    if not secret_key or secret_key == DEFAULT_DEV_SECRET_KEY or secret_key.startswith("django-insecure"):
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be explicitly set to a non-development value in production."
        )
    if not allowed_hosts:
        raise ImproperlyConfigured("ALLOWED_HOSTS must be configured in production.")


def build_database_settings(base_dir: Path, *, use_sqlite: bool):
    """Build the Django DATABASES setting from environment variables."""
    if use_sqlite:
        sqlite_name = env_str("SQLITE_NAME", "db.sqlite3")
        return {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": base_dir / sqlite_name,
                "OPTIONS": {
                    "timeout": env_int("SQLITE_TIMEOUT_SECONDS", 5, minimum=1),
                },
            }
        }

    options = {
        "connect_timeout": env_int("DB_CONNECT_TIMEOUT", 10, minimum=1),
    }
    sslmode = env_str("POSTGRES_SSLMODE", "")
    if sslmode:
        options["sslmode"] = sslmode

    return {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env_str("POSTGRES_DB", "rdash_webhooks", required=True),
            "USER": env_str("POSTGRES_USER", "postgres", required=True),
            "PASSWORD": env_str("POSTGRES_PASSWORD", "postgres"),
            "HOST": env_str("POSTGRES_HOST", "localhost", required=True),
            "PORT": env_str("POSTGRES_PORT", "5432", required=True),
            "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60, minimum=0),
            "CONN_HEALTH_CHECKS": env_bool("DB_CONN_HEALTH_CHECKS", True),
            "OPTIONS": options,
        }
    }


def build_celery_transport_options():
    """Return broker transport options tuned for durable task handling."""
    return {
        "visibility_timeout": env_int("CELERY_VISIBILITY_TIMEOUT", 3600, minimum=1),
    }


def build_celery_task_annotations():
    """Return task-specific Celery annotations."""
    return {
        "interface.tasks.deliver_webhook": {
            "rate_limit": env_str("WEBHOOK_DELIVERY_RATE_LIMIT", "120/m"),
        },
    }


def build_celery_beat_schedule():
    """Return the beat schedule for outbox dispatch."""
    return {
        "dispatch-webhook-outbox": {
            "task": "interface.tasks.dispatch_outbox_batch",
            "schedule": env_float(
                "WEBHOOK_OUTBOX_DISPATCH_INTERVAL_SECONDS",
                5.0,
                minimum=0.1,
            ),
        },
    }
