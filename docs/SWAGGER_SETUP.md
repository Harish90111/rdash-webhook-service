# Swagger / OpenAPI Setup

This project uses `drf-spectacular` to expose an OpenAPI schema and two
interactive documentation views when the package is installed.

## Available Endpoints

- Swagger UI: <http://localhost:8000/api/docs/>
- ReDoc: <http://localhost:8000/api/redoc/>
- OpenAPI schema: <http://localhost:8000/api/schema/>

These routes are enabled only when `drf-spectacular` is importable in the
running environment.

## Installation

Install the project dependencies:

```bash
pip install -r requirements.txt
```

Then start the service:

```bash
python manage.py runserver
```

## Current Wiring

The runtime schema integration is configured in
[`config/settings.py`](../config/settings.py) and
[`config/urls.py`](../config/urls.py):

- `REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"]` is set to
  `drf_spectacular.openapi.AutoSchema` when available
- `/api/schema/`, `/api/docs/`, and `/api/redoc/` are registered only when
  `drf-spectacular` is installed

The docs smoke test lives in
[`tests/integration/test_api_documentation.py`](../tests/integration/test_api_documentation.py).

## Authentication Notes

The runtime API itself accepts either:

- `X-API-Key: <raw-key>`
- `Authorization: Api-Key <raw-key>`

Swagger documents the endpoints, but the project does not currently ship a
custom `drf-spectacular` authentication extension for the tenant API key class.
That means the schema view may not render a polished "Authorize" workflow for
the custom auth scheme in every environment.

For interactive testing today, use one of these paths:

1. open the docs for request and response shapes
2. use `curl`, Postman, or another HTTP client with `X-API-Key`

Example:

```bash
curl -X GET http://localhost:8000/api/subscriptions/ \
  -H "X-API-Key: YOUR_API_KEY"
```

## Troubleshooting

### `/api/docs/` loads but shows a schema error

Check `/api/schema/` directly first. If that endpoint returns `500`, run:

```bash
python manage.py check
pytest tests/integration/test_api_documentation.py -q
```

### Docs routes return `404`

`drf-spectacular` is probably not installed in the active environment.

### Docs are stale after code changes

Restart the Django server and reload `/api/schema/`.

## Related Docs

- [`README.md`](../README.md)
- [`API_DOCUMENTATION.md`](./API_DOCUMENTATION.md)
- [`QUICKSTART.md`](./QUICKSTART.md)
