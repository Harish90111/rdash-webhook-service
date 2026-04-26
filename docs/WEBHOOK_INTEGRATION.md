# Webhook Integration Examples

Guide for integrating your application to receive and verify webhooks from the Webhook Delivery Service.

## Receiving Webhooks

When you subscribe to an event type, the service delivers webhooks to your endpoint via HTTP POST requests.

### Webhook Request Format

**Method:** `POST`  
**Content-Type:** `application/json`

**Headers:**
```
X-Webhook-ID: evt_abc123
X-Delivery-ID: del_456789
X-Signature: sha256=1234567890abcdef...
Timestamp: 1719407100
```

**Body:**
```json
{
  "id": "evt_abc123",
  "event_type": "order.created",
  "timestamp": "2024-04-26T10:45:00Z",
  "payload": {
    "order_id": "ORD-12345",
    "amount": 99.99,
    "customer_email": "john@example.com"
  }
}
```

---

## Security: Verifying Webhook Signatures

### Why Verify Signatures?

- ✅ Confirm webhook came from the service (not spoofed)
- ✅ Detect tampering with webhook data
- ✅ Protect against replay attacks (using timestamp)

### Signature Format

The `X-Signature` header contains an HMAC-SHA256 signature:

```
X-Signature: sha256={base64_encoded_hmac}
```

The signed message is: `{timestamp}.{raw_request_body}`

### Python Example

```python
import hmac
import hashlib
import json
import time
from functools import wraps
from flask import request, abort

WEBHOOK_SECRET = "whsec_abcd1234efgh5678ijkl9101112"  # From subscription creation
MAX_TIMESTAMP_AGE = 300  # 5 minutes - prevent replay attacks

def verify_webhook_signature(f):
    """Decorator to verify webhook signatures."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Extract signature header
        signature_header = request.headers.get('X-Signature', '')
        timestamp = request.headers.get('Timestamp', '')
        
        if not signature_header or not timestamp:
            return {'error': 'Missing signature or timestamp'}, 401
        
        # Verify timestamp is recent (prevent replay)
        try:
            timestamp_int = int(timestamp)
            current_time = int(time.time())
            if abs(current_time - timestamp_int) > MAX_TIMESTAMP_AGE:
                return {'error': 'Timestamp too old'}, 401
        except (ValueError, TypeError):
            return {'error': 'Invalid timestamp'}, 401
        
        # Get raw request body
        request_body = request.get_data(as_text=True)
        
        # Reconstruct the signed message
        message = f"{timestamp}.{request_body}".encode('utf-8')
        
        # Calculate expected signature
        expected_signature = hmac.new(
            WEBHOOK_SECRET.encode('utf-8'),
            message,
            hashlib.sha256
        ).hexdigest()
        
        # Extract signature from header (format: sha256=<hex>)
        try:
            _, received_signature = signature_header.split('=', 1)
        except ValueError:
            return {'error': 'Invalid signature format'}, 401
        
        # Compare signatures (constant-time to prevent timing attacks)
        if not hmac.compare_digest(expected_signature, received_signature):
            return {'error': 'Signature verification failed'}, 401
        
        # Signature valid, call the wrapped function
        return f(*args, **kwargs)
    
    return decorated_function

@app.route('/webhooks/events', methods=['POST'])
@verify_webhook_signature
def handle_webhook():
    """Handle incoming webhook."""
    webhook = request.json
    
    # Process webhook
    print(f"Received {webhook['event_type']} event")
    print(f"Data: {webhook['payload']}")
    
    # Always return 200 to acknowledge receipt
    return {'status': 'received'}, 200
```

### Node.js/Express Example

```javascript
import crypto from 'crypto';
import express from 'express';

const WEBHOOK_SECRET = 'whsec_abcd1234efgh5678ijkl9101112';
const MAX_TIMESTAMP_AGE = 300; // 5 minutes

function verifyWebhookSignature(req, res, next) {
  const signatureHeader = req.headers['x-signature'] || '';
  const timestamp = req.headers['timestamp'] || '';
  
  if (!signatureHeader || !timestamp) {
    return res.status(401).json({ error: 'Missing signature or timestamp' });
  }
  
  // Verify timestamp is recent
  const timestampInt = parseInt(timestamp, 10);
  const currentTime = Math.floor(Date.now() / 1000);
  if (Math.abs(currentTime - timestampInt) > MAX_TIMESTAMP_AGE) {
    return res.status(401).json({ error: 'Timestamp too old' });
  }
  
  // Get raw request body
  const rawBody = req.rawBody; // Need to capture raw body before JSON parsing
  
  // Reconstruct signed message
  const message = `${timestamp}.${rawBody}`;
  
  // Calculate expected signature
  const expectedSignature = crypto
    .createHmac('sha256', WEBHOOK_SECRET)
    .update(message)
    .digest('hex');
  
  // Extract signature from header
  const [algo, receivedSignature] = signatureHeader.split('=');
  if (algo !== 'sha256') {
    return res.status(401).json({ error: 'Invalid signature algorithm' });
  }
  
  // Compare (constant-time)
  if (!crypto.timingSafeEqual(
    Buffer.from(expectedSignature),
    Buffer.from(receivedSignature)
  )) {
    return res.status(401).json({ error: 'Signature verification failed' });
  }
  
  next();
}

// Middleware to capture raw body
app.use(express.raw({ type: 'application/json' }));

// Convert raw body to JSON for easier handling
app.use((req, res, next) => {
  if (req.body) {
    req.rawBody = req.body.toString('utf-8');
    req.body = JSON.parse(req.rawBody);
  }
  next();
});

app.post('/webhooks/events', verifyWebhookSignature, (req, res) => {
  const webhook = req.body;
  
  // Process webhook
  console.log(`Received ${webhook.event_type} event`);
  console.log(`Data: ${JSON.stringify(webhook.payload)}`);
  
  // Always return 200 to acknowledge
  res.status(200).json({ status: 'received' });
});
```

### Java/Spring Boot Example

```java
import org.springframework.web.bind.annotation.*;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.InvalidKeyException;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.HexFormat;

@RestController
@RequestMapping("/webhooks")
public class WebhookController {
    
    private static final String WEBHOOK_SECRET = "whsec_abcd1234efgh5678ijkl9101112";
    private static final long MAX_TIMESTAMP_AGE = 300; // 5 minutes
    
    @PostMapping("/events")
    public ResponseEntity<Map<String, String>> handleWebhook(
            @RequestHeader("X-Signature") String signature,
            @RequestHeader("Timestamp") String timestamp,
            @RequestBody String rawBody) {
        
        // Verify signature
        try {
            if (!verifySignature(signature, timestamp, rawBody)) {
                return ResponseEntity
                    .status(HttpStatus.UNAUTHORIZED)
                    .body(Map.of("error", "Signature verification failed"));
            }
        } catch (Exception e) {
            return ResponseEntity
                .status(HttpStatus.UNAUTHORIZED)
                .body(Map.of("error", "Invalid signature"));
        }
        
        // Parse webhook
        ObjectMapper mapper = new ObjectMapper();
        WebhookEvent webhook = mapper.readValue(rawBody, WebhookEvent.class);
        
        // Process webhook
        System.out.println("Received " + webhook.getEventType() + " event");
        System.out.println("Data: " + webhook.getPayload());
        
        return ResponseEntity
            .ok(Map.of("status", "received"));
    }
    
    private boolean verifySignature(String signatureHeader, String timestamp, String rawBody)
            throws NoSuchAlgorithmException, InvalidKeyException {
        
        // Verify timestamp
        long timestampLong = Long.parseLong(timestamp);
        long currentTime = Instant.now().getEpochSecond();
        if (Math.abs(currentTime - timestampLong) > MAX_TIMESTAMP_AGE) {
            throw new IllegalArgumentException("Timestamp too old");
        }
        
        // Reconstruct message
        String message = timestamp + "." + rawBody;
        
        // Calculate HMAC
        Mac hmac = Mac.getInstance("HmacSHA256");
        SecretKeySpec key = new SecretKeySpec(
            WEBHOOK_SECRET.getBytes(StandardCharsets.UTF_8),
            "HmacSHA256"
        );
        hmac.init(key);
        
        byte[] digest = hmac.doFinal(message.getBytes(StandardCharsets.UTF_8));
        String expectedSignature = HexFormat.of().formatHex(digest);
        
        // Extract signature from header
        String[] parts = signatureHeader.split("=");
        if (parts.length != 2 || !"sha256".equals(parts[0])) {
            return false;
        }
        String receivedSignature = parts[1];
        
        // Compare (constant-time)
        return MessageDigest.isEqual(
            expectedSignature.getBytes(),
            receivedSignature.getBytes()
        );
    }
}
```

---

## Handling Webhooks

### 1. Verify Signature (See Above)

### 2. Check Idempotency

Use the `X-Delivery-ID` header to prevent processing duplicates:

```python
@handle_webhook
def process_webhook(webhook):
    delivery_id = request.headers.get('X-Delivery-ID')
    
    # Check if already processed
    if DeliveryLog.objects.filter(delivery_id=delivery_id).exists():
        print(f"Duplicate delivery {delivery_id}, ignoring")
        return {'status': 'duplicate'}, 200
    
    # Process webhook
    try:
        process_event(webhook)
        
        # Log successful processing
        DeliveryLog.objects.create(
            delivery_id=delivery_id,
            event_id=webhook['id'],
            status='success'
        )
        return {'status': 'received'}, 200
    except Exception as e:
        # Log failed processing
        DeliveryLog.objects.create(
            delivery_id=delivery_id,
            event_id=webhook['id'],
            status='failed',
            error=str(e)
        )
        # Return non-200 to trigger retry
        return {'error': str(e)}, 500
```

### 3. Respond Quickly

