# Phase 6.1 - Domain Tests

Branch: `feature/p6-testing-p6_1_Domain_Tests`

## Objective

Make the pure test layer a first-class, runnable slice of the system and close the gaps that had opened between protocol changes and the domain test suite.

## Changes

- Added `pytest.ini` with explicit `domain`, `integration`, and `e2e` markers.
- Added root `conftest.py` to auto-mark tests by suite path, so `pytest -m domain` and later phase-specific runs stay ergonomic.
- Fixed the runtime-checkable repository protocol test after `DeliveryAttemptRepository` gained `claim_for_delivery`.
- Added entity tests for subscription secret rotation and delivery-attempt retry-window clearing.
- Documented the domain-test verification flow for the project.

## Architecture Notes

- Domain tests stay framework-light and continue to protect the zero-Django rule.
- Marker-based selection reduces friction between pure unit verification and Django-backed test runs.
- The protocol fix matters because `@runtime_checkable` protocols can silently drift from their fake implementations unless the suite exercises them directly.

## Verification

- `.venv\Scripts\python -m pytest tests/domain -q`
- `.venv\Scripts\python -m pytest -m domain -q`
- `python -m compileall tests`

## Deferred

- SQLite-backed ORM integration gaps caused by local JSON support remain outside this subphase.
- E2E workflow coverage remains part of later testing subphases.
