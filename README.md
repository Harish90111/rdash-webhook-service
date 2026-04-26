# Webhook Delivery Service

A centralized, production-ready webhook delivery service built with Django and Clean Architecture principles. Handles event ingestion, subscription management, and reliable fan-out delivery with retry logic.

## Features

- **Event-Driven Architecture**: Async event ingestion and webhook delivery using Celery
- **Reliable Delivery**: Outbox pattern + idempotency keys for at-least-once guarantees
- **Retry Logic**: Exponential backoff with jitter for failed deliveries
- **Multi-Tenant Support**: Complete tenant isolation at repository level
- **API Key Authentication**: Principal-based security model
- **Request Signing**: HMAC-SHA256 signatures for webhook authenticity
- **OpenAPI/Swagger**: Auto-generated API documentation
- **Clean Architecture**: Separated domain, interface, and data layers
- **Comprehensive Testing**: Unit, integration, and E2E tests included

## Architecture

```
rdash-webhook-service/
├── domain/           # Pure Python, zero framework dependencies
│   ├── entities/     # Subscription, WebhookEvent, DeliveryAttempt
│   ├── services/     # Business logic (wildcard matching, retry policies)
│   ├── interfaces/   # ABCs/Protocols for repositories and gateways
│   └── exceptions/   # Domain-specific exceptions
├── interface/        # Django-specific entry points
│   ├── views/        # DRF views (thin, delegate to use cases)
│   ├── serializers/  # Request/response serialization
│   ├── urls/         # URL routing
│   └── tasks/        # Celery task definitions
├── data/             # Infrastructure implementations
│   ├── models/       # Django ORM models
│   ├── repositories/ # Repository implementations
│   └── gateways/     # HTTP client for outgoing webhooks
├── tests/            # Test suite
└── config/           # Django settings
```

## Prerequisites

- Python 3.9+
- PostgreSQL 12+ (or SQLite for local development)
- Redis 6+
- Docker & Docker Compose (optional, for containerized setup)

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd rdash-webhook-service
```

### 2. Create and activate virtual environment

```bash
# Using venv
python -m venv .venv

# Activate (Linux/macOS)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

```bash
cp .env.example .env
# Edit .env with your configuration
```

**Key environment variables:**
```env
# Django
DEBUG=True
DJANGO_SECRET_KEY=your-secret-key-here
APP_ENV=development

# Database (PostgreSQL)
DATABASE_URL=postgresql://user:password@localhost:5432/webhook_service

# Redis/Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Or use SQLite for local development
USE_SQLITE=True
```

### 5. Run migrations

```bash
python manage.py migrate
```

## Running the Application

### Development Mode

**Terminal 1 - Django Development Server:**
```bash
python manage.py runserver
```

**Terminal 2 - Celery Worker:**
```bash
celery -A config worker -l info
```

**Terminal 3 - Celery Beat (Optional - for scheduled tasks):**
```bash
celery -A config beat -l info
```

### Using Docker Compose

```bash
docker-compose up
```

This starts:
- Web service (Django)
- Worker service (Celery)
- Redis broker
- PostgreSQL database

## API Documentation

### OpenAPI/Swagger UI

Once the server is running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/api/docs/
- **ReDoc (Alternative)**: http://localhost:8000/api/redoc/
- **Raw OpenAPI Schema**: http://localhost:8000/api/schema/

### Key API Endpoints

#### Subscriptions
- `POST /api/subscriptions/` - Create a new webhook subscription
- `GET /api/subscriptions/` - List all subscriptions
- `GET /api/subscriptions/{id}/` - Get subscription details
- `PATCH /api/subscriptions/{id}/` - Update subscription (activate/deactivate)
- `DELETE /api/subscriptions/{id}/` - Delete subscription

#### Events
- `POST /api/events/` - Ingest a new event
- `GET /api/events/` - List all events

#### Delivery Attempts
- `GET /api/delivery-attempts/` - View webhook delivery history

### Authentication

All API endpoints require API key authentication via the `Authorization` header:

```bash
curl -H "Authorization: ApiKey your-api-key" \
  http://localhost:8000/api/subscriptions/
```

### Example: Create a Subscription

```bash
curl -X POST http://localhost:8000/api/subscriptions/ \
  -H "Authorization: ApiKey your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "order.created",
    "target_url": "https://your-webhook-endpoint.com/webhooks",
    "active": true
  }'
```

**Response** (secret returned once):
```json
{
  "id": "sub_123abc",
  "event_type": "order.created",
  "target_url": "https://your-webhook-endpoint.com/webhooks",
  "active": true,
  "secret": "whsec_abcd1234efgh5678",
  "created_at": "2024-04-26T10:30:00Z"
}
```

### Example: Ingest an Event