- Respond with `2xx` status within 30 seconds
- Move long operations to background jobs
- Return `2xx` even if processing fails (don't retry)

```python
from celery import shared_task

@handle_webhook
def receive_webhook(webhook):
    delivery_id = request.headers.get('X-Delivery-ID')
    
    # Queue processing, return immediately
    process_webhook_async.delay(webhook, delivery_id)
    
    return {'status': 'queued'}, 202

@shared_task
def process_webhook_async(webhook, delivery_id):
    # Heavy processing here
    print(f"Processing webhook {delivery_id}")
    # Update database, call APIs, etc.
```

### 4. Error Handling

```python
@handle_webhook
def receive_webhook(webhook):
    try:
        validate_webhook(webhook)
        process_webhook(webhook)
        return {'status': 'success'}, 200
    except ValidationError as e:
        # Bad webhook format - don't retry
        logger.warning(f"Invalid webhook: {e}")
        return {'error': str(e)}, 400
    except TemporaryError as e:
        # Service temporarily unavailable - retry
        logger.error(f"Temporary error: {e}")
        return {'error': str(e)}, 500
    except Exception as e:
        # Unknown error - let service decide on retry
        logger.exception(f"Unexpected error: {e}")
        return {'error': 'Internal error'}, 500
```

---

## Testing Webhooks Locally

### Using ngrok

Expose local server to internet:

```bash
# Install ngrok
brew install ngrok  # macOS
# or download from https://ngrok.com/

# Start local server
python manage.py runserver

# In another terminal, expose to internet
ngrok http 8000
```

Get public URL (e.g., `https://abc123.ngrok.io`), use for webhook subscription:

```bash
curl -X POST http://localhost:8000/api/subscriptions/ \
  -H "Authorization: ApiKey your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "test.event",
    "target_url": "https://abc123.ngrok.io/webhooks/events",
    "active": true
  }'
```

### Using RequestBin

Debug webhook requests at https://requestbin.com:

1. Create new request bin (get URL like `https://requestbin.com/r/abc123`)
2. Subscribe to webhook with that URL
3. Trigger event
4. View all requests in RequestBin

### Webhook Testing Library

```python
# tests/test_webhook_integration.py
import pytest
from django.test import Client
from rest_framework.test import APIClient

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def api_key():
    # Create test API key
    from rest_framework.authtoken.models import Token
    from django.contrib.auth.models import User
    
    user = User.objects.create_user(username='test')
    token = Token.objects.create(user=user)
    return str(token.key)

def test_webhook_signature_verification(api_client, api_key):
    """Test that invalid signatures are rejected."""
    from rest_framework.test import APIRequestFactory
    import hmac
    import hashlib
    
    webhook_data = {
        "event_type": "test.event",
        "payload": {"test": "data"}
    }
    
    # Sign with wrong secret
    wrong_secret = "wrong_secret"
    timestamp = str(int(time.time()))
    body = json.dumps(webhook_data)
    
    wrong_signature = hmac.new(
        wrong_secret.encode(),
        f"{timestamp}.{body}".encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Send webhook with wrong signature
    response = api_client.post(
        '/webhooks/events',
        data=body,
        content_type='application/json',
        HTTP_X_SIGNATURE=f'sha256={wrong_signature}',
        HTTP_TIMESTAMP=timestamp
    )
    
    # Should be rejected
    assert response.status_code == 401
```

---

## Common Webhook Issues

### Webhook Never Delivered

1. **Check subscription is active**
   ```
   GET /api/subscriptions/{id}/
   ```

2. **Check event type matches subscription pattern**
   - Subscription: `order.*`
   - Event: `order.created` ✅
   - Event: `user.created` ❌

3. **Check delivery attempts**
   ```
   GET /api/delivery-attempts/?subscription_id=sub_123
   ```

4. **Check webhook endpoint is accessible**
   - Must be publicly accessible HTTPS URL
   - Must return `2xx` response
   - Must respond within 30 seconds

### Webhook Delivery Retried Many Times

- Service retries failed webhooks up to 7 times
- Use exponential backoff: 1s, 2s, 4s, 8s, 16s, 32s, 60s
- Fix your endpoint, retries will continue automatically
- Check `X-Delivery-ID` to prevent duplicate processing

### Signature Verification Fails

1. Verify you have the correct secret from subscription creation
2. Check timestamp is within 5 minutes of current time
3. Ensure you're using SHA256, not MD5/SHA1
4. Use constant-time comparison to prevent timing attacks

---

## Best Practices

✅ **Do:**
- Always verify signatures
- Use constant-time signature comparison
- Respond quickly (queue heavy work)
- Log webhook delivery ID for support
- Use delivery ID to prevent duplicates
- Return 200-299 for success, 400-599 for failure

❌ **Don't:**
- Trust unverified webhooks
- Do CPU-intensive work before responding
- Ignore timestamp validation
- Process duplicate delivery IDs
- Return 2xx for every response (hampers debugging)
- Hardcode secrets (use environment variables)

---

## References

- [OWASP: Webhook Security](https://cheatsheetseries.owasp.org/cheatsheets/Webhook_Security_Cheat_Sheet.html)
- [RFC 2104: HMAC](https://datatracker.ietf.org/doc/html/rfc2104)
- [Svix Webhook Guide](https://docs.svix.com/webhook-guide)
