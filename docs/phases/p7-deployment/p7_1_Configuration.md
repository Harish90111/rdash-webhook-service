# Phase 7.1 - Configuration

Branch: `feature/p7-deployment-p7_1_Configuration`

## Objective

Strengthen the deployment surface of the service so runtime behavior is explicitly environment-driven, Celery worker capacity is configurable without code edits, and PostgreSQL connection pooling controls are first-class settings instead of hardcoded defaults.

## Changes

- Added typed environment helpers in `config/env.py` for booleans, numbers, lists, constrained choices, and deployment validation.
- Introduced `APP_ENV` with explicit `development`, `test`, and `production` modes.
- Added production safety validation for `DJANGO_SECRET_KEY` and `ALLOWED_HOSTS`.
- Moved database construction into a helper that supports:
  - SQLite local timeout configuration
  - PostgreSQL connection max age
  - PostgreSQL connection health checks
  - PostgreSQL connect timeout
  - optional PostgreSQL SSL mode
- Expanded Celery settings so concurrency and broker tuning are environment-driven:
  - worker concurrency
  - prefetch multiplier
  - max tasks per child
  - max memory per child
  - broker connection retry on startup
  - broker pool limit
  - broker heartbeat
  - visibility timeout
  - beat loop interval
- Updated `.env.example` to document the full runtime configuration surface.
- Refactored `docker-compose.yml` to use a shared application environment block, reducing drift between the web, worker, and beat containers.
- Added focused tests for the configuration helpers and production validation rules.

## Architecture Notes

- `config/env.py` keeps environment parsing and validation out of the body of `settings.py`, which makes startup behavior easier to reason about and easier to test.
- Celery concurrency now lives in configuration rather than worker command flags, so the same codebase can scale differently across local development, staging, and production.
- PostgreSQL connection pooling remains Django-native through `CONN_MAX_AGE` and `CONN_HEALTH_CHECKS`, which matches the current architecture without introducing an external pooler dependency.
- Docker Compose now shares one canonical application environment map across process types, reducing the risk that the web app and workers run with subtly different queue or database settings.

## Verification

- `.venv\Scripts\python -m pytest tests\integration\test_configuration_helpers.py -q`
- `.venv\Scripts\python manage.py check` with `USE_SQLITE=True`
- `python -m compileall config tests`

## Deferred

- Health endpoints, delivery metrics, and deeper structured logging remain part of Phase 7.2.
- Container entrypoint hardening and production web-server process management remain future deployment concerns outside this subphase.
