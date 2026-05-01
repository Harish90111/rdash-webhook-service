#!/bin/sh

set -eu

is_true() {
    normalized="$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')"
    [ "$normalized" = "1" ] || [ "$normalized" = "true" ] || [ "$normalized" = "yes" ] || [ "$normalized" = "on" ]
}

if is_true "${CELERY_BEAT_DEBUGPY_ENABLE:-False}"; then
    if is_true "${CELERY_BEAT_DEBUGPY_WAIT_FOR_CLIENT:-False}"; then
        exec python -m debugpy \
            --listen 0.0.0.0:"${CELERY_BEAT_DEBUGPY_PORT:-5681}" \
            --wait-for-client \
            -m celery -A config beat -l "${CELERY_LOG_LEVEL:-INFO}"
    fi
    exec python -m debugpy \
        --listen 0.0.0.0:"${CELERY_BEAT_DEBUGPY_PORT:-5681}" \
        -m celery -A config beat -l "${CELERY_LOG_LEVEL:-INFO}"
fi

exec celery -A config beat -l "${CELERY_LOG_LEVEL:-INFO}"
