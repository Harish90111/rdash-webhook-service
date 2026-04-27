# Quick Start

Get the service running locally and make your first authenticated API calls.

## 1. Install and bootstrap

### Windows PowerShell

```powershell
.\bin\setup.ps1 -Action Bootstrap -UseSqlite
```

### Manual setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py check
```

For lightweight local development, add this to `.env`:

```env
USE_SQLITE=True
```

## 2. Run the app

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

## 3. Bootstrap a tenant

Create an admin user:

```bash
python manage.py createsuperuser
```

Open <http://localhost:8000/admin/> and:

1. create a `Tenant`
2. create a tenant API key for that tenant

Or issue the API key from the command line:

```bash
python manage.py create_api_key --tenant-id <tenant-uuid> --name "local-dev"
```

The raw key is shown once.

## 4. Explore the docs

- Swagger UI: <http://localhost:8000/api/docs/>
- ReDoc: <http://localhost:8000/api/redoc/>
- Schema: <http://localhost:8000/api/schema/>

## 5. Create a subscription

```bash
curl -X POST http://localhost:8000/api/subscriptions/ \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "po.*",
    "target_url": "https://webhook.site/your-id",
    "active": true
  }'
```

## 6. Send an event

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

If the same idempotency key is replayed for the same tenant, the service
returns the existing event instead of creating a duplicate.

## 7. Check service health and metrics

```bash
curl http://localhost:8000/api/health/
curl -H "X-API-Key: YOUR_API_KEY" http://localhost:8000/api/metrics/
```

## 8. Inspect delivery attempts

```bash
curl -G http://localhost:8000/api/deliveries/ \
  -H "X-API-Key: YOUR_API_KEY" \
  --data-urlencode "status=retrying" \
  --data-urlencode "page=1" \
  --data-urlencode "page_size=20"
```

## 9. Requeue a failed delivery

```bash
curl -X POST http://localhost:8000/api/deliveries/DELIVERY_ATTEMPT_ID/retry/ \
  -H "X-API-Key: YOUR_API_KEY"
```

## Testing shortcuts

```bash
pytest tests/domain -q
pytest tests/integration -q
pytest tests/e2e -q
```

## Where to look next

- [README.md](../README.md)
- [API_DOCUMENTATION.md](./API_DOCUMENTATION.md)
- [WEBHOOK_INTEGRATION.md](./WEBHOOK_INTEGRATION.md)
- [DESIGN.md](../DESIGN.md)
