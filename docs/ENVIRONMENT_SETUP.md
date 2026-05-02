# Environment Setup and Debugging

This project now supports three explicit runtime environments:

- `development`
- `staging`
- `production`

The environment templates live in:

- [config/environments/development.env](../config/environments/development.env)
- [config/environments/staging.env](../config/environments/staging.env)
- [config/environments/production.env](../config/environments/production.env)

The Django settings loader reads:

1. `.env` if present
2. `ENV_FILE` if explicitly provided, overriding `.env`
3. otherwise `config/environments/{APP_ENV}.env` when `.env` is absent

That means you can run the same codebase against different environments without
copying settings into multiple Python files.

## Recommended usage

### Local development

PowerShell:

```powershell
$env:APP_ENV = "development"
$env:ENV_FILE = "config/environments/development.env"
.\.venv\Scripts\python manage.py runserver
```

### Local staging simulation

PowerShell:

```powershell
$env:APP_ENV = "staging"
$env:ENV_FILE = "config/environments/staging.env"
.\.venv\Scripts\python manage.py runserver
```

### Local production simulation

PowerShell:

```powershell
$env:APP_ENV = "production"
$env:ENV_FILE = "config/environments/production.env"
.\.venv\Scripts\python manage.py check
```

For production-like serving in Docker, use the production compose override. The
container runs `gunicorn`, not Django's development server.

## Docker commands

### Development

```powershell
docker compose -f docker-compose.yml -f docker-compose.development.yml up --build
```

Services:

- web: `http://localhost:8000`
- web debugpy: `localhost:5678`
- worker debugpy: `localhost:5680`
- beat debugpy: `localhost:5681`
- postgres: `localhost:5432`
- redis: `localhost:6379`

### Staging

```powershell
docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build
```

Services:

- web: `http://localhost:8001`
- web debugpy: `localhost:5679`
- worker debugpy: `localhost:5690`
- beat debugpy: `localhost:5691`
- postgres: `localhost:5433`
- redis: `localhost:6380`

### Production

```powershell
docker compose -f docker-compose.yml -f docker-compose.production.yml up --build
```

Services:

- web: `http://localhost:8000`

Production does not expose a debugger port and does not mount the working tree
into the container.

## What changes when debug is enabled

When `DEBUG=True`:

- Django returns the debug error page with stack traces
- Django `runserver` is used instead of `gunicorn`
- source code is mounted into the container in dev/staging compose
- `debugpy` can listen for an attached debugger
- settings default to more permissive local hostnames
- logging is usually more verbose

When `DEBUG=False`:

- Django hides internal stack traces from HTTP responses
- the container uses `gunicorn` for the web server
- no debugger listener is started
- production validation is stricter:
  - non-development `DJANGO_SECRET_KEY` required
  - `ALLOWED_HOSTS` required
  - `DEBUG=True` is rejected by system/config validation
- production config is expected to disable bootstrap conveniences like
  auto-created admin users

## Debugger setup

The container web entrypoint supports:

- `DEBUGPY_ENABLE`
- `DEBUGPY_PORT`
- `DEBUGPY_WAIT_FOR_CLIENT`

The container worker entrypoint supports:

- `CELERY_WORKER_DEBUGPY_ENABLE`
- `CELERY_WORKER_DEBUGPY_PORT`
- `CELERY_WORKER_DEBUGPY_WAIT_FOR_CLIENT`
- `CELERY_WORKER_DEBUG_POOL`

The container beat entrypoint supports:

- `CELERY_BEAT_DEBUGPY_ENABLE`
- `CELERY_BEAT_DEBUGPY_PORT`
- `CELERY_BEAT_DEBUGPY_WAIT_FOR_CLIENT`

Examples:

- development template: debugger enabled on `5678`
- development worker debugger enabled on `5680`
- development beat debugger enabled on `5681`
- staging template: web debugger enabled on `5678` inside container, mapped to
  host port `5679`
- staging worker debugger enabled on `5680` inside container, mapped to host
  port `5690`
- staging beat debugger enabled on `5681` inside container, mapped to host
  port `5691`
- production template: debugger disabled

If `DEBUGPY_WAIT_FOR_CLIENT=True`, the web server will pause at startup until a
debugger attaches.

If `CELERY_WORKER_DEBUGPY_WAIT_FOR_CLIENT=True` or
`CELERY_BEAT_DEBUGPY_WAIT_FOR_CLIENT=True`, the worker or beat process will
pause at startup until the debugger attaches. The worker defaults to `solo`
pool in debug mode so breakpoints behave predictably.

## Why production behaves differently

Production is intentionally stricter:

- `gunicorn` is safer than Django's development server
- `DEBUG=False` prevents internal exception leakage
- no bind-mounted source tree means the container runs the baked image
- no debugger port means less accidental exposure

## Helper script

The Windows helper now supports environment selection:

```powershell
.\bin\setup.ps1 -Action Bootstrap -EnvironmentName development
.\bin\setup.ps1 -Action RunServer -EnvironmentName staging
.\bin\setup.ps1 -Action Docker -EnvironmentName production
```
