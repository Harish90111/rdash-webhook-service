# Webhook Integration Guide

This guide shows customer engineering teams how to receive and verify webhook
requests from the service.

## Request Format

Webhook deliveries are `POST` requests with `application/json` bodies.

### Headers

```http
X-Event-Id: 1f33f4de-9f0f-41bc-92a2-0a055665d8f3
X-Event-Type: po.created
X-Timestamp: 1714133444
X-Signature: sha256=ebbb85d53a240b6568e6e3f9c851993b0a6f279362be8908dda3f9568189ebac
X-Signature-Version: v1
Content-Type: application/json
```

### Body

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

## Signature Contract

The service signs the outbound request body using HMAC-SHA256 over:

```text
{timestamp}.{raw_body}
```

Where:

- `timestamp` is the value of `X-Timestamp`
- `raw_body` is the exact request body bytes

The `X-Signature` header is formatted as:

```text
sha256=<hex-digest>
```

The signature version header is currently:

```text
X-Signature-Version: v1
```

## Python Example

```python
import hashlib
import hmac
import time
from flask import Flask, request, jsonify


app = Flask(__name__)
WEBHOOK_SECRET = "whsec_from_subscription_creation"
MAX_CLOCK_SKEW_SECONDS = 300


def verify_signature(headers: dict, body: bytes) -> bool:
    if headers.get("X-Signature-Version") != "v1":
        return False

    timestamp = headers.get("X-Timestamp", "")
    signature = headers.get("X-Signature", "")
    if not timestamp or not signature:
        return False

    try:
        timestamp_value = int(timestamp)
    except ValueError:
        return False

    if abs(int(time.time()) - timestamp_value) > MAX_CLOCK_SKEW_SECONDS:
        return False

    message = timestamp.encode("utf-8") + b"." + body
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/webhooks/events")
def receive_webhook():
    body = request.get_data()
    headers = request.headers

    if not verify_signature(headers, body):
        return jsonify({"error": "invalid signature"}), 401

    event_id = headers["X-Event-Id"]
    event_type = headers["X-Event-Type"]

    # Use event_id as your idempotency key for downstream processing.
    print("received", event_type, event_id)
    print(body.decode("utf-8"))

    return jsonify({"status": "received"}), 200
```

## Node.js Example

```javascript
import crypto from "crypto";
import express from "express";

const app = express();
const webhookSecret = "whsec_from_subscription_creation";
const maxClockSkewSeconds = 300;

app.use(express.raw({ type: "application/json" }));

function verifySignature(headers, rawBody) {
  if (headers["x-signature-version"] !== "v1") {
    return false;
  }

  const timestamp = headers["x-timestamp"] || "";
  const signature = headers["x-signature"] || "";
  if (!timestamp || !signature) {
    return false;
  }

  const timestampValue = Number(timestamp);
  if (!Number.isInteger(timestampValue)) {
    return false;
  }

  const now = Math.floor(Date.now() / 1000);
  if (Math.abs(now - timestampValue) > maxClockSkewSeconds) {
    return false;
  }

  const message = Buffer.concat([
    Buffer.from(timestamp, "utf8"),
    Buffer.from(".", "utf8"),
    rawBody,
  ]);

  const expected =
    "sha256=" +
    crypto.createHmac("sha256", webhookSecret).update(message).digest("hex");

  return crypto.timingSafeEqual(
    Buffer.from(expected, "utf8"),
    Buffer.from(signature, "utf8"),
  );
}

app.post("/webhooks/events", (req, res) => {
  if (!verifySignature(req.headers, req.body)) {
    return res.status(401).json({ error: "invalid signature" });
  }

  const eventId = req.headers["x-event-id"];
  const eventType = req.headers["x-event-type"];

  console.log("received", eventType, eventId);
  console.log(req.body.toString("utf8"));

  return res.status(200).json({ status: "received" });
});
```

## Delivery Semantics

- a `2xx` response is treated as success
- a non-`2xx` response or transport failure is treated as failure
- failures are retried with exponential backoff and jitter
- the same `X-Event-Id` may be delivered again during retries or producer
  replay handling

Receivers should therefore make downstream processing idempotent using
`X-Event-Id` or the body field `id`.

## Local Testing

Use [webhook.site](https://webhook.site) or any public request bin:

1. create a tenant API key
2. create a subscription pointing at your temporary URL
3. ingest an event
4. inspect the received headers and body

Example subscription create:

```bash
curl -X POST http://localhost:8000/api/subscriptions/ \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "test.*",
    "target_url": "https://webhook.site/YOUR-ID"
  }'
```

Example event ingest:

```bash
curl -X POST http://localhost:8000/api/events/ \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "test.created",
    "payload": {
      "id": "evt-1"
    },
    "idempotency_key": "evt-1"
  }'
```
