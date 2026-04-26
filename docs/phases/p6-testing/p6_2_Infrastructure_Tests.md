# Phase 6.2 - Infrastructure Tests

Branch: `feature/p6-testing-p6_2_Infrastructure_Tests`

## Objective

Make the Django-backed integration suite runnable and trustworthy on a local developer machine, then expand the repository and HTTP gateway coverage to match the infrastructure that now exists in the application.

## Changes

- Added a SQLite compatibility hook in `data.models` that registers `JSON_VALID` for older local SQLite builds used by Windows Python distributions.
- Wired the compatibility registration through `DataModelsConfig.ready()` so Django migrations and pytest database setup both get the function before JSON-backed tables are created.
- Expanded repository integration tests to cover:
  - subscription create, update, delete, secret encryption, and tenant-scoped visibility
  - event lookup by idempotency key with tenant isolation
  - delivery-attempt claim semantics for first-delivery and due-retry paths
  - tenant API key issuance, authentication, and inactive/expired key rejection
- Expanded model integration coverage with a nested JSON payload round-trip assertion for `WebhookEvent`.
- Tightened HTTP gateway response handling by normalizing returned response headers to lowercase and added coverage for downstream retry-oriented headers.

## Architecture Notes

- The SQLite compatibility shim is intentionally narrow: it fills only the `JSON_VALID` gap required by Django's generated `JSONField` constraints and leaves PostgreSQL as the primary production database.
- Returning lowercase response-header keys from the HTTP gateway gives callers deterministic access to retry metadata after leaving `httpx`'s case-insensitive header container.
- Repository list operations continue to hide decrypted subscription secrets by default, while targeted reads remain able to reveal the raw secret for delivery signing.

## Verification

- `.venv\Scripts\python -m pytest tests\integration -q`
- `.venv\Scripts\python -m pytest -m integration -q`
- `.venv\Scripts\python manage.py check` with `USE_SQLITE=True`
- `python -m compileall domain data interface tests config`

## Deferred

- PostgreSQL-native integration runs are still the higher-fidelity deployment check and should remain part of CI or container-based validation.
- End-to-end ingestion, fan-out, and worker-concurrency coverage remains part of Phase 6.3.
