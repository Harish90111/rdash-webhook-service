# Implementation Plan: Event-Driven Webhook Delivery Service

## Project Overview

Build a centralized Webhook Delivery Service using Django with Clean Architecture (Domain/Interface/Data layers). The service handles event ingestion, subscription management, and reliable fan-out delivery with retry logic.

---

## Phase 1: Project Setup & Infrastructure

### 1.1 Initialize Django Project
- [ ] Create Django project with proper structure
- [ ] Configure settings for multi-tenant architecture
- [ ] Set up PostgreSQL database connection
- [ ] Configure Celery with Redis broker
- [ ] Set up logging and monitoring

### 1.2 Project Structure (Clean Architecture)
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
├── tests/
│   ├── domain/       # Pure unit tests
│   ├── integration/  # ORM and HTTP gateway tests
│   └── e2e/          # Full path tests
└── config/           # Django settings
```

---

## Phase 2: Domain Layer (Core Business Logic)

### 2.1 Entities
- [ ] Implement `Subscription` entity (event_type, target_url, active, secret, tenant_id)
- [ ] Implement `WebhookEvent` entity (event_id, event_type, payload, timestamp, tenant_id)
- [ ] Implement `DeliveryAttempt` entity (event_id, subscription_id, status, response_code, timestamp)

### 2.2 Domain Services
- [ ] Implement wildcard matching logic (e.g., `po.*` matches `po.created`)
- [ ] Implement HMAC-SHA256 signature generation
- [ ] Implement retry policy with exponential backoff + jitter
- [ ] Implement idempotency check logic

### 2.3 Interfaces (Abstract Base Classes)
- [ ] Define `SubscriptionRepository` protocol
- [ ] Define `EventRepository` protocol
- [ ] Define `DeliveryAttemptRepository` protocol
- [ ] Define `HttpGateway` protocol for outgoing requests

---

## Phase 3: Data Layer (Infrastructure)

### 3.1 Django Models
- [ ] Create `Tenant` model (organization, api_keys)
- [ ] Create `Subscription` model with tenant FK
- [ ] Create `WebhookEvent` model with tenant FK
- [ ] Create `DeliveryAttempt` model with event and subscription FKs
- [ ] Write migrations for all models

### 3.2 Repository Implementations
- [ ] Implement `DjangoSubscriptionRepository`
- [ ] Implement `DjangoEventRepository`
- [ ] Implement `DjangoDeliveryAttemptRepository`
- [ ] Ensure tenant isolation at repository level

### 3.3 HTTP Gateway
- [ ] Implement `httpx` based HTTP client
- [ ] Add timeout and retry handling
- [ ] Add response logging/truncation

---

## Phase 4: Interface Layer (API & Workers)

### 4.1 Subscription Management API
- [ ] `POST /subscriptions/` - Create subscription
- [ ] `GET /subscriptions/` - List subscriptions
- [ ] `GET /subscriptions/{id}/` - Retrieve detail
- [ ] `PATCH /subscriptions/{id}/` - Activate/Deactivate
- [ ] `DELETE /subscriptions/{id}/` - Remove subscription

### 4.2 Event Ingestion API
- [ ] `POST /events/` - Ingest events (persist first, then queue)
- [ ] Implement idempotency handling

### 4.3 Celery Tasks
- [ ] Implement fan-out task (atomic matching)
- [ ] Implement delivery task with retry logic
- [ ] Implement dead-letter handling

---

## Phase 5: Security & Authentication

### 5.1 API Key Authentication
- [ ] Implement API key model and management
- [ ] Create authentication middleware
- [ ] Derive tenant from authenticated principal

### 5.2 Secret Management
- [ ] Auto-generate subscription secrets
- [ ] Store secrets securely (hashed/encrypted)
- [ ] Show secret only on creation

### 5.3 Request Signing
- [ ] Add `X-Signature` header (HMAC-SHA256)
- [ ] Include timestamp in signature

---

## Phase 6: Testing

### 6.1 Domain Tests (Unit)
- [ ] Test wildcard matching logic
- [ ] Test retry policy calculations
- [ ] Test HMAC signature generation
- [ ] Test idempotency logic

### 6.2 Infrastructure Tests
- [ ] Test ORM repositories (CRUD + tenant isolation)
- [ ] Test HTTP gateway (timeout, response handling)

### 6.3 End-to-End Tests
- [ ] Test full ingestion → fan-out → delivery path
- [ ] Test concurrent worker safety
- [ ] Test tenant isolation
- [ ] Test wildcard matching in integration

---

## Phase 7: Deployment & Operations

### 7.1 Configuration
- [ ] Environment-based settings
- [ ] Celery configuration
- [ ] Database connection pooling

### 7.2 Monitoring
- [ ] Health check endpoint
- [ ] Metrics for delivery success/failure rates
- [ ] Logging structure

---

## Implementation Order

| Step | Component | Priority |
|------|-----------|----------|
| 1 | Project setup & structure | High |
| 2 | Domain entities & interfaces | High |
| 3 | Django models & migrations | High |
| 4 | Repository implementations | High |
| 5 | Subscription API endpoints | High |
| 6 | Event ingestion API | High |
| 7 | Celery tasks (fan-out & delivery) | High |
| 8 | Security (auth, signing) | Medium |
| 9 | Domain unit tests | Medium |
| 10 | Integration & E2E tests | Medium |
| 11 | Deployment configuration | Low |

---

## Notes

- Domain layer must have **zero** Django/ORM imports
- Views should remain "thin" - delegate to domain use cases
- Tenant isolation enforced at repository level, not just view level
- One slow target should not affect other deliveries (use Celery tasks per delivery)