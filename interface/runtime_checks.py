"""Runtime compatibility checks for the Django interface layer."""

import sys
from typing import Iterable, Tuple

from django import VERSION as DJANGO_VERSION
from django.core.checks import Error, Tags, register


DJANGO_42_SERIES = (4, 2)
MAX_DJANGO_42_PYTHON = (3, 12)


def runtime_compatibility_errors(
    *,
    python_version: Tuple[int, int],
    django_version: Tuple[int, int],
) -> Iterable[Error]:
    """Return system-check errors for unsupported Django/Python combinations."""

    if django_version == DJANGO_42_SERIES and python_version > MAX_DJANGO_42_PYTHON:
        return [
            Error(
                "Unsupported Django/Python runtime combination.",
                hint=(
                    "Django 4.2 supports Python 3.8 through 3.12. "
                    "Use Python 3.12 for this project container or upgrade Django "
                    "to a version that officially supports Python "
                    f"{python_version[0]}.{python_version[1]}."
                ),
                id="webhook.E001",
            )
        ]
    return []


@register(Tags.compatibility)
def check_runtime_compatibility(app_configs, **kwargs):
    """Fail fast when the runtime is outside Django's supported matrix."""

    return list(
        runtime_compatibility_errors(
            python_version=sys.version_info[:2],
            django_version=DJANGO_VERSION[:2],
        )
    )
