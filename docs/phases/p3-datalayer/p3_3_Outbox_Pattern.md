# Phase 3.3 - Outbox Pattern

Branch: `feature/p3-datalayer-p3_3_Outbox_Pattern`

## Objective

Guarantee that event ingestion can commit the event and durable fan-out intent in the database before any broker publish is attempted.

## Changes

- Added `OutboxMessage` and `OutboxStatus` ORM models.
- Added migration `0002_outbox_message`.
- Added `DjangoOutboxRepository` for creating, listing, locking, publishing, and failing outbox rows.
- Added `create_event_with_outbox()` to persist a `WebhookEvent` and its fan-out task intent in one `transaction.atomic()` block.
- Added integration tests covering atomic event/outbox creation, duplicate task protection, state transitions, and pending batch locking.

## Architecture Notes

- Redis/Celery is no longer the source of durability for ingestion. The database commits the event and a pending outbox row first.
- `uniq_outbox_event_task` prevents duplicate fan-out intent for the same event/task pair.
- `lock_pending_batch()` uses `select_for_update(skip_locked=True)` so multiple dispatchers can work concurrently without processing the same pending row.
- Outbox rows include tenant IDs for operational filtering and tenant-aware updates.
- Broker publishing itself remains deferred to Celery/interface tasks; this subphase establishes durable state only.

## Verification

- `python -m compileall data tests`
- Attempted `python manage.py check`; blocked because Django is not installed in the current local Python environment.

## Deferred

- Successful `python manage.py check` and Django integration test execution are deferred until Django is installed locally.
- The outbox dispatcher task is handled in the interface/Celery phase.
