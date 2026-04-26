# Swagger/OpenAPI Setup & Configuration

Complete guide to using OpenAPI/Swagger documentation for the Webhook Delivery Service API.

## Overview

The service uses **drf-spectacular**, a modern OpenAPI 3.0 schema generator for Django REST Framework. It automatically generates interactive API documentation from your code, eliminating the need for manual documentation updates.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

The `requirements.txt` includes:
```
drf-spectacular>=0.27.0
```

### 2. Start the Development Server

```bash
python manage.py runserver
```

### 3. Access Documentation

Open your browser to:
- **Swagger UI** (Interactive): http://localhost:8000/api/docs/
- **ReDoc** (Alternative): http://localhost:8000/api/redoc/
- **Raw OpenAPI Schema**: http://localhost:8000/api/schema/

---

## Features

### Swagger UI (`/api/docs/`)

Interactive API explorer with:
- ✅ **Try It Out**: Test endpoints directly from the browser
- ✅ **Request/Response Examples**: See sample data for each endpoint
- ✅ **Schema Visualization**: Understand data structures at a glance
- ✅ **Authentication UI**: Easy API key input
- ✅ **Response Codes**: See all possible responses per endpoint

**Usage:**
1. Click on an endpoint to expand it
2. Click "Try It Out" button
3. Fill in request parameters/body
4. Click "Execute"
5. View response status, headers, and body

### ReDoc (`/api/redoc/`)

Alternative documentation viewer:
- Clean, readable layout
- Excellent for production documentation
- API reference PDFs can be generated
- Optimized for mobile

### Raw Schema (`/api/schema/`)

Returns OpenAPI 3.0 JSON schema:
```json
{
  "openapi": "3.0.2",
  "info": {
    "title": "Webhook Delivery Service API",
    "version": "1.0.0",
    "description": "Event-driven webhook delivery service..."
  },
  "paths": { ... },
  "components": { ... }
}
```

Can be used to:
- Generate client SDKs
- Import into Postman
- Integrate with API gateways
- Create external documentation

---

## Configuration

Settings are in `config/settings.py`:

### REST Framework Configuration

```python
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # ... other settings
}
```

This enables automatic schema generation for all DRF endpoints.

### Spectacular Settings

```python
SPECTACULAR_SETTINGS = {
    'TITLE': 'Webhook Delivery Service API',
    'DESCRIPTION': 'Event-driven webhook delivery service...',
    'VERSION': '1.0.0',
    
    'SERVE_PERMISSIONS': [
        'rest_framework.permissions.AllowAny',  # Allow public schema access
    ],
    
    'CONTACT': {
        'name': 'Development Team',
        'email': 'support@example.com',
    },
    
    'LICENSE': {
        'name': 'Proprietary',
    },
    
    'SERVERS': [
        {'url': 'http://localhost:8000', 'description': 'Development'},
        {'url': 'https://api.example.com', 'description': 'Production'},
    ],
    
    'COMPONENT_SPLIT_REQUEST': True,  # Separate request/response schemas
    'SORT_OPERATIONS_BY_NAME': True,   # Sort endpoints alphabetically
}
```

---

## Customizing Schema

### Document Your ViewSet

```python
from rest_framework.viewsets import ModelViewSet
from drf_spectacular.utils import extend_schema, extend_schema_field

class SubscriptionViewSet(ModelViewSet):
    """
    Manage webhook subscriptions.
    
    Create subscriptions to receive webhooks for specific event types.
    """
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Create a new subscription",
        description="Create a webhook subscription for an event type.",
        tags=["subscriptions"],
        examples=[
            {
                "request": {
                    "content": {
                        "application/json": {
                            "example": {
                                "event_type": "order.created",
                                "target_url": "https://webhook.example.com/orders",
                                "active": True
                            }
                        }
                    }
                }
            }
        ]
    )
    def create(self, request, *args, **kwargs):
        """Create a subscription."""
        return super().create(request, *args, **kwargs)
    
    @extend_schema(
        summary="List subscriptions",
        tags=["subscriptions"],
    )
    def list(self, request, *args, **kwargs):
        """List all subscriptions."""
        return super().list(request, *args, **kwargs)
```

### Document Serializer Fields

```python
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

class SubscriptionSerializer(serializers.ModelSerializer):
    secret = serializers.SerializerMethodField(
        help_text="Subscription secret (returned only on creation)"
    )
    
    @extend_schema_field(serializers.CharField)
    def get_secret(self, obj):
        return None  # Secret never shown in API responses
    
    class Meta:
        model = Subscription
        fields = ['id', 'event_type', 'target_url', 'active', 'secret', 'created_at']
        extra_kwargs = {
            'event_type': {
                'help_text': 'Event type to subscribe to (supports wildcards: po.*)',
            },
            'target_url': {
                'help_text': 'HTTPS endpoint to receive webhooks',
            },
        }
```

### Add Request/Response Examples

```python
from drf_spectacular.utils import extend_schema, OpenApiExample

@extend_schema(
    request=EventIngestionSerializer,
    responses={201: EventSerializer},
    examples=[
        OpenApiExample(
            'Success',
            value={
                "id": "evt_abc123",
                "event_type": "order.created",
                "payload": {
                    "order_id": "ORD-12345",
                    "amount": 99.99
                },
                "created_at": "2024-04-26T10:45:00Z"
            },
            response_only=True,
            status_codes=['201']
        ),
    ]
)
def create_event(request):
    """Ingest a new event."""
    pass
```

---

## Hiding Endpoints from Schema

If you have internal endpoints, exclude them from Swagger:

```python
from drf_spectacular.utils import extend_schema

@extend_schema(exclude=True)
def health_check(request):
    """Internal health check - not in public schema."""
    pass
```

