# Phase 2.2 - Domain Services

Branch: `feature/p2-domainlayer-p2_2_domain_Services`

## Objective

Build the pure-Python business services required by the webhook delivery domain while preserving the Phase 2 zero-framework rule.

## Changes

- Added segment-aware wildcard matching for event subscription patterns.
- Added retry policy helpers for capped exponential backoff with bounded jitter.
- Added HMAC-SHA256 request signing and constant-time signature verification.
- Added idempotency key normalization, deterministic fallback key generation, and duplicate-submission checks.
- Exported domain services through `domain.services` for application-layer use.
- Added focused unit tests for wildcard matching, retry behavior, signing, and idempotency.

## Architecture Notes

- `po.*` intentionally matches `po.created` but not `po.created.v2`; callers must use `po.*.*` for three-segment events.
- Signatures are generated over `{timestamp}.{body}` and returned as `sha256=<digest>`, matching the planned webhook header contract.
- The fallback idempotency key is scoped by tenant, event type, and canonical JSON payload so identical payloads from different tenants never collide.
- The domain service package imports only standard-library modules and project-domain code.

## Verification

- `python -m compileall domain tests`
- Direct Python verification of wildcard matching, retry delays, signing, idempotency, and banned framework imports.

## Deferred

- Repository protocols are handled in Phase 2.3.
- Domain exceptions are handled in Phase 2.4.
- Full `pytest` execution is deferred until the local Python environment has `pytest` installed.
