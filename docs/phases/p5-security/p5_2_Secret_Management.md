# Phase 5.2 - Secret Management

Branch: `feature/p5-security-p5_2_Secret_Management`

## Objective

Store subscription signing secrets safely at rest while still making them available for outbound HMAC delivery when needed.

## Changes

- Added encrypted-at-rest storage for subscription signing secrets via `secret_encrypted`.
- Kept `secret_hash` as a one-way digest alongside encrypted storage.
- Added `DjangoSubscriptionSecretCipher` using Fernet-compatible encryption derived from a dedicated setting or Django `SECRET_KEY`.
- Updated subscription creation to persist raw secrets through the repository, return them only once on create, and exclude them from list/detail responses.
- Updated subscription reads so `get_by_id()` can supply the decrypted secret for delivery signing while collection reads continue to omit it.
- Added focused tests for secret round-tripping and updated subscription use-case tests for the new raw-secret issuance flow.
- Added `WEBHOOK_SECRET_ENCRYPTION_KEY` to configuration and `.env.example`.

## Architecture Notes

- The repository now owns persistence-specific secret handling: hashing, encryption, and selective decryption.
- `CreateSubscription` remains the one-time secret issuance path for API responses, but persistence no longer stores only a hash.
- Existing subscriptions created before this subphase will have empty `secret_encrypted` values and cannot participate in signed delivery until rotated or recreated.
- A dedicated encryption key is recommended in production. When unset, the cipher derives a stable key from Django `SECRET_KEY` so local development remains unblocked.

## Verification

- `python -m compileall domain data interface tests config`
- `.venv\Scripts\python -m pytest tests\domain\test_subscription_use_cases.py tests\integration\test_secret_management.py tests\domain\test_delivery_task_use_cases.py -q`
- `set USE_SQLITE=True && .venv\Scripts\python manage.py check`

## Deferred

- Secret rotation and legacy-subscription backfill workflows are not added in this subphase.
- ORM-backed repository migration tests remain deferred locally because the bundled SQLite library lacks JSON support required by current JSONField migrations.
