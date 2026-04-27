# Webhook Delivery Service

Centralized webhook subscription, ingestion, fan-out, and delivery service for
tenant-scoped SaaS events such as `po.created`, `invoice.paid`, and
`project.milestone_completed`.

## What It Does

- receives tenant-authenticated business events
- stores events durably before queue publication
- matches subscriptions by wildcard event type
- fans out one delivery attempt per matched subscription
- signs outbound webhook requests with HMAC-SHA256
- retries failed deliveries with exponential backoff and jitter
- opens a per-tenant circuit breaker for repeatedly failing target URLs
- exposes health and tenant metrics endpoints

## Architecture

The service follows Clean Architecture:

- `interface/`: Django, DRF, authentication, URL routing, Celery entry points
- `domain/`: pure Python entities, interfaces, business rules, use cases
- `data/`: Django ORM models, repository implementations, HTTP gateway

See [DESIGN.md](./DESIGN.md) for the detailed reliability and crash-recovery
story.

## Prerequisites

- Python 3.9+
- PostgreSQL 12+ and Redis 6+ for the full local stack
- or SQLite for lightweight local development
- Docker Desktop / Docker Compose if you want the containerized stack

## Setup

### Option 1: helper script

On Windows PowerShell:

```powershell
.\bin\setup.ps1 -Action Help
.\bin\setup.ps1 -Action Bootstrap -UseSqlite
```

### Option 2: manual setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py check
```

For local SQLite development, set this in `.env`:

```env
USE_SQLITE=True
```

For PostgreSQL, use the `POSTGRES_*` variables from
[.env.example](./.env.example).

## Running the Service

### Local processes

Terminal 1:

```bash
python manage.py runserver
```

Terminal 2:

```bash
celery -A config worker -l info
```

Terminal 3:

```bash
celery -A config beat -l info
```

### Docker Compose

```bash
docker compose up -d
```

Local URLs:

- API root: <http://localhost:8000/api/>
- health: <http://localhost:8000/api/health/>
- swagger: <http://localhost:8000/api/docs/>
- redoc: <http://localhost:8000/api/redoc/>
- schema: <http://localhost:8000/api/schema/>
- admin: <http://localhost:8000/admin/>

## Tenant Bootstrap

There is no public tenant-creation API. Bootstrap happens through Django admin
or the management command flow.

1. ensure the local Django admin user exists:

```bash
python manage.py ensure_admin_user
```

The local setup script and Docker web startup already run this automatically.
The default dev credentials come from `.env`:

- `DJANGO_SUPERUSER_USERNAME=admin`
- `DJANGO_SUPERUSER_PASSWORD=admin`
- `DJANGO_SUPERUSER_EMAIL=admin@example.com`

2. create a `Tenant` in `/admin/`
3. create a tenant API key either in `/admin/` or with:

```bash
python manage.py create_api_key --tenant-id <tenant-uuid> --name "primary"
```

The raw API key is shown once. Store it securely.

## Runtime API

### Authentication

Runtime API endpoints accept either:

- `X-API-Key: <raw-key>`
- `Authorization: Api-Key <raw-key>`

Examples below use `X-API-Key`.

### Endpoints

- `GET /api/health/`
- `GET /api/metrics/`
- `GET /api/deliveries/`
- `POST /api/deliveries/{id}/retry/`
- `POST /api/events/`
- `GET /api/subscriptions/`
- `POST /api/subscriptions/`
- `GET /api/subscriptions/{id}/`
- `PATCH /api/subscriptions/{id}/`
- `DELETE /api/subscriptions/{id}/`

See [docs/API_DOCUMENTATION.md](./docs/API_DOCUMENTATION.md) for the full
request and response contract.

## Producer Integration Guide

### 1. Create a subscription

```bash
curl -X POST http://localhost:8000/api/subscriptions/ \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "po.*",
    "target_url": "https://example.com/webhooks",
    "active": true
  }'
```

Successful create response:

```json
{
  "data": {
    "id": "8b55be17-83d0-4a3a-8a96-6f1d796dca3f",
    "tenant_id": "37a1f651-b2d7-4c6c-beac-cc1de86c227f",
    "event_type": "po.*",
    "target_url": "https://example.com/webhooks",
    "active": true,
    "created_at": "2026-04-26T13:30:00+00:00",
    "updated_at": "2026-04-26T13:30:00+00:00",
    "secret": "whsec_..."
  }
}
```

The subscription secret is returned once and then only stored encrypted/hashed.

### 2. Ingest an event

```bash
curl -X POST http://localhost:8000/api/events/ \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "po.created",
    "payload": {
      "po_number": "PO-1001",
      "amount": 4200
    },
    "idempotency_key": "po-1001-created"
  }'
