# Phase 2.1 - Entities

Branch: `feature/p2-domainlayer-p2_1_Entities`

## Objective

Define the framework-neutral domain entities that represent subscriptions, inbound events, and delivery attempts.

## Changes

- Added `Subscription`, `WebhookEvent`, and `DeliveryAttempt` entities.
- Added `DeliveryStatus` values for worker state transitions.
- Added timezone-aware UTC timestamps for all domain-created times.
- Added required-field validation and URL scheme validation for subscriptions.
- Added defensive payload copying for webhook events so caller mutation cannot alter the domain object after construction.
- Added delivery response truncation, retry state transitions, terminal-state checks, and attempt-number validation.
- Added focused entity tests.

## Architecture Notes

- Entities import only Python standard-library modules and remain portable outside Django.
- `Subscription.to_dict()` excludes secrets by default; `to_dict_with_secret()` is explicit for the create-response path.
- Delivery attempts model workflow state, while tenant scoping remains enforced by repositories because attempts link through events/subscriptions.
- Response bodies are capped at `MAX_RESPONSE_BODY_LENGTH` to keep persisted delivery logs bounded.

## Verification

- `python -m compileall domain tests`
- Direct Python verification of entity validation, serialization, state transitions, and banned framework imports.

## Deferred

- Persistent Django models are handled in Phase 3.1.
- Secret hashing/encryption is handled in Phase 5.2.
