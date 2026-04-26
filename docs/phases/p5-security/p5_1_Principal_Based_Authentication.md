# Phase 5.1 - Principal-Based Authentication

Branch: `feature/p5-security-p5_1_Principal_Based_Authentication`

## Objective

Introduce tenant-scoped API key authentication so interface-layer views derive tenant identity from the authenticated principal rather than request payloads.

## Changes

- Added pure API key helpers for generation, prefix extraction, and hashing.
- Added `DjangoTenantAPIKeyRepository` for key issuance and tenant-authentication lookups.
- Added `IssueTenantAPIKey` use case for one-time raw key creation.
- Added `interface.authentication.APIKeyAuthentication` and `APIKeyPrincipal` for DRF request authentication.
- Added `create_api_key` management command so operators can issue tenant API keys without waiting for an admin UI.
- Updated interface integration tests to use DRF `force_authenticate` where views are exercised in isolation.
- Added focused domain and integration tests for API key generation, authentication, expiry handling, and command-based issuance.

## Architecture Notes

- Tenant identity now comes from the authenticated principal attached by DRF authentication, not from request bodies.
- Raw API keys are shown only at issuance time. Persistence stores a SHA-256 hash plus a short display prefix.
- Authentication accepts either `X-API-Key` or `Authorization: Api-Key <token>`.
- Existing thin views continue to resolve tenant identity through `PrincipalTenantMixin`, so the authentication change stays orthogonal to use-case logic.
- This subphase establishes principal-based authentication. Dedicated key lifecycle APIs and stronger secret-rotation workflows can build on top of this in later security work.

## Verification

- `.venv\Scripts\python -m pytest tests/domain/test_api_key_security.py -q`
- `set USE_SQLITE=True && .venv\Scripts\python -m pytest --ds=config.settings tests/integration/test_api_key_authentication.py tests/integration/test_interface_foundation.py tests/integration/test_subscription_api.py tests/integration/test_event_ingestion_api.py -q`
- `set USE_SQLITE=True && .venv\Scripts\python manage.py check`

## Deferred

- API key CRUD endpoints and rotation workflows are not added in this subphase.
- Encrypted storage or external secret management for subscriber signing secrets remains part of later security subphases.
- ORM-backed repository tests remain deferred locally because the bundled SQLite library lacks JSON support required by current JSONField migrations.
