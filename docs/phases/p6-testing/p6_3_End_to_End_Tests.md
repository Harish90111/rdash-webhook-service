# Phase 6.3 - End-to-End Tests

Branch: `feature/p6-testing-p6_3_End_to_End_Tests`

## Objective

Exercise the full webhook workflow from authenticated API ingress through durable outbox dispatch, fan-out, and delivery, while proving that replayed task messages do not break tenant isolation or double-deliver webhooks.

## Changes

- Added a new end-to-end suite in `tests/e2e/test_webhook_delivery_flow.py`.
- Used real DRF API requests with actual tenant API-key authentication for subscription creation and event ingestion.
- Added a synchronous Celery scheduling recorder so the suite can observe queued fan-out and delivery messages without requiring a live Redis broker.
- Added a recording HTTP gateway stub to assert the final outbound request contract produced by delivery tasks.
- Covered the following workflow cases:
  - full ingestion -> outbox -> fan-out -> delivery success path
  - wildcard subscription matching in the end-to-end path
  - fan-out replay after a simulated crash without duplicate delivery-attempt rows
  - duplicate delivery messages being claimed only once
  - tenant isolation across subscriptions, events, outbox rows, and deliveries

## Architecture Notes

- The tests drive the real interface and data layers, then drain the asynchronous edges synchronously by patching task scheduling points instead of mocking out the workflow internals.
- Replay safety is enforced in two places: fan-out reuses existing delivery-attempt rows, and delivery workers atomically claim attempts before sending HTTP requests.
- The suite intentionally validates multi-tenant boundaries at the workflow level, not only at repository level, so regressions in view/auth/task wiring show up quickly.

## Verification

- `.venv\Scripts\python -m pytest tests\e2e\test_webhook_delivery_flow.py -q`
- `.venv\Scripts\python -m pytest -m e2e -q`
- `.venv\Scripts\python -m pytest tests\integration tests\e2e -q`
- `.venv\Scripts\python manage.py check` with `USE_SQLITE=True`
- `python -m compileall domain data interface tests config`

## Deferred

- Real broker-backed Celery worker concurrency in Docker or CI remains a useful higher-fidelity operational test beyond this local synchronous harness.
- PostgreSQL-native end-to-end execution remains the preferred deployment-adjacent validation path.
