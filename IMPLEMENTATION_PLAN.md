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

### 1.2 Docker Compose Setup
- [ ] Create `docker-compose.yml` with separate services:
  - **Web**: Django application
  - **Worker**: Celery workers (isolated from web server)
  - **Redis**: Celery broker
  - **PostgreSQL**: Database
- [ ] Ensure worker environment is isolated from web server
- [ ] Configure networking between services

### 1.3 Project Structure (Clean Architecture)
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

## Phase 2: Domain Layer (The "Brain") ⚠️ CRITICAL

> **Zero-Django Rule**: This phase must have **zero** imports from Django, the ORM, or httpx. The folder must be copy-pasteable into a FastAPI project and run without changes.

### 2.1 Entities (Pure Python)
- [ ] Implement `Subscription` entity (event_type, target_url, active, secret, tenant_id)
- [ ] Implement `WebhookEvent` entity (event_id, event_type, payload, timestamp, tenant_id)
- [ ] Implement `DeliveryAttempt` entity (event_id, subscription_id, status, response_code, timestamp)

### 2.2 Domain Services (Pure Python)
- [ ] **Wildcard Matching**: Implement logic to match `po.*` against `po.created` or `po.approved`
  ```python
  # Example: pattern "po.*" should match "po.created", "po.approved"
  def matches_wildcard(event_type: str, pattern: str) -> bool:
      # Pure Python implementation
  ```
- [ ] **Retry Policy**: Implement exponential backoff with jitter
  ```python
  # Example: Calculate next retry delay
  def calculate_retry_delay(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
      # Exponential backoff with jitter
  ```
- [ ] **HMAC-SHA256 Signing**: Code signature generation
  ```python
  # Example: sha256=HMAC over {timestamp}.{body}
  def generate_signature(secret: str, timestamp: str, body: str) -> str:
      # Pure Python implementation using hmac and hashlib
  ```
- [ ] **Idempotency Check**: Implement duplicate detection logic

### 2.3 Interfaces (Abstract Base Classes / Protocols)
- [ ] Define `SubscriptionRepository` protocol
- [ ] Define `EventRepository` protocol
- [ ] Define `DeliveryAttemptRepository` protocol
- [ ] Define `HttpGateway` protocol for outgoing requests

### 2.4 Domain Exceptions
- [ ] Define custom exceptions (e.g., `SubscriptionNotFoundError`, `DeliveryFailedError`)

---

## Phase 3: Data Layer (The "Muscle")

### 3.1 Django Models
- [ ] Create `Tenant` model (organization, api_keys)
- [ ] Create `Subscription` model with tenant FK
- [ ] Create `WebhookEvent` model with tenant FK
- [ ] Create `DeliveryAttempt` model with event and subscription FKs
- [ ] Write migrations for all models

### 3.2 Repository Implementations (Implements Domain Interfaces)
- [ ] Implement `DjangoSubscriptionRepository`
- [ ] Implement `DjangoEventRepository`
- [ ] Implement `DjangoDeliveryAttemptRepository`
- [ ] **Tenant Isolation**: Hardcode Organization scoping into repository methods
  ```python
  # Example: Always filter by tenant_id
  def get_by_id(self, subscription_id: str, tenant_id: str) -> Subscription:
      return self.model.objects.get(id=subscription_id, tenant_id=tenant_id)
  ```

### 3.3 The Outbox Pattern
- [ ] Implement outbox table for reliable event delivery
- [ ] Ensure producers can commit events without losing them if broker is down
- [ ] Use database transaction for event + outbox entry

### 3.4 HTTP Gateway
- [ ] Implement `httpx` based HTTP client
- [ ] **Strict timeout configuration** (critical for event-driven systems):
  - `connect_timeout`: 5-10 seconds max
  - `read_timeout`: 10-30 seconds max
  - **Never use infinite timeouts** - a "hanging" request is more dangerous than a "failed" one because it ties up worker threads
- [ ] Add retry handling
- [ ] Add response logging/truncation

---

## Phase 4: Interface Layer (The "Skin")

### 4.1 Thin Views (DRF)
- [ ] Keep views strictly for translating HTTP → use-cases
- [ ] Views should NOT contain business logic

### 4.2 Subscription Management API
- [ ] `POST /subscriptions/` - Create subscription (return secret **once**)
- [ ] `GET /subscriptions/` - List subscriptions
- [ ] `GET /subscriptions/{id}/` - Retrieve detail (secret **NOT** included)
- [ ] `PATCH /subscriptions/{id}/` - Activate/Deactivate (secret **NOT** included)
- [ ] `DELETE /subscriptions/{id}/` - Remove subscription

### 4.3 Event Ingestion API ⚠️ CRITICAL PATH
- [ ] `POST /events/` - Ingest events
  - **Persist first, then queue** (at-least-once guarantee)

  git br
  - Implement idempotency handling for duplicate submissions
- [ ] Justify ingestion mechanism in DESIGN.md

