"""Shared response helpers for thin DRF views."""

from typing import Any, Mapping, Optional

from rest_framework.response import Response


def success_response(
    data: Any = None,
    *,
    status_code: int = 200,
    meta: Optional[Mapping[str, Any]] = None,
) -> Response:
    """Return a consistent success envelope."""
    payload = {"data": data}
    if meta:
        payload["meta"] = dict(meta)
    return Response(payload, status=status_code)


def error_response(
    *,
    error_code: str,
    message: str,
    status_code: int,
    context: Optional[Mapping[str, Any]] = None,
) -> Response:
    """Return a consistent error envelope."""
    return Response(
        {
            "error": {
                "code": error_code,
                "message": message,
                "context": dict(context or {}),
            }
        },
        status=status_code,
    )
