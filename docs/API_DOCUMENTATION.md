# API Documentation

This document describes the runtime API that is currently implemented by the
service.

## Authentication

Authenticated endpoints accept either:

- `X-API-Key: <raw-key>`
- `Authorization: Api-Key <raw-key>`

Examples below use `X-API-Key`.

## Response Envelope

Successful responses use:

```json
{
  "data": {},
  "meta": {}
}
```

Errors are returned through the DRF exception layer with a stable error shape.

## Public Endpoints

### `GET /api/health/`

Unauthenticated service health check.

Example response:

```json
{
  "data": {
    "service": "rdash-webhook-service",
    "version": "v1",
    "environment": "development",
    "status": "ok",
    "timestamp": "2026-04-26T13:44:44.608029+00:00",
    "checks": {
      "database": {
        "status": "ok",
        "vendor": "postgresql",
        "latency_ms": 1.3
      },
      "broker": {
        "status": "ok",
        "mode": "configuration",
        "transport": "redis"
      }
    }
  }
}
```

### `GET /api/schema/`

OpenAPI schema, available when `drf-spectacular` is installed.

### `GET /api/docs/`

Swagger UI, available when `drf-spectacular` is installed.

### `GET /api/redoc/`

ReDoc UI, available when `drf-spectacular` is installed.

## Authenticated Endpoints

## Subscriptions

### `GET /api/subscriptions/`

List the authenticated tenant's subscriptions.

Example:

```bash
curl -H "X-API-Key: YOUR_API_KEY" \
  http://localhost:8000/api/subscriptions/
```

### `POST /api/subscriptions/`

Create a subscription for the authenticated tenant.

Request body:

```json
{
  "event_type": "po.*",
  "target_url": "https://example.com/webhooks",
  "active": true
}
```

Notes:

- `event_type` supports wildcard matching such as `po.*`
- `tenant_id` is forbidden in the payload and comes only from authentication
- `secret` is auto-generated and returned once on create

Success response:

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

### `GET /api/subscriptions/{id}/`

Retrieve one subscription for the authenticated tenant.

### `PATCH /api/subscriptions/{id}/`

Partially update one subscription.

Allowed fields:

- `event_type`
- `target_url`
- `active`

### `DELETE /api/subscriptions/{id}/`

Delete one subscription for the authenticated tenant.

## Events

### `POST /api/events/`

Ingest a business event for the authenticated tenant.

Request body:

```json
{
  "event_type": "po.created",
  "payload": {
    "po_number": "PO-1001",
    "amount": 4200
  },
  "idempotency_key": "po-1001-created"
}
```

Behaviour:

1. tenant identity is derived from the API key principal
2. the event is checked for existing tenant-scoped idempotency key reuse
3. a new event and outbox row are persisted in one transaction
4. Celery beat later dispatches the outbox row to the fan-out task

First submission response:

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

Replay response:

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
    "idempotent_replay": true
  }
}
```

## Metrics

### `GET /api/metrics/`

Return tenant-scoped operational metrics for the authenticated tenant.

Example:

```bash
curl -H "X-API-Key: YOUR_API_KEY" \
  http://localhost:8000/api/metrics/
```

Example response:

```json
{
  "data": {
    "tenant_id": "37a1f651-b2d7-4c6c-beac-cc1de86c227f",
    "captured_at": "2026-04-26T13:50:00+00:00",
    "subscriptions": {
      "total": 2,
      "active": 2
    },
    "events": {
      "received": 5,
      "processed": 5,
      "pending": 0,
      "oldest_pending_age_seconds": 0.0
    },
    "deliveries": {
      "total": 5,
      "completed": 5,
      "success_rate": 100.0,
      "failure_rate": 0.0,
      "lag_seconds": 0.0,
      "by_status": {
        "success": 5,
        "dead_letter": 0,
        "retrying": 0
      }
    },
    "outbox": {
      "total": 5,
      "backlog": 0,
      "oldest_backlog_age_seconds": 0.0,
      "by_status": {
        "published": 5
      }
    }
  }
}
```

Additional metric notes:

- `events.oldest_pending_age_seconds` is the age of the oldest unprocessed event
- `deliveries.lag_seconds` is the age of the oldest non-terminal delivery attempt
- `outbox.oldest_backlog_age_seconds` is the age of the oldest unpublished outbox item

## Deliveries

### `GET /api/deliveries/`

List delivery attempts for the authenticated tenant.

Supported query parameters:

- `status`
- `event_id`
- `subscription_id`
- `page`
- `page_size`

Example:

```bash
curl -G http://localhost:8000/api/deliveries/ \
  -H "X-API-Key: YOUR_API_KEY" \
  --data-urlencode "status=retrying" \
  --data-urlencode "page=1" \
  --data-urlencode "page_size=20"
