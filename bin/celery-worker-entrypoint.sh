#!/bin/sh

set -eu

is_true() {
    normalized="$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')"
    [ "$normalized" = "1" ] || [ "$normalized" = "true" ] || [ "$normalized" = "yes" ] || [ "$normalized" = "on" ]
}

if is_true "${CELERY_WORKER_DEBUGPY_ENABLE:-False}"; then
    worker_pool="${CELERY_WORKER_DEBUG_POOL:-solo}"
    if is_true "${CELERY_WORKER_DEBUGPY_WAIT_FOR_CLIENT:-False}"; then
        exec python -m debugpy \
            --listen 0.0.0.0:"${CELERY_WORKER_DEBUGPY_PORT:-5680}" \
            --wait-for-client \
            -m celery -A config worker -l "${CELERY_LOG_LEVEL:-INFO}" -P "${worker_pool}"
    fi
    exec python -m debugpy \
        --listen 0.0.0.0:"${CELERY_WORKER_DEBUGPY_PORT:-5680}" \
        -m celery -A config worker -l "${CELERY_LOG_LEVEL:-INFO}" -P "${worker_pool}"
fi

exec celery -A config worker -l "${CELERY_LOG_LEVEL:-INFO}" -P "${CELERY_WORKER_POOL:-prefork}"
