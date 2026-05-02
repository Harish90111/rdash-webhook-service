#!/bin/sh

set -eu

is_true() {
    normalized="$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')"
    [ "$normalized" = "1" ] || [ "$normalized" = "true" ] || [ "$normalized" = "yes" ] || [ "$normalized" = "on" ]
}

python manage.py migrate

if is_true "${DJANGO_SUPERUSER_BOOTSTRAP:-False}"; then
    python manage.py ensure_admin_user
fi

python manage.py check

if [ "${APP_ENV:-development}" = "production" ]; then
    exec gunicorn config.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers "${GUNICORN_WORKERS:-4}" \
        --timeout "${GUNICORN_TIMEOUT:-60}" \
        --access-logfile - \
        --error-logfile -
fi

if is_true "${DEBUGPY_ENABLE:-False}"; then
    if is_true "${DEBUGPY_WAIT_FOR_CLIENT:-False}"; then
        exec python -m debugpy \
            --listen 0.0.0.0:"${DEBUGPY_PORT:-5678}" \
            --wait-for-client \
            manage.py runserver 0.0.0.0:8000
    fi
    exec python -m debugpy \
        --listen 0.0.0.0:"${DEBUGPY_PORT:-5678}" \
        manage.py runserver 0.0.0.0:8000
fi

exec python manage.py runserver 0.0.0.0:8000