```

Example response:

```json
{
  "data": [
    {
      "id": "0df6a2dc-7966-4d26-8dc4-e20b8c8015ea",
      "event_id": "1f33f4de-9f0f-41bc-92a2-0a055665d8f3",
      "subscription_id": "8b55be17-83d0-4a3a-8a96-6f1d796dca3f",
      "status": "retrying",
      "attempt_number": 2,
      "status_code": 503,
      "response_body": "upstream unavailable",
      "error_message": "Webhook endpoint returned HTTP 503.",
      "next_retry_at": "2026-04-26T13:32:01+00:00",
      "created_at": "2026-04-26T13:31:02+00:00",
      "completed_at": null
    }
  ],
  "meta": {
    "pagination": {
      "count": 1,
      "page": 1,
      "page_size": 20,
      "total_pages": 1,
      "next": null,
      "previous": null
    }
  }
}
```

### `POST /api/deliveries/{id}/retry/`

Queue an immediate manual retry for a tenant-scoped delivery attempt.

Rules:

- tenant identity comes from the authenticated API key
- only `failed` and `dead_letter` attempts are retryable
- the endpoint requeues the existing attempt instead of creating a new one

Example:

```bash
curl -X POST http://localhost:8000/api/deliveries/0df6a2dc-7966-4d26-8dc4-e20b8c8015ea/retry/ \
  -H "X-API-Key: YOUR_API_KEY"
```

Example response:

```json
{
  "data": {
    "id": "0df6a2dc-7966-4d26-8dc4-e20b8c8015ea",
    "event_id": "1f33f4de-9f0f-41bc-92a2-0a055665d8f3",
    "subscription_id": "8b55be17-83d0-4a3a-8a96-6f1d796dca3f",
    "status": "retrying",
    "attempt_number": 5,
    "status_code": 503,
    "response_body": "upstream unavailable",
    "error_message": "Webhook endpoint returned HTTP 503.",
    "next_retry_at": "2026-04-26T13:32:01+00:00",
    "created_at": "2026-04-26T13:31:02+00:00",
    "completed_at": null
  },
  "meta": {
    "queued": true
  }
}
```

## Webhook Delivery Contract

When a subscription matches an ingested event, the outbound webhook request is:

- method: `POST`
- content type: `application/json`
- signed with HMAC-SHA256 over `{timestamp}.{raw_body}`

Headers:

- `X-Event-Id`
- `X-Event-Type`
- `X-Timestamp`
- `X-Signature`
- `X-Signature-Version`

Example:

```http
POST /webhooks HTTP/1.1
Content-Type: application/json
X-Event-Id: 1f33f4de-9f0f-41bc-92a2-0a055665d8f3
X-Event-Type: po.created
X-Timestamp: 1714133444
X-Signature: sha256=ebbb85d53a240b6568e6e3f9c851993b0a6f279362be8908dda3f9568189ebac
X-Signature-Version: v1
```

Example body:

```json
{
  "id": "1f33f4de-9f0f-41bc-92a2-0a055665d8f3",
  "tenant_id": "37a1f651-b2d7-4c6c-beac-cc1de86c227f",
  "event_type": "po.created",
  "payload": {
    "po_number": "PO-1001",
    "amount": 4200
  },
  "timestamp": "2026-04-26T13:31:00+00:00"
}
```

Verification example:

```python
import hashlib
import hmac


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

## Delivery and Retry Notes

The service records delivery attempts, exposes tenant-scoped listing through
`GET /api/deliveries/`, and supports immediate manual retry through
`POST /api/deliveries/{id}/retry/`.

To protect subscribers and workers from repeated failing targets, outbound
delivery also uses a per-tenant circuit breaker keyed by target URL:

- the breaker opens after `5` consecutive failures by default
- while open, delivery attempts are short-circuited without making an HTTP call
- after `60s` by default, one half-open probe is allowed
- a successful probe closes the breaker and resets the failure count
- a failed probe reopens it

The breaker delay is folded into retry scheduling so attempts do not burn
through the retry budget while the target is still cooling down.

Default delivery settings:

- connect timeout: `5s`
- read timeout: `15s`
- max retries: `5`
- base retry delay: `1s`
- max retry delay: `60s`
- jitter factor: `0.1`
- circuit breaker failure threshold: `5`
- circuit breaker recovery timeout: `60s`
