# API Documentation

Complete reference for the Webhook Delivery Service API.

## Overview

The API provides endpoints for managing webhook subscriptions, ingesting events, and monitoring delivery attempts. All endpoints require authentication via API key.

## Quick Start

### Authentication

Include your API key in the `Authorization` header:

```bash
curl -H "Authorization: ApiKey YOUR_API_KEY" \
  https://api.example.com/api/subscriptions/
```

### Interactive Documentation

- **Swagger UI**: `/api/docs/` - Interactive API explorer
- **ReDoc**: `/api/redoc/` - Alternative documentation view
- **OpenAPI Schema**: `/api/schema/` - Raw OpenAPI 3.0 JSON schema

## Endpoints

### Subscriptions

Manage webhook subscriptions for specific event types.

#### List Subscriptions

```http
GET /api/subscriptions/
```

**Query Parameters:**
- `event_type` (string, optional) - Filter by event type
- `active` (boolean, optional) - Filter by active status
- `page` (integer, optional) - Page number (default: 1)
- `limit` (integer, optional) - Items per page (default: 20)

**Response:**
```json
{
  "count": 5,
  "next": "http://api.example.com/api/subscriptions/?page=2",
  "previous": null,
  "results": [
    {
      "id": "sub_abc123",
      "event_type": "order.created",
      "target_url": "https://webhook.example.com/orders",
      "active": true,
      "created_at": "2024-04-26T10:30:00Z",
      "updated_at": "2024-04-26T10:30:00Z"
    }
  ]
}
```

**Status Codes:**
- `200 OK` - Success
- `401 Unauthorized` - Missing or invalid API key
- `403 Forbidden` - Insufficient permissions

---

#### Create Subscription

```http
POST /api/subscriptions/
```

**Request Body:**
```json
{
  "event_type": "order.created",
  "target_url": "https://webhook.example.com/webhooks",
  "active": true
}
```

**Request Fields:**
- `event_type` (string, required) - The event type to subscribe to
  - Supports wildcards: `po.*` matches `po.created`, `po.updated`, etc.
- `target_url` (string, required) - The HTTP endpoint to receive webhooks
  - Must be a valid HTTPS URL (HTTP allowed in development)
- `active` (boolean, optional, default: true) - Whether to deliver webhooks

**Response:** `201 Created`
```json
{
  "id": "sub_xyz789",
  "event_type": "order.created",
  "target_url": "https://webhook.example.com/webhooks",
  "active": true,
  "secret": "whsec_abcd1234efgh5678ijkl9101112",
  "created_at": "2024-04-26T10:35:00Z",
  "updated_at": "2024-04-26T10:35:00Z"
}
```

⚠️ **Important**: The `secret` is returned **only once**. Store it securely. It will not be included in subsequent GET or PATCH responses.

**Status Codes:**
- `201 Created` - Subscription created successfully
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Missing or invalid API key
- `409 Conflict` - Subscription already exists for this event type

---

#### Get Subscription Details

```http
GET /api/subscriptions/{id}/
```

**Path Parameters:**
- `id` (string, required) - Subscription ID

**Response:** `200 OK`
```json
{
  "id": "sub_xyz789",
  "event_type": "order.created",
  "target_url": "https://webhook.example.com/webhooks",
  "active": true,
  "created_at": "2024-04-26T10:35:00Z",
  "updated_at": "2024-04-26T10:35:00Z"
}
```

**Status Codes:**
- `200 OK` - Success
- `401 Unauthorized` - Missing or invalid API key
- `404 Not Found` - Subscription not found

---

#### Update Subscription

```http
PATCH /api/subscriptions/{id}/
```

**Path Parameters:**
- `id` (string, required) - Subscription ID

**Request Body:**
```json
{
  "active": false,
  "target_url": "https://new-webhook-endpoint.example.com/webhooks"
}
```

**Updatable Fields:**
- `active` (boolean) - Enable/disable webhook delivery
- `target_url` (string) - Update the webhook endpoint URL

**Response:** `200 OK`
```json
{
  "id": "sub_xyz789",
  "event_type": "order.created",
  "target_url": "https://new-webhook-endpoint.example.com/webhooks",
  "active": false,
  "created_at": "2024-04-26T10:35:00Z",
  "updated_at": "2024-04-26T11:00:00Z"
}
```

**Status Codes:**
- `200 OK` - Updated successfully
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Missing or invalid API key
- `404 Not Found` - Subscription not found

---

#### Delete Subscription

```http
DELETE /api/subscriptions/{id}/
```

**Path Parameters:**
- `id` (string, required) - Subscription ID

**Response:** `204 No Content` (empty body)

**Status Codes:**
- `204 No Content` - Deleted successfully
- `401 Unauthorized` - Missing or invalid API key
- `404 Not Found` - Subscription not found

---

### Events

Ingest events to be delivered to subscribed webhooks.

#### List Events

```http
GET /api/events/
```

**Query Parameters:**
- `event_type` (string, optional) - Filter by event type
- `from_date` (ISO 8601 datetime, optional) - Filter events after this date
- `to_date` (ISO 8601 datetime, optional) - Filter events before this date
- `page` (integer, optional) - Page number (default: 1)
- `limit` (integer, optional) - Items per page (default: 20)

**Response:**
```json
{
  "count": 42,
  "next": "http://api.example.com/api/events/?page=2",
  "previous": null,
  "results": [
    {
      "id": "evt_123",
      "event_type": "order.created",
      "payload": {
        "order_id": "ORD-12345",
        "amount": 99.99,
        "customer_email": "john@example.com"
      },
      "created_at": "2024-04-26T10:45:00Z"
    }
  ]
}
```

**Status Codes:**
- `200 OK` - Success
- `401 Unauthorized` - Missing or invalid API key

---

#### Ingest Event

```http
POST /api/events/
```

**Request Body:**
```json
{
  "event_type": "order.created",
  "payload": {
    "order_id": "ORD-12345",
    "amount": 99.99,
    "customer_email": "john@example.com",
    "items": [
      {
        "sku": "WIDGET-001",
        "quantity": 2,
        "price": 49.99
      }
    ]
  }
}
```

**Request Fields:**
- `event_type` (string, required) - Event type (e.g., `order.created`, `user.updated`)
- `payload` (object, required) - Event data (any valid JSON object)
- `idempotency_key` (string, optional) - Unique key to prevent duplicate processing
  - If provided, duplicate submissions with the same key within 24 hours are ignored

**Response:** `201 Created`
```json
{
  "id": "evt_abc456",
  "event_type": "order.created",
  "payload": {
    "order_id": "ORD-12345",
    "amount": 99.99,
    "customer_email": "john@example.com",
    "items": [...]
  },
  "created_at": "2024-04-26T10:45:00Z"
}
```

**Behavior:**
1. Event is persisted immediately (at-least-once guarantee)
2. Celery task enqueued to fan-out to matching subscriptions
3. Each matching subscription gets a delivery task with retry logic
4. Duplicate events (same idempotency_key) within 24 hours are rejected with `409 Conflict`

**Status Codes:**
- `201 Created` - Event ingested successfully
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Missing or invalid API key
- `409 Conflict` - Duplicate event (same idempotency_key)

---

#### Get Event Details

```http
GET /api/events/{id}/
```

**Path Parameters:**
- `id` (string, required) - Event ID

**Response:** `200 OK`
```json
{
  "id": "evt_abc456",
  "event_type": "order.created",
  "payload": { ... },
  "created_at": "2024-04-26T10:45:00Z"
}
```

**Status Codes:**
- `200 OK` - Success
- `401 Unauthorized` - Missing or invalid API key
- `404 Not Found` - Event not found

---

### Delivery Attempts

Monitor webhook delivery status and retry history.

#### List Delivery Attempts

```http
GET /api/delivery-attempts/
```

**Query Parameters:**
- `event_id` (string, optional) - Filter by event ID
- `subscription_id` (string, optional) - Filter by subscription ID
- `status` (string, optional) - Filter by status: `pending`, `success`, `failed`, `retrying`
- `from_date` (ISO 8601 datetime, optional) - Filter attempts after this date
- `page` (integer, optional) - Page number (default: 1)
- `limit` (integer, optional) - Items per page (default: 20)

**Response:**
```json
{
  "count": 150,
  "next": "http://api.example.com/api/delivery-attempts/?page=2",
  "previous": null,
  "results": [
    {
      "id": "del_123",
      "event_id": "evt_abc456",
      "subscription_id": "sub_xyz789",
      "status": "success",
      "response_code": 200,
      "response_body": null,
      "error_message": null,
      "attempt_number": 1,
      "next_retry_at": null,
      "created_at": "2024-04-26T10:46:00Z",
      "updated_at": "2024-04-26T10:46:00Z"
    },
    {
      "id": "del_124",
      "event_id": "evt_abc456",
      "subscription_id": "sub_def456",
      "status": "retrying",
      "response_code": 500,
      "response_body": null,
      "error_message": "Internal Server Error",
      "attempt_number": 2,
      "next_retry_at": "2024-04-26T11:46:00Z",
      "created_at": "2024-04-26T10:46:00Z",
      "updated_at": "2024-04-26T10:46:00Z"
    }
  ]
}
```

**Status Codes:**
- `200 OK` - Success
- `401 Unauthorized` - Missing or invalid API key

---

#### Get Delivery Attempt Details

