# Design Notes

## Event Ingestion

Event ingestion uses an HTTP API endpoint backed by a database outbox pattern.

The ingestion endpoint derives tenant identity from the authenticated principal and accepts only event data from the request body. Producers may send an `idempotency_key`; if they do not, the service builds a deterministic tenant-scoped key from `tenant_id`, `event_type`, and canonical payload content.

The write path is:

1. Check for an existing event by tenant-scoped idempotency key.
2. If an event already exists, return it as an idempotent replay and do not create another outbox row.
3. If it does not exist, persist the event and pending fan-out outbox message inside one database transaction.
4. Return the persisted event immediately. A dispatcher/Celery workflow can publish pending outbox rows after commit.

This gives producers at-least-once submission safety without causing duplicate fan-out deliveries for the same idempotency key. Redis/Celery is intentionally not part of the ingestion transaction; broker downtime leaves durable pending outbox rows in PostgreSQL instead of losing events.

The event body never supplies tenant identity. Tenant isolation is enforced by the principal, event repository lookups, and outbox rows scoped to the same tenant.