```bash
curl -X POST http://localhost:8000/api/events/ \
  -H "Authorization: ApiKey your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "order.created",
    "payload": {
      "order_id": "12345",
      "amount": 99.99,
      "customer": "john@example.com"
    }
  }'
```

**Response:**
```json
{
  "id": "evt_xyz789",
  "event_type": "order.created",
  "payload": { ... },
  "created_at": "2024-04-26T10:35:00Z"
}
```

## Testing

### Run all tests

```bash
pytest
```

### Run specific test categories

```bash
# Unit tests only
pytest tests/domain/

# Integration tests
pytest tests/integration/

# E2E tests
pytest tests/e2e/

# With coverage report
pytest --cov=domain --cov=interface --cov=data
```

### Generate coverage HTML report

```bash
pytest --cov=. --cov-report=html
open htmlcov/index.html
```

## Configuration

### Environment-Based Settings

The application supports multiple environments via `APP_ENV`:

- `development` - Debug mode enabled, SQLite by default
- `staging` - Debug mode disabled, requires PostgreSQL
- `production` - Enhanced security, strict validation

Set via environment variable:
```bash
APP_ENV=production
```

### Celery Configuration

Key worker settings in `config/settings.py`:

```python
CELERY_WORKER_CONCURRENCY = 4  # Worker processes
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Prevent task starvation
CELERY_TASK_ACKS_LATE = True  # Acknowledge after completion
```

### Database

- **Production**: PostgreSQL (via `DATABASE_URL`)
- **Development**: PostgreSQL or SQLite (set `USE_SQLITE=True`)

## Security

### API Key Management

Create an API key for authenticated requests:
```bash
python manage.py createsuperuser
python manage.py create_apikey
```

### Secret Storage

Webhook subscription secrets are:
- Auto-generated on creation
- Returned **only once** in the creation response
- Hashed/encrypted in the database
- Never included in GET/PATCH responses

### Request Signing

Outgoing webhooks include an `X-Signature` header with HMAC-SHA256 signature:

```
X-Signature: sha256={timestamp}.{signature}
```

Verify on receiving end:
```python
import hmac
import hashlib

def verify_webhook(secret, timestamp, body, signature):
    message = f"{timestamp}.{body}".encode()
    expected = hmac.new(
        secret.encode(),
        message,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

## Deployment

### Using Docker

Build and push image:
```bash
docker build -t webhook-service:latest .
docker push your-registry/webhook-service:latest
```

Run with docker-compose:
```bash
docker-compose -f docker-compose.yml up -d
```

### Environment Setup

Create `.env.production` with:
```env
APP_ENV=production
DEBUG=False
DJANGO_SECRET_KEY=<generate-secure-key>
DATABASE_URL=postgresql://user:pwd@db-host:5432/db
CELERY_BROKER_URL=redis://redis-host:6379/0
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
```

### Health Check

```bash
curl http://localhost:8000/health/
```

## Monitoring & Logging

### Logs Location

- **Application logs**: `logs/django.log`
- **Celery worker logs**: Printed to terminal/container output

### Enable Debug Logging

```python
# In .env
DJANGO_LOG_LEVEL=DEBUG
```

### Metrics

Track webhook delivery via the admin interface or query directly:
```bash
python manage.py shell
>>> from data.models import DeliveryAttempt
>>> DeliveryAttempt.objects.filter(status='success').count()
```

## Development Guidelines

### Clean Architecture Principles

1. **Domain Layer** (Pure Python, no Django imports)
   - Contains business logic and entities
   - Can be used in FastAPI or other frameworks
   - Must pass linting: `# flake8: noqa` only for migrations

2. **Interface Layer** (Django-specific)
   - Thin views that delegate to use cases
   - Serializers for request/response validation
   - Never contains business logic

3. **Data Layer** (Infrastructure)
   - Repository implementations
   - Django models and migrations
   - External service integrations (HTTP gateway)

### Code Style

```bash
# Format code
black . --line-length=100

# Check style
flake8 . --max-line-length=100

# Type checking (optional)
mypy domain/
```

## Troubleshooting

### Celery Not Connecting

Check Redis is running:
```bash
redis-cli ping
# Should return: PONG
```

### Database Connection Error

Verify PostgreSQL/SQLite:
```bash
# PostgreSQL
psql -h localhost -U user -d webhook_service

# SQLite
sqlite3 db.sqlite3 ".tables"
```

### Permission Denied on `.venv`

Regenerate virtual environment:
```bash
rm -rf .venv
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## Contributing

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Write tests for new functionality
3. Ensure all tests pass: `pytest`
4. Submit a pull request

## License

Proprietary - All rights reserved

## Support

For issues, questions, or feature requests, contact the development team at support@example.com