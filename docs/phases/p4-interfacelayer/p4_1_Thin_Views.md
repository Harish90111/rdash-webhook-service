# Phase 4.1 - Thin Views

Branch: `feature/p4-interfacelayer-p4_1_Thin_Views`

## Objective

Establish the DRF interface foundation so future HTTP endpoints translate requests into use-case calls without embedding business logic in views.

## Changes

- Added consistent success and error response envelopes.
- Added custom DRF exception handling for domain exceptions.
- Added `PrincipalTenantMixin` to resolve tenant identity from the authenticated principal only.
- Added `ThinAPIView` as a small base class for HTTP-to-use-case delegation.
- Added a minimal API root view for routing sanity checks.
- Wired `/api/` into the project URL configuration.
- Added integration tests for response envelopes, domain exception mapping, and principal tenant resolution.

## Architecture Notes

- Views must not derive tenant identity from request bodies, query strings, or path data.
- Domain exceptions stay framework-neutral; `interface.exceptions` performs HTTP mapping.
- `ThinAPIView.run_use_case()` is intentionally boring: it makes delegation explicit without becoming an application service container.
- Subscription management, event ingestion, and Celery task endpoints remain separate subphases.

## Verification

- `python -m compileall config interface tests`
- Attempted `python manage.py check`; blocked because Django is not installed in the current local Python environment.

## Deferred

- Successful `python manage.py check` and runtime DRF/Django tests are deferred until Django and DRF are installed locally.
- API-key authentication is handled in Phase 5.1.
- Subscription and event endpoint implementations are handled in Phase 4.2 and Phase 4.3.