Or exclude entire views:

```python
class InternalViewSet(ModelViewSet):
    exclude_from_schema = True
```

---

## Authentication in Swagger

### API Key Authentication

API key auth is automatically detected. In Swagger:

1. Click the "Authorize" button (🔓)
2. Paste your API key in the `ApiKey` field
3. Click "Authorize"
4. All requests will include the key

### Generate an API Key

```bash
python manage.py shell
>>> from rest_framework.authtoken.models import Token
>>> from django.contrib.auth.models import User
>>> user = User.objects.get(username='your_user')
>>> token, created = Token.objects.get_or_create(user=user)
>>> print(token.key)  # Use this in Swagger
```

---

## Validation & Linting

### Validate Schema

Ensure your schema is valid:

```bash
python manage.py spectacular --file schema.json
python manage.py spectacular --validate
```

### Check for Documentation Issues

```bash
python manage.py spectacular --file schema.json --validation
```

---

## Exporting Schema

### Export to JSON

```bash
python manage.py spectacular --file docs/openapi-schema.json
```

### Export to YAML

```bash
# Install pyyaml first
pip install pyyaml

# Export
python manage.py spectacular --file docs/openapi-schema.yaml
```

### Use Schema with External Tools

#### Import into Postman

1. Generate schema: `python manage.py spectacular --file schema.json`
2. Open Postman
3. Click "Import"
4. Select the JSON file
5. Collections automatically created

#### Import into Insomnia

1. Generate schema
2. Open Insomnia
3. "Design" → "Import" → Select JSON file

#### Publish to SwaggerHub

1. Create account at https://swaggerhub.com
2. Create new API
3. Paste schema JSON content
4. Share public link

---

## Custom Branding & Styling

### Update Info in Settings

```python
SPECTACULAR_SETTINGS = {
    'TITLE': 'My Company Webhook API',
    'DESCRIPTION': '''
        Reliable webhook delivery service
        
        ## Features
        - Event ingestion API
        - Subscription management
        - Automatic retries with exponential backoff
    ''',
    'VERSION': '2.0.0',
    'CONTACT': {
        'name': 'API Support',
        'email': 'api-support@mycompany.com',
        'url': 'https://api.mycompany.com/support',
    },
    'LICENSE': {
        'name': 'MIT License',
        'url': 'https://opensource.org/licenses/MIT',
    },
    'TAGS': [
        {
            'name': 'subscriptions',
            'description': 'Manage webhook subscriptions',
        },
        {
            'name': 'events',
            'description': 'Ingest and list events',
        },
    ],
}
```

### Custom Swagger UI Config

```python
SPECTACULAR_SETTINGS = {
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'presets': [
            'swagger-ui/dist/swagger-ui.js',
            'swagger-ui/dist/swagger-ui-standalone-preset.js',
        ],
        'layout': 'BaseLayout',
        'requestInterceptor': 'function(request) { return request; }',
    },
}
```

---

## Troubleshooting

### Schema Not Updating

Clear Django cache:
```bash
python manage.py clear_cache
rm -rf .pytest_cache __pycache__
```

Restart development server:
```bash
python manage.py runserver
```

### Serializer Fields Missing from Schema

Ensure serializer is properly defined:
```python
class MySerializer(serializers.Serializer):
    field_name = serializers.CharField(help_text="...")  # Add help_text
```

### Authentication Not Working in Swagger

Verify auth is enabled in settings:
```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'interface.authentication.APIKeyAuthentication',
    ],
}
```

### Custom View Methods Not in Schema

Use `@extend_schema` decorator:
```python
from drf_spectacular.utils import extend_schema

@extend_schema(summary="Custom action")
@action(methods=['post'], detail=True)
def custom_action(self, request, pk=None):
    pass
```

---

## Best Practices

1. **Always Add Docstrings**: Used as endpoint descriptions
   ```python
   def list(self, request):
       """List all subscriptions with optional filtering."""
   ```

2. **Use `help_text`** on fields:
   ```python
   event_type = serializers.CharField(
       help_text="Event type (wildcards: po.*)"
   )
   ```

3. **Document Status Codes**:
   ```python
   @extend_schema(
       responses={
           200: SubscriptionSerializer,
           401: {"description": "Authentication failed"},
           404: {"description": "Subscription not found"},
       }
   )
   ```

4. **Include Examples**:
   ```python
   @extend_schema(
       examples=[
           OpenApiExample('Success', value={...}),
           OpenApiExample('Error', value={...}),
       ]
   )
   ```

5. **Version Your API**:
   ```python
   # In settings.py
   SPECTACULAR_SETTINGS = {
       'VERSION': '1.2.3',  # Update per release
   }
   ```

---

## Production Considerations

### Disable Interactive Features

In production, disable schema editing:
```python
# settings.py
if not DEBUG:
    SPECTACULAR_SETTINGS = {
        'SERVE_PERMISSIONS': [
            'rest_framework.permissions.IsAdminUser',  # Admins only
        ],
    }
```

### Use HTTPS URLs Only

```python
SPECTACULAR_SETTINGS = {
    'SERVERS': [
        {'url': 'https://api.example.com', 'description': 'Production'},
    ] if not DEBUG else [
        {'url': 'http://localhost:8000', 'description': 'Development'},
    ],
}
```

### Cache Schema

```python
# Cache the schema to reduce load
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

SPECTACULAR_SETTINGS = {
    'SCHEMA_CACHE_TIMEOUT': 3600,  # Cache for 1 hour
}
```

---

## References

- [drf-spectacular Documentation](https://drf-spectacular.readthedocs.io/)
- [OpenAPI 3.0 Specification](https://spec.openapis.org/oas/v3.0.3)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Swagger UI Documentation](https://github.com/swagger-api/swagger-ui)