### 4.4 Celery Tasks (Fan-Out & Delivery)
- [ ] **Atomic Fan-Out**: Design task so crash mid-way doesn't cause duplicate deliveries
  - Use database state to track processed events
  - Implement idempotency keys
- [ ] **Delivery Task**: Per-subscription delivery with retry logic
  - Use httpx client with **strict timeouts** (connect: 5-10s, read: 10-30s)
  - Never use infinite timeouts - hanging requests tie up worker threads
- [ ] **Dead-Letter Handling**: Failed deliveries after max retries
- [ ] **Noisy Neighbor Protection**: Configure worker to prevent one tenant from starving others
  - Use separate queues per tenant or priority-based routing
  - Set task rate limits

---

## Phase 5: Security & Authentication

### 5.1 Principal-Based Authentication
- [ ] Implement API key model and management
- [ ] Create authentication middleware
- [ ] **Derive tenant identity from API key, never from request body**
  ```python
  # Example: Tenant comes from authenticated principal
  tenant = request.user.tenant  # NOT from request.data['tenant_id']
  ```

### 5.2 Secret Management
- [ ] Auto-generate subscription secrets on creation
- [ ] **Store secrets hashed or encrypted in DB** (not plain text)
- [ ] Show secret **only once** upon creation in response
- [ ] Never return secret in GET or PATCH responses

### 5.3 Request Signing
- [ ] Add `X-Signature` header (HMAC-SHA256)
- [ ] Include timestamp in signature: `{timestamp}.{body}`

---

## Phase 6: Testing Strategy

### 6.1 Domain Tests (Unit - Millisecond Fast)
- [ ] Test wildcard matching logic (`po.*` matches `po.created`)
- [ ] Test retry policy calculations (exponential backoff + jitter)
- [ ] Test HMAC signature generation
- [ ] Test idempotency logic

### 6.2 Infrastructure Tests (Integration)
- [ ] Test ORM repositories (CRUD + tenant isolation)
- [ ] Test HTTP gateway (timeout, response handling)

### 6.3 End-to-End Tests
- [ ] Test full ingestion → fan-out → delivery path
- [ ] **Test fan-out idempotency** (crash mid-way, restart shouldn't duplicate)
- **Test concurrent worker safety** (prevent double-processing)
- [ ] Test tenant isolation
- [ ] Test wildcard matching in integration

---

## Phase 7: Deployment & Operations

### 7.1 Configuration
- [ ] Environment-based settings
- [ ] Celery configuration with proper concurrency
- [ ] Database connection pooling

### 7.2 Monitoring
- [ ] Health check endpoint
- [ ] Metrics for delivery success/failure rates
- [ ] Logging structure

---

## Implementation Order

| Step | Component | Priority | Notes |
|------|-----------|----------|-------|
| 1 | Project setup + Docker Compose | High | Separate Redis/worker isolation |
| 2 | Domain entities & interfaces | High | **Zero Django imports** |
| 3 | Domain services (wildcard, retry, signing) | High | Pure Python, copy to FastAPI |
| 4 | Django models & migrations | High | |
| 5 | Repository implementations + tenant isolation | High | Hardcode tenant scoping |
| 6 | Outbox pattern implementation | High | Ensure no event loss |
| 7 | Subscription API endpoints | High | Secret shown once |
| 8 | Event ingestion API | High | Persist first, then queue |
| 9 | Celery tasks (fan-out + delivery) | High | Atomic, idempotent |
| 10 | Worker isolation (noisy neighbors) | High | Per-tenant queues/rate limits |
| 11 | Security (auth, signing, secret storage) | Medium | |
| 12 | Domain unit tests | Medium | Millisecond-fast |
| 13 | Integration & E2E tests | Medium | Concurrent worker safety |
| 14 | Deployment configuration | Low | |

---

## ⚠️ Elias's Critical Path Warnings

### Ingestion Invalidation
- Justify ingestion mechanism in DESIGN.md
- If simple API endpoint: how to handle "at-least-once" producers without duplicate deliveries?
- **Solution**: Implement idempotency keys and outbox pattern

### Noisy Neighbors
- Configure workers so one tenant with thousands of failing endpoints doesn't starve others
- **Solution**: Per-tenant queues or priority-based routing with rate limits

### The "Zero-Django" Rule
- Phase 2 folder must be copy-pasteable into FastAPI project
- Run without changing a single line of code
- **Verification**: No imports from `django`, `django.db`, `httpx`, etc.

---

## Key Principles Summary

| Principle | Implementation |
|-----------|----------------|
| **Zero-Django in Domain** | Pure Python, copyable to FastAPI |
| **Tenant Isolation** | Hardcoded in repositories, not just views |
| **At-Least-Once** | Persist first, then queue + idempotency keys |
| **Atomic Fan-Out** | Database state tracking + idempotency |
| **Secret Security** | Hash/encrypt, show once only |
| **Principal Auth** | Tenant from API key, never request body |
| **Noisy Neighbor Protection** | Per-tenant queues + rate limiting |