# Phase 4.2 - Subscription Management API

Branch: `feature/p4-interfacelayer-p4_2_Subscription_Management_API`

## Objective

Expose tenant-scoped subscription CRUD endpoints while keeping DRF views thin and ensuring subscription secrets are shown only once.

## Changes

- Added request/response serializers for subscription create, patch, and response payloads.
- Added subscription use cases for create, list, get, patch, and delete.
- Added `SubscriptionCollectionView` and `SubscriptionDetailView`.
- Wired `/api/subscriptions/` and `/api/subscriptions/{id}/`.
- Added one-time raw secret generation on create.
- Added SHA-256 hashing before subscription secret persistence.
- Added tests for use-case secret hashing and API response behavior.

## Architecture Notes

- Views derive `tenant_id` only from the authenticated principal via `PrincipalTenantMixin`.
- Request serializers reject body-provided `tenant_id`.
- `POST /subscriptions/` returns the raw generated secret once.
- `GET`, `PATCH`, and list responses use `Subscription.to_dict()` and never include secrets.
- Secret hashing will be strengthened in Phase 5.2 if encrypted/peppered storage is required.

## Verification

- `python -m compileall interface tests`
- Direct Python verification of subscription secret hashing and patch use-case behavior.
- Attempted `python manage.py check`; blocked because Django is not installed in the current local Python environment.

## Deferred

- Successful `python manage.py check` and runtime DRF/Django tests are deferred until Django and DRF are installed locally.
- API-key authentication is handled in Phase 5.1.
