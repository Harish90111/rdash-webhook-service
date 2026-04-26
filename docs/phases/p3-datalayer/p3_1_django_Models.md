# Phase 3.1 - Django Models

Branch: `feature/p3-datalayer-p3_1_django_Models`

## Objective

Create the Django ORM schema foundation for tenants, subscriptions, persisted events, and delivery state while preserving Clean Architecture boundaries.

## Changes

- Added the `webhook_data` Django app label for the `data.models` app.
- Added ORM models for `Tenant`, `TenantAPIKey`, `Subscription`, `WebhookEvent`, and `DeliveryAttempt`.
- Added `DeliveryStatus` database choices aligned with the domain delivery statuses.
- Added tenant-scoped indexes and uniqueness constraints for subscription lookup, event idempotency, and delivery idempotency.
- Added an initial migration that creates the schema.
- Added integration tests for key model constraints.

## Architecture Notes

- Domain entities remain pure Python. These ORM models are infrastructure persistence concerns only.
- `TenantAPIKey` stores only `key_prefix` and `key_hash`; raw API key generation and verification remain deferred to the security phase.
- Event idempotency is enforced with a tenant-scoped partial unique constraint on non-null idempotency keys.
- Delivery state is unique per event/subscription pair to support atomic fan-out and prevent duplicate delivery rows.
- Outbox persistence is intentionally deferred to Phase 3.3.

## Verification

- `python -m compileall data tests`
- Attempted `python manage.py check`; blocked because Django is not installed in the current local Python environment.

## Deferred

- Successful `python manage.py check` and `python manage.py test tests.integration.test_django_models` are deferred until dependencies are installed.
- Repository implementations are handled in Phase 3.2.
- Outbox tables and transaction workflow are handled in Phase 3.3.