```http
GET /api/delivery-attempts/{id}/
```

**Path Parameters:**
- `id` (string, required) - Delivery attempt ID

**Response:** `200 OK`
```json
{
  "id": "del_123",
  "event_id": "evt_abc456",
  "subscription_id": "sub_xyz789",
  "status": "success",
  "response_code": 200,
  "response_body": "{\"status\": \"received\"}",
  "error_message": null,
  "attempt_number": 1,
  "next_retry_at": null,
  "request_headers": {
    "Content-Type": "application/json",
    "X-Signature": "sha256=1234567890abcdef..."
  },
  "created_at": "2024-04-26T10:46:00Z",
  "updated_at": "2024-04-26T10:46:00Z"
}
```

**Status Codes:**
- `200 OK` - Success
- `401 Unauthorized` - Missing or invalid API key
- `404 Not Found` - Delivery attempt not found

---

## Webhooks Received

When a webhook is delivered to your endpoint, it includes:

### Headers

```
POST /webhooks HTTP/1.1
Host: webhook.example.com
Content-Type: application/json
X-Signature: sha256=1234567890abcdef...
X-Webhook-ID: evt_abc456
X-Delivery-ID: del_123
Timestamp: 1719407100
```

**Header Fields:**
- `X-Signature` - HMAC-SHA256 signature for authenticity verification
- `X-Webhook-ID` - Event ID
- `X-Delivery-ID` - Delivery attempt ID
- `Timestamp` - Unix timestamp of webhook dispatch

### Body

```json
{
  "id": "evt_abc456",
  "event_type": "order.created",
  "timestamp": "2024-04-26T10:45:00Z",
  "payload": {
    "order_id": "ORD-12345",
    "amount": 99.99,
    "customer_email": "john@example.com"
  }
}
```

### Verify Webhook Signature

```python
import hmac
import hashlib

def verify_webhook(secret, request_headers, request_body):
    signature_header = request_headers.get('X-Signature', '')
    timestamp = request_headers.get('Timestamp', '')
    
    # Reconstruct the signed message
    message = f"{timestamp}.{request_body}".encode()
    
    # Calculate HMAC
    expected_sig = hmac.new(
        secret.encode(),
        message,
        hashlib.sha256
    ).hexdigest()
    
    # Extract signature from header (format: sha256=<hex>)
    _, received_sig = signature_header.split('=')
    
    # Compare (constant-time)
    return hmac.compare_digest(expected_sig, received_sig)
```

### Webhook Response

Return `2xx` status code to indicate success:

```
HTTP/1.1 200 OK
Content-Type: application/json

{"status": "received", "processing": true}
```

**Important:**
- Respond within 30 seconds (service timeout)
- Return `2xx` to acknowledge receipt
- Return non-`2xx` or timeout to trigger retry
- Retries follow exponential backoff: 1s, 2s, 4s, 8s, 16s, 32s, 60s
- Maximum 7 retries (total ~2 minutes)

---

## Error Responses

All errors follow a consistent format:

```json
{
  "detail": "Error message here",
  "code": "error_code",
  "status_code": 400
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `invalid_request` | 400 | Malformed request data |
| `unauthorized` | 401 | Missing or invalid API key |
| `forbidden` | 403 | Insufficient permissions |
| `not_found` | 404 | Resource not found |
| `conflict` | 409 | Resource already exists or duplicate submission |
| `rate_limit_exceeded` | 429 | Too many requests |
| `internal_error` | 500 | Server error |

---

## Rate Limiting

API endpoints are rate limited per API key:

- **Subscriptions API**: 100 requests/minute
- **Events API**: 1000 requests/minute
- **Delivery Attempts API**: 100 requests/minute

**Headers in response:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1619407200
```

When limit exceeded:
```
HTTP/1.1 429 Too Many Requests

{
  "detail": "Rate limit exceeded. Try again in 60 seconds.",
  "code": "rate_limit_exceeded"
}
```

---

## Pagination

List endpoints support cursor-based pagination:

**Query Parameters:**
- `page` (integer) - Page number (default: 1)
- `limit` (integer) - Items per page (default: 20, max: 100)

**Response:**
```json
{
  "count": 500,
  "next": "http://api.example.com/api/subscriptions/?page=2",
  "previous": null,
  "results": [...]
}
```

---

## Filtering & Searching

Endpoints support filtering via query parameters:

```
GET /api/subscriptions/?event_type=order.created&active=true
GET /api/events/?from_date=2024-04-01&to_date=2024-04-30
GET /api/delivery-attempts/?status=failed&page=1
```

---

## Changelog

### Version 1.0.0 (2024-04-26)
- Initial API release
- Subscriptions management
- Event ingestion
- Webhook delivery with retries
- OpenAPI/Swagger documentation
