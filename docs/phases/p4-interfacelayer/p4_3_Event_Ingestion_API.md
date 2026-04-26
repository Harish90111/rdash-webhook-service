# Phase 4.3 - Event Ingestion API

Branch: `feature/p4-interfacelayer-p4_3_Event_Ingestion_API`

## Objective

Expose `POST /api/events/` as the durable ingestion path for producer submissions with tenant-scoped idempotency and outbox-backed fan-out intent.

## Changes

- Added event ingestion request/response serializers.
- Added `IngestEvent` use case.
- Added `EventIngestionView`.
- Wired `/api/events/`.
- Added tenant-scoped idempotency handling.
- Added fallback deterministic idempotency keys for producers that omit a key.
- Added atomic event + outbox persistence through `create_event_with_outbox()`.
- Added `DESIGN.md` ingestion justification.
- Added use-case and view tests.

## Architecture Notes

- Views derive `tenant_id` only from the authenticated principal.
- Request bodies that include `tenant_id` are rejected.
- New events return HTTP `201`; duplicate submissions return HTTP `200` with `meta.idempotent_replay=true`.
- The use case checks existing events before creating a new event/outbox pair, and handles duplicate races by re-reading the existing event.
- Broker publishing is intentionally deferred; ingestion persists durable intent first.

## Verification

- `python -m compileall interface tests`
- Direct Python verification of ingestion use-case idempotency behavior.
- Attempted `python manage.py check`; blocked because Django is not installed in the current local Python environment.

## Deferred

- Successful `python manage.py check` and runtime DRF/Django tests are deferred until Django and DRF are installed locally.
- Fan-out and delivery Celery tasks are handled in Phase 4.4.
