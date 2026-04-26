# Phase 4.4 - Celery Tasks

Branch: `feature/p4-interfacelayer-p4_4_Celery_Tasks`

## Objective

Add Celery task wrappers and testable task use cases for durable outbox dispatch, atomic fan-out, per-subscription delivery, retry scheduling, and dead-letter handling.

## Changes

- Added `dispatch_outbox_batch` task to lock pending outbox rows and enqueue fan-out tasks.
- Added `fanout_event` task to create idempotent delivery attempts for matching active subscriptions.
- Added `deliver_webhook` task to send signed webhook POSTs through the HTTP gateway.
- Added `FanOutEvent` and `DeliverWebhook` use cases for testable task behavior.
- Added deterministic delivery task IDs and stable tenant queue buckets.
- Added atomic delivery claiming so duplicate Celery messages cannot concurrently deliver the same attempt.
- Added retryable outbox release for transient broker publish failures and stale outbox lock recovery.
- Added Celery task routes, beat schedule, delivery rate limit annotation, outbox retry settings, and tenant queue bucket setting.
- Added focused tests for fan-out idempotency, delivery claiming, delivery success, retry scheduling, dead-lettering, queue naming, and signature header generation.

## Architecture Notes

- Ingestion remains durable through the outbox table. Celery publishing happens after commit via `dispatch_outbox_batch`.
- Fan-out creates at most one delivery attempt per event/subscription pair; reruns reuse existing attempts.
- Delivery tasks claim attempts with a database conditional update before sending. Terminal, in-progress, and future retry attempts are skipped.
- Failed non-2xx or transport responses use domain retry policy. Exhausted attempts move to `dead_letter`.
- Outbox dispatch failures are released back to pending with exponential backoff instead of being dropped after one broker failure.
- Tenant queue buckets reduce noisy-neighbor blast radius without requiring one worker queue per tenant.
- Full secret retrieval for production signing depends on Phase 5 secret management. The delivery use case requires a domain subscription with a signing secret available and will fail the attempt when it is missing.

## Verification

- `python -m compileall domain data interface tests config`
- Direct Python execution of all functions in `tests/domain/test_delivery_task_use_cases.py`

## Local Environment Gaps

- `python -m pytest tests/domain/test_delivery_task_use_cases.py` could not run because `pytest` is not installed locally.
- `python manage.py check` could not run because `django` is not installed locally.

## Deferred

- Successful Celery/Django runtime tests are deferred until local dependencies are installed.
- Encrypted/decrypted subscription signing secret retrieval is handled in Phase 5.2.
- End-to-end concurrent worker safety tests are handled in Phase 6.3.
