# Assignment Checklist

## Core Deliverables

- [x] Clean architecture with inward dependency flow
- [x] Pure Python domain layer with zero Django imports
- [x] Tenant-scoped subscription management API
- [x] Durable event ingestion with idempotency protection
- [x] Atomic event plus outbox persistence
- [x] Wildcard subscription matching
- [x] Replay-safe fan-out with one delivery row per event/subscription
- [x] Delivery worker with signed requests, attempt tracking, and strict timeouts
- [x] Exponential backoff with jitter
- [x] Tenant-scoped API key authentication
- [x] Repository-level tenant isolation
- [x] Secret generation with one-time reveal and encrypted storage
- [x] Domain, integration, and end-to-end tests
- [x] `docker-compose.yml`
- [x] `README.md`
- [x] `DESIGN.md`

## Optional / Nice-to-Haves

- [x] Django admin for operational inspection
- [x] Metrics endpoint
- [x] `GET /deliveries/` listing endpoint
- [ ] `POST /deliveries/{id}/retry` manual retry endpoint
- [ ] Circuit breaker per target URL

## Follow-Up Notes

- Delivery isolation is good for this scope through queue bucketing and rate
  limiting, but it is not yet a full per-target fairness or circuit-breaker
  design.
- The runtime API now covers ingestion, subscriptions, health, metrics, and
  delivery visibility. Manual replay remains a backlog item.
