# Delivery Attempt And Circuit Breaker Testing

This guide shows how to create repeatable test data for:

- actual `webhook_delivery_attempt` generation through the runtime APIs
- actual `webhook_circuit_breaker` transitions through repeated failed deliveries
- forced database preconditions when you need to jump straight to a retry or open-breaker scenario

The goal is to be explicit about what should be created by the application and
what is acceptable to seed directly in the database.

## 1. What must come from DB vs APIs

| Record / concern | Create directly in DB? | Create via app/API? | Notes |
| --- | --- | --- | --- |
| `webhook_tenant` | Yes | No public API exists | Use SQL or Django admin. |
| `webhook_tenant_api_key` | No | Yes | Use Django admin or `python manage.py create_api_key`. Raw key hashing must be done by the app. |
| `webhook_subscription` | Prefer API | Yes | The app generates and stores the signing secret correctly. |
| `webhook_event` | No | Yes | Use `POST /api/events/` so idempotency and outbox are exercised. |
| `webhook_outbox_message` | No for normal tests | Auto-created | It should be created automatically with event ingestion. |
| `webhook_delivery_attempt` | No for normal tests | Auto-created | It should be created by fan-out after event ingestion. Direct DB writes are only for forced retry/dead-letter scenarios. |
| `webhook_circuit_breaker` | Optional | Auto-created | Repeated real delivery failures will create it. Direct DB writes are useful when you need a pre-opened breaker immediately. |

## 2. Recommended test target URLs

Choose the target URL based on where the delivery worker is running.

### If worker runs in Docker Compose

- success target: `http://web:8000/api/health/`
- failure target: `http://web:8000/does-not-exist`

### If worker runs directly on your machine

- success target: `http://localhost:8000/api/health/`
- failure target: `http://localhost:8000/does-not-exist`

The failure URL is useful because the worker can reach it reliably, and Django
will return `404`, which still counts as a delivery failure and advances the
circuit breaker.

## 3. Base prerequisites

1. Start the stack.
2. Make sure migrations are applied.
3. Make sure an admin user exists.
4. Create one tenant.
5. Create one tenant API key and keep the raw value.

Example commands:

```bash
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py ensure_admin_user
docker compose exec web python manage.py create_api_key --tenant-id 11111111-1111-1111-1111-111111111111 --name "delivery-test-key"
```

## 4. Insert the tenant directly in DB

There is no public tenant creation API, so this is the one record that is
perfectly reasonable to seed directly.

Use DBeaver, `psql`, or another SQL client against PostgreSQL:

```sql
INSERT INTO webhook_tenant (
    id,
    name,
    slug,
    is_active,
    created_at,
    updated_at
) VALUES (
    '11111111-1111-1111-1111-111111111111',
    'Delivery Attempt Test Tenant',
    'delivery-attempt-test',
    TRUE,
    NOW(),
    NOW()
)
ON CONFLICT (id) DO UPDATE
SET
    name = EXCLUDED.name,
    slug = EXCLUDED.slug,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();
```

## 5. Create the tenant API key through the app

Do not insert `webhook_tenant_api_key` directly, because the app must generate
the raw key and hash correctly.

```bash
docker compose exec web python manage.py create_api_key \
  --tenant-id 11111111-1111-1111-1111-111111111111 \
  --name "delivery-test-key"
```

Capture the printed raw API key and use it in `X-API-Key`.

## 6. Create subscriptions through the API

### 6.1 Success-path subscription payload

Use this when you want successful delivery attempts.

```json
{
  "event_type": "invoice.paid",
  "target_url": "http://web:8000/api/health/",
  "active": true
}
```

Example:

```bash
curl -X POST http://localhost:8000/api/subscriptions/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_RAW_API_KEY" \
  -d '{
    "event_type": "invoice.paid",
    "target_url": "http://web:8000/api/health/",
    "active": true
  }'
```

### 6.2 Failure-path subscription payload

Use this when you want failed delivery attempts and circuit breaker progression.

```json
{
  "event_type": "invoice.paid",
  "target_url": "http://web:8000/does-not-exist",
  "active": true
}
```

Example:

```bash
curl -X POST http://localhost:8000/api/subscriptions/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_RAW_API_KEY" \
  -d '{
    "event_type": "invoice.paid",
    "target_url": "http://web:8000/does-not-exist",
    "active": true
  }'
```

Keep the returned `subscription.id`. The response also shows the signing secret
once; that is expected and correct.

## 7. Create delivery attempts through the event ingestion API

For actual delivery-attempt testing, do not insert into
`webhook_delivery_attempt` first. Let the platform create it from an event.

### 7.1 Single-event payload

```json
{
  "event_type": "invoice.paid",
  "idempotency_key": "invoice-paid-test-001",
  "payload": {
    "invoice_id": "INV-001",
    "project_id": "PRJ-001",
    "amount": 12500.5,
    "currency": "INR",
    "paid_at": "2026-04-27T07:15:00Z",
    "sequence": 1
  }
}
```

Example:

```bash
curl -X POST http://localhost:8000/api/events/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_RAW_API_KEY" \
  -d '{
    "event_type": "invoice.paid",
    "idempotency_key": "invoice-paid-test-001",
    "payload": {
      "invoice_id": "INV-001",
      "project_id": "PRJ-001",
      "amount": 12500.5,
      "currency": "INR",
      "paid_at": "2026-04-27T07:15:00Z",
      "sequence": 1
    }
  }'
```

This should produce:

1. one `webhook_event`
2. one `webhook_outbox_message`
3. one `webhook_delivery_attempt` after fan-out

## 8. Verify the records in DB

### 8.1 Subscriptions

```sql
SELECT id, tenant_id, event_type, target_url, active, created_at
FROM webhook_subscription
WHERE tenant_id = '11111111-1111-1111-1111-111111111111'
ORDER BY created_at DESC;
```

### 8.2 Events

```sql
SELECT id, tenant_id, event_type, idempotency_key, processed, processed_at, received_at
FROM webhook_event
WHERE tenant_id = '11111111-1111-1111-1111-111111111111'
ORDER BY received_at DESC;
```

### 8.3 Delivery attempts

```sql
SELECT
    id,
    event_id,
    subscription_id,
    status,
    attempt_number,
    status_code,
    error_message,
    next_retry_at,
    completed_at,
    created_at,
    updated_at
FROM webhook_delivery_attempt
WHERE event_id = 'PUT_EVENT_ID_HERE'
ORDER BY created_at DESC;
```

### 8.4 Circuit breaker state

```sql
SELECT
    id,
    tenant_id,
    target_url,
    state,
    consecutive_failures,
    opened_at,
    last_failure_at,
    last_success_at,
    created_at,
    updated_at
FROM webhook_circuit_breaker
WHERE tenant_id = '11111111-1111-1111-1111-111111111111'
ORDER BY updated_at DESC;
```

## 9. Actual circuit breaker test through APIs

The default breaker threshold is `5`. To open it through the real workflow:

1. create one failure-path subscription
2. ingest six unique events for the same `target_url`
3. let workers process them

Use a unique `idempotency_key` every time. Example sequence values:

- `invoice-paid-cb-001`
- `invoice-paid-cb-002`
- `invoice-paid-cb-003`
- `invoice-paid-cb-004`
- `invoice-paid-cb-005`
- `invoice-paid-cb-006`

Example payload template:

```json
{
  "event_type": "invoice.paid",
  "idempotency_key": "invoice-paid-cb-001",
  "payload": {
    "invoice_id": "INV-CB-001",
    "project_id": "PRJ-CB-001",
    "amount": 999.99,
    "currency": "INR",
    "paid_at": "2026-04-27T07:30:00Z",
    "sequence": 1
  }
}
```

Expected behavior:

1. attempts 1 to 5 perform real outbound HTTP calls and fail with `404`
2. the circuit breaker row moves from `closed` to `open`
3. the sixth event should still create a delivery attempt, but the worker should
   short-circuit it using the open breaker instead of doing another HTTP call

Inspect:

```sql
SELECT target_url, state, consecutive_failures, opened_at, last_failure_at
FROM webhook_circuit_breaker
WHERE tenant_id = '11111111-1111-1111-1111-111111111111'
  AND target_url = 'http://web:8000/does-not-exist';
```

## 10. Force a delivery attempt directly in DB

Direct DB insertion is useful when testing `POST /api/deliveries/{id}/retry/`
without replaying the full event flow.

Only do this after `webhook_event` and `webhook_subscription` already exist.

### 10.1 Insert a failed delivery attempt

```sql
INSERT INTO webhook_delivery_attempt (
    id,
    event_id,
    subscription_id,
    status,
    attempt_number,
    status_code,
    response_body,
    error_message,
    next_retry_at,
    completed_at,
    created_at,
    updated_at
) VALUES (
    '22222222-2222-2222-2222-222222222222',
    'PUT_EVENT_ID_HERE',
    'PUT_SUBSCRIPTION_ID_HERE',
    'failed',
    1,
    503,
    'forced failure for retry testing',
    'Forced DB seed for /api/deliveries/{id}/retry/ testing.',
    NULL,
    NOW(),
    NOW(),
    NOW()
)
ON CONFLICT (id) DO NOTHING;
```

### 10.2 Retry it through the API

This endpoint has no request body.

```bash
curl -X POST http://localhost:8000/api/deliveries/22222222-2222-2222-2222-222222222222/retry/ \
  -H "X-API-Key: YOUR_RAW_API_KEY"
```

Expected outcome:

- row stays the same `id`
- status moves to `retrying`
- `next_retry_at` is set
- worker processes it again

## 11. Force the circuit breaker directly in DB

If you want a pre-opened breaker without sending five failed events, insert or
update it directly.

```sql
INSERT INTO webhook_circuit_breaker (
    id,
    tenant_id,
    target_url,
    state,
    consecutive_failures,
    opened_at,
    last_failure_at,
    last_success_at,
    created_at,
    updated_at
) VALUES (
    '33333333-3333-3333-3333-333333333333',
    '11111111-1111-1111-1111-111111111111',
    'http://web:8000/does-not-exist',
    'open',
    5,
    NOW(),
    NOW(),
    NULL,
    NOW(),
    NOW()
)
ON CONFLICT ON CONSTRAINT uniq_circuit_tenant_target
DO UPDATE SET
    state = EXCLUDED.state,
    consecutive_failures = EXCLUDED.consecutive_failures,
    opened_at = EXCLUDED.opened_at,
    last_failure_at = EXCLUDED.last_failure_at,
    updated_at = NOW();
```

Then ingest one more event through `POST /api/events/`. The delivery attempt
should be created, but the worker should respect the open breaker and avoid a
real outbound call until recovery time passes.

## 12. Short execution checklist

1. Insert `webhook_tenant` directly.
2. Create tenant API key through `create_api_key`.
3. Create subscription through `POST /api/subscriptions/`.
4. Ingest event(s) through `POST /api/events/`.
5. Inspect `webhook_event`, `webhook_outbox_message`, and
   `webhook_delivery_attempt`.
6. For organic breaker testing, send repeated failing events.
7. For forced preconditions, insert or update `webhook_delivery_attempt` and
   `webhook_circuit_breaker` directly.
8. Use `GET /api/deliveries/` and `POST /api/deliveries/{id}/retry/` to verify
   the runtime behavior.
