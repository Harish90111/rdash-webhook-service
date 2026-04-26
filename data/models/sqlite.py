"""SQLite compatibility helpers for local development and test execution."""

import json
from typing import Any


def register_sqlite_json_functions(connection, **kwargs) -> None:
    """
    Backfill JSON1 helpers that older local SQLite builds may not expose.

    Django's JSONField schema for SQLite relies on ``JSON_VALID`` in table
    constraints. Some Windows Python distributions ship SQLite without that
    function even though normal JSON serialization still works for our test
    cases, so we register a small Python implementation for local runs.
    """
    if connection.vendor != "sqlite" or connection.connection is None:
        return

    def json_valid(value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        if not isinstance(value, str):
            return 0
        try:
            json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return 0
        return 1

    try:
        connection.connection.create_function(
            "JSON_VALID",
            1,
            json_valid,
            deterministic=True,
        )
    except TypeError:
        connection.connection.create_function("JSON_VALID", 1, json_valid)
