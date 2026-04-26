# Quick Start Guide

Get the Webhook Delivery Service running and making API calls in 5 minutes.

## Prerequisites

- Python 3.9+
- PostgreSQL or SQLite (for local dev)
- curl or Postman for testing

## 1. Install & Configure (2 minutes)

```bash
# Clone repo
git clone <repo-url>
cd rdash-webhook-service

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or .venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# For local dev with SQLite, set: USE_SQLITE=True
```

## 2. Run the Server (1 minute)

```bash
# Terminal 1: Django server
python manage.py migrate
python manage.py runserver

# Terminal 2: Celery worker (optional, for async delivery)
celery -A config worker -l info
```

Server running at: **http://localhost:8000**

## 3. Explore API Docs (1 minute)

Open browser:
- **Swagger UI**: http://localhost:8000/api/docs/
- **ReDoc**: http://localhost:8000/api/redoc/

## 4. Make Your First API Call (1 minute)

### Get API Key

For local testing, use dummy key:
```bash
API_KEY="local-test-key-12345"
```

### Create a Subscription

```bash
curl -X POST http://localhost:8000/api/subscriptions/ \
  -H "Authorization: ApiKey ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "order.created",
    "target_url": "https://webhook.site/unique-id",
    "active": true
  }'
```

**Response:**
```json
{
  "id": "sub_abc123",
  "event_type": "order.created",
  "target_url": "https://webhook.site/unique-id",
  "active": true,
  "secret": "whsec_xyz789...",
  "created_at": "2024-04-26T10:00:00Z"
}
```

⚠️ **Save the secret!** It's returned only once.

### Send an Event

```bash
curl -X POST http://localhost:8000/api/events/ \
  -H "Authorization: ApiKey ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "order.created",
    "payload": {
      "order_id": "12345",
      "amount": 99.99
    }
  }'
```

**Response:**
```json
{
  "id": "evt_def456",
  "event_type": "order.created",
  "payload": {
    "order_id": "12345",
    "amount": 99.99
  },
  "created_at": "2024-04-26T10:05:00Z"
}
```

### Check Delivery Status

```bash
# Get all delivery attempts
curl -H "Authorization: ApiKey ${API_KEY}" \
  http://localhost:8000/api/delivery-attempts/
```

---

## Common Tasks

### Test Webhook Locally

Use [webhook.site](https://webhook.site):

1. Go to https://webhook.site
2. Copy unique URL
3. Create subscription with that URL:
   ```bash
   curl -X POST http://localhost:8000/api/subscriptions/ \
     -H "Authorization: ApiKey ${API_KEY}" \
     -H "Content-Type: application/json" \
     -d '{
       "event_type": "test.*",
       "target_url": "https://webhook.site/YOUR-UNIQUE-ID"
     }'
   ```
4. Send event, watch it appear in webhook.site UI

### Use Postman

1. Export schema: `python manage.py spectacular --file schema.json`
2. Open Postman → Import → Select `schema.json`
3. Click "Authorize" button, paste API key
4. Make requests from collection

### Run Tests

```bash
pytest                              # All tests
pytest tests/domain/                # Unit tests only
pytest -v                           # Verbose
pytest --cov=.                      # With coverage
```

### Create Admin User

```bash
python manage.py createsuperuser
# Then visit http://localhost:8000/admin/
```

---

## Project Structure at a Glance

```
rdash-webhook-service/
├── README.md                    # Full setup guide
├── docs/
│   ├── API_DOCUMENTATION.md     # Complete API reference
│   ├── SWAGGER_SETUP.md         # Swagger/OpenAPI details
│   └── WEBHOOK_INTEGRATION.md   # How to receive webhooks
├── config/
│   ├── settings.py              # Django config
│   ├── urls.py                  # API routes
│   └── celery.py                # Celery config
├── domain/                      # Pure Python business logic
│   ├── entities/                # Data models
│   ├── services/                # Services (retry, signing, etc.)
│   └── interfaces/              # Abstract interfaces
├── interface/                   # Django views & serializers
├── data/                        # Database & HTTP implementations
└── tests/                       # Test suite
```

## Key Concepts

### Event Type Matching

Subscriptions support **wildcard patterns**:
- `order.created` - Exact match only
- `order.*` - Matches `order.created`, `order.updated`, etc.
- `*.created` - Matches any `.created` event

### Webhook Delivery

1. Event ingested → stored immediately
2. Celery worker matches subscriptions
3. One delivery task per subscription
4. Automatic retries on failure (up to 7 times)
5. Response must be 2xx within 30 seconds

### Security

- **API Key Auth**: Required header `Authorization: ApiKey YOUR_KEY`
- **Signatures**: Outgoing webhooks signed with HMAC-SHA256
- **Secrets**: One-time display, stored hashed

---

## API Endpoints Summary

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/subscriptions/` | Create subscription |
| `GET` | `/api/subscriptions/` | List subscriptions |
| `GET` | `/api/subscriptions/{id}/` | Get one subscription |
| `PATCH` | `/api/subscriptions/{id}/` | Update subscription |
| `DELETE` | `/api/subscriptions/{id}/` | Delete subscription |
| `POST` | `/api/events/` | Ingest event |
| `GET` | `/api/events/` | List events |
| `GET` | `/api/delivery-attempts/` | Check delivery status |

---

## Troubleshooting

**"Connection refused" - Is server running?**
```bash
# Check if port 8000 is listening
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows
```

**"No module named 'rest_framework'"**
```bash
pip install -r requirements.txt
```

**Database errors?**
```bash
python manage.py migrate
```

**Tests failing?**
```bash
pytest --tb=short -v  # Detailed output
```

---

## Next Steps

1. **Read Full Docs**: [README.md](../README.md)
2. **Explore API**: http://localhost:8000/api/docs/
3. **Test Webhooks**: [WEBHOOK_INTEGRATION.md](./WEBHOOK_INTEGRATION.md)
4. **Configure Swagger**: [SWAGGER_SETUP.md](./SWAGGER_SETUP.md)
5. **Check API Reference**: [API_DOCUMENTATION.md](./API_DOCUMENTATION.md)

---

## Quick Reference Commands

```bash
# Start server
python manage.py runserver

# Start worker
celery -A config worker -l info

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Open shell
python manage.py shell

# Run tests
pytest

# Generate schema
python manage.py spectacular --file schema.json

# Format code
black .

# Lint
flake8 .

# Check coverage
pytest --cov=.
```

---

Need help? Check the full [README.md](../README.md) or [API_DOCUMENTATION.md](./API_DOCUMENTATION.md)
