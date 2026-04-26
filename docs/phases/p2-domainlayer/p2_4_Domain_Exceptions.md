# Phase 2.4 - Domain Exceptions

Branch: `feature/p2-domainlayer-p2_4_Domain_Exceptions`

## Objective

Define a framework-neutral error hierarchy for the domain layer so interface and data adapters can translate business failures consistently.

## Changes

- Added `WebhookDomainError` as the base exception for all domain failures.
- Added stable `error_code` values for subscription, event, delivery, duplicate, and signature errors.
- Added `safe_message` defaults and optional contextual metadata.
- Added `to_dict()` for framework-neutral serialization by future API adapters.
- Added focused tests for inheritance, stable codes, context copying, and serializable payloads.

## Architecture Notes

- Domain exceptions do not import Django, DRF, httpx, Celery, or any infrastructure package.
- Context is copied at construction time so callers cannot mutate the error payload after raising.
- HTTP status mapping is intentionally deferred to the interface layer; the domain exposes semantic failures only.
- Stable error codes give logs, API responses, and retry handling a shared vocabulary without coupling layers.

## Verification

- `python -m compileall domain tests`
- Direct Python verification of exception serialization, hierarchy, stable codes, and banned framework imports.

## Deferred

- API exception-to-response translation will be handled in the interface layer.
- Repository implementations will raise these domain errors in Phase 3.2.
