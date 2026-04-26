from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.env import (
    DEFAULT_DEV_SECRET_KEY,
    build_celery_task_annotations,
    build_celery_transport_options,
    build_database_settings,
    env_bool,
    env_list,
    validate_runtime_settings,
)


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("off", False),
    ],
)
def test_env_bool_parses_common_values(monkeypatch, raw_value, expected):
    monkeypatch.setenv("TEST_BOOL", raw_value)

    assert env_bool("TEST_BOOL") is expected


def test_env_list_strips_whitespace_and_empty_values(monkeypatch):
    monkeypatch.setenv("TEST_LIST", " alpha, beta ,, gamma ")

    assert env_list("TEST_LIST") == ["alpha", "beta", "gamma"]


def test_build_database_settings_for_postgres_applies_pooling_controls(monkeypatch):
    monkeypatch.setenv("POSTGRES_DB", "rdash_webhooks")
    monkeypatch.setenv("POSTGRES_USER", "postgres")
    monkeypatch.setenv("POSTGRES_PASSWORD", "postgres")
    monkeypatch.setenv("POSTGRES_HOST", "db.internal")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("DB_CONN_MAX_AGE", "120")
    monkeypatch.setenv("DB_CONN_HEALTH_CHECKS", "true")
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "15")
    monkeypatch.setenv("POSTGRES_SSLMODE", "require")

    database_settings = build_database_settings(Path("D:/workspace"), use_sqlite=False)
    default = database_settings["default"]

    assert default["ENGINE"] == "django.db.backends.postgresql"
    assert default["HOST"] == "db.internal"
    assert default["CONN_MAX_AGE"] == 120
    assert default["CONN_HEALTH_CHECKS"] is True
    assert default["OPTIONS"]["connect_timeout"] == 15
    assert default["OPTIONS"]["sslmode"] == "require"


def test_build_database_settings_for_sqlite_uses_timeout(monkeypatch):
    monkeypatch.setenv("SQLITE_NAME", "local.sqlite3")
    monkeypatch.setenv("SQLITE_TIMEOUT_SECONDS", "9")

    database_settings = build_database_settings(Path("D:/workspace"), use_sqlite=True)
    default = database_settings["default"]

    assert default["ENGINE"] == "django.db.backends.sqlite3"
    assert default["NAME"] == Path("D:/workspace") / "local.sqlite3"
    assert default["OPTIONS"]["timeout"] == 9


def test_celery_helpers_use_environment_defaults(monkeypatch):
    monkeypatch.setenv("CELERY_VISIBILITY_TIMEOUT", "7200")
    monkeypatch.setenv("WEBHOOK_DELIVERY_RATE_LIMIT", "60/m")

    assert build_celery_transport_options() == {"visibility_timeout": 7200}
    assert build_celery_task_annotations()["interface.tasks.deliver_webhook"]["rate_limit"] == "60/m"


def test_validate_runtime_settings_rejects_insecure_production_defaults():
    with pytest.raises(ImproperlyConfigured):
        validate_runtime_settings(
            app_env="production",
            secret_key=DEFAULT_DEV_SECRET_KEY,
            allowed_hosts=["api.example.com"],
        )

    with pytest.raises(ImproperlyConfigured):
        validate_runtime_settings(
            app_env="production",
            secret_key="super-secret-production-key",
            allowed_hosts=[],
        )
