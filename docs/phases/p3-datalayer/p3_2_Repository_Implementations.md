# Phase 3.2 - Repository Implementations

Branch: `feature/p3-datalayer-p3_2_Repository_Implementations`

## Objective

Implement Django ORM repositories for the domain persistence contracts with tenant isolation enforced inside the data layer.

## Changes

- Added `DjangoSubscriptionRepository`.
- Added `DjangoEventRepository`.
- Added `DjangoDeliveryAttemptRepository`.
- Exported repositories from `data.repositories`.
- Added integration tests for tenant isolation, duplicate event handling, processed-state updates, and delivery attempt persistence.

## Architecture Notes

- Repository methods filter by tenant IDs directly, so callers cannot rely on view-level scoping alone.
- Subscription reads do not return stored secret hashes as domain secrets. The create/update paths preserve the caller-provided secret value for the current use case only.
- Event creation translates tenant-scoped idempotency constraint violations into `DuplicateEventError`.
- Delivery attempts are tenant-scoped through both event and subscription joins to prevent cross-tenant delivery state access.
- Concrete repositories raise domain exceptions, keeping application use cases independent of Django exception types.

## Verification

- `python -m compileall data tests`
- Attempted `python manage.py check`; blocked because Django is not installed in the current local Python environment.

## Deferred

- Successful `python manage.py check` and Django integration test execution are deferred until Django is installed in the current local Python environment.
- Outbox persistence and transaction workflow are handled in Phase 3.3.
