# Phase 2.3 - Interfaces

Branch: `feature/p2-domainlayer-p2_3_Interfaces`

## Objective

Define the domain-owned contracts that the Django data layer and HTTP delivery infrastructure must implement.

## Changes

- Added repository protocols for subscriptions, events, and delivery attempts.
- Added an HTTP gateway protocol for outgoing webhook delivery.
- Added transport-agnostic `HttpRequest`, `HttpResponse`, and `HttpTimeouts` value objects.
- Made protocols runtime-checkable so tests and adapter wiring can validate contract shape without importing infrastructure.
- Made tenant scoping explicit in delivery-attempt repository methods to prevent accidental cross-tenant reads or updates.
- Added interface tests and a zero-framework import guard for the full domain layer.

## Architecture Notes

- The domain layer owns contracts, while Django ORM/httpx implementations will live under `data/`.
- Delivery attempts do not carry tenant IDs directly, so the repository contract requires tenant IDs on read/update methods and infrastructure must validate through event/subscription ownership.
- HTTP timeout configuration is split into connect and read values to support strict delivery timeouts later in the httpx gateway.
- Protocols are intentionally small. Application use cases can compose them without depending on Django models.

## Verification

- `python -m compileall domain tests`
- Direct Python verification of interface value objects, runtime-checkable protocols, and banned framework imports.

## Deferred

- Concrete Django repository implementations are handled in Phase 3.2.
- Concrete httpx delivery gateway is handled in Phase 3.4.