```

New event response:

```json
{
  "data": {
    "id": "1f33f4de-9f0f-41bc-92a2-0a055665d8f3",
    "tenant_id": "37a1f651-b2d7-4c6c-beac-cc1de86c227f",
    "event_type": "po.created",
    "payload": {
      "po_number": "PO-1001",
      "amount": 4200
    },
    "idempotency_key": "po-1001-created",
    "timestamp": "2026-04-26T13:31:00+00:00",
    "processed": false
  },
  "meta": {
    "idempotent_replay": false
  }
}
```

If the same idempotency key is replayed for the same tenant, the service
returns the existing event with `idempotent_replay: true` instead of creating a
duplicate.

### 3. Inspect delivery attempts

```bash
curl -G http://localhost:8000/api/deliveries/ \
  -H "X-API-Key: YOUR_API_KEY" \
  --data-urlencode "status=retrying" \
  --data-urlencode "page=1" \
  --data-urlencode "page_size=20"
```

The delivery listing is tenant-scoped and supports filtering by:

- `status`
- `event_id`
- `subscription_id`

### 4. Manually requeue a failed delivery

```bash
curl -X POST http://localhost:8000/api/deliveries/DELIVERY_ATTEMPT_ID/retry/ \
  -H "X-API-Key: YOUR_API_KEY"
```

Manual retry is allowed for delivery attempts in `failed` or `dead_letter`
state and requeues the existing attempt for immediate processing.

## Webhook Delivery Contract

Outbound requests are `POST` requests with JSON bodies and these headers:

- `Content-Type: application/json`
- `X-Event-Id: <event-id>`
- `X-Event-Type: <event-type>`
- `X-Timestamp: <unix-timestamp>`
- `X-Signature: sha256=<hex-digest>`
- `X-Signature-Version: v1`

The signature is computed over:

```text
{timestamp}.{raw_body}
```

### Verification example

```python
import hmac
import hashlib


def verify_webhook(secret: str, headers: dict, body: bytes) -> bool:
    timestamp = headers["X-Timestamp"]
    provided = headers["X-Signature"]
    message = timestamp.encode("utf-8") + b"." + body
    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, provided)
```

More receiver-side examples live in
[docs/WEBHOOK_INTEGRATION.md](./docs/WEBHOOK_INTEGRATION.md).

## Retry Behaviour

By default, delivery uses:

- connect timeout: `5s`
- read timeout: `15s`
- max retries: `5`
- base retry delay: `1s`
- max retry delay: `60s`
- jitter factor: `0.1`

This means retries use capped exponential backoff with bounded jitter rather
than retrying every failing target in lock-step.

Circuit breaker defaults:

- failure threshold: `5` consecutive failures
- recovery timeout: `60s`

When a target keeps failing, the breaker opens for that tenant/target pair and
short-circuits new delivery attempts until the cooldown window expires. The
first probe after cooldown runs in half-open mode.

## Testing

### Fast domain tests

```bash
pytest tests/domain -q
```

### Infrastructure tests

```bash
pytest tests/integration -q
```

### End-to-end tests

```bash
pytest tests/e2e -q
```

### Focused checks used during development

```bash
python manage.py check
pytest tests/integration/test_monitoring_api.py -q
pytest tests/e2e/test_webhook_delivery_flow.py -q
```

## Operational Visibility

- admin UI for tenants, API keys, subscriptions, events, attempts, and outbox
- `GET /api/health/` for service health
- `GET /api/metrics/` for tenant-scoped metrics
- `GET /api/deliveries/` for tenant-scoped delivery visibility
- `POST /api/deliveries/{id}/retry/` for manual requeue of failed attempts

## Documentation

- [DESIGN.md](./DESIGN.md)
- [docs/API_DOCUMENTATION.md](./docs/API_DOCUMENTATION.md)
- [docs/QUICKSTART.md](./docs/QUICKSTART.md)
- [docs/WEBHOOK_INTEGRATION.md](./docs/WEBHOOK_INTEGRATION.md)
- [docs/DELIVERY_ATTEMPT_AND_CIRCUIT_BREAKER_TESTING.md](./docs/DELIVERY_ATTEMPT_AND_CIRCUIT_BREAKER_TESTING.md)
- [docs/ASSIGNMENT_CHECKLIST.md](./docs/ASSIGNMENT_CHECKLIST.md)

## Remaining Polish

The assignment checklist is now covered end to end in
[docs/ASSIGNMENT_CHECKLIST.md](./docs/ASSIGNMENT_CHECKLIST.md).

The remaining work is polish rather than a missing feature:

- richer metrics such as delivery lag and oldest pending event age
- a more explicit OpenAPI security scheme for the custom API key auth
