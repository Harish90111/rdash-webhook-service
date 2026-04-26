# Phase 7.2 - Monitoring

Branch: `feature/p7-deployment-p7_2_Monitoring`

## Objective

Add an operational monitoring surface that helps both platform operators and tenant integrators understand service health, delivery posture, and queue state without digging through raw database tables or ad hoc logs.

## Changes

- Added a public health endpoint at `/api/health/` with database readiness and broker-configuration checks.
- Added a tenant-authenticated metrics endpoint at `/api/metrics/` that reports:
  - subscription totals and active counts
  - event receive/process backlog
  - delivery counts by status
  - delivery success/failure rates based on terminal outcomes
  - outbox counts and backlog depth
- Added monitoring serializers and views so the new endpoints stay consistent with the existing thin-view response shape.
- Added a structured JSON formatter in `config/logging.py`.
- Switched the rotating file handler to structured JSON output while keeping console logs human-readable.
- Standardized task and HTTP gateway logs with explicit `event` and `component` fields so operational logs have a stable schema.
- Expanded integration coverage for:
  - public health access
  - degraded health responses
  - tenant-scoped metrics visibility
  - metrics authentication requirements
  - structured JSON log formatting

## Architecture Notes

- The health endpoint is intentionally lightweight: it checks database readiness directly and broker presence through configuration so it remains safe to call frequently.
- The metrics endpoint is tenant-scoped and uses the existing principal-based API-key authentication, which avoids exposing global platform internals to one tenant.
- Delivery success and failure rates are calculated from terminal delivery outcomes (`success` and `dead_letter`) rather than transient retry states.
- Structured file logs now preserve event metadata under a stable JSON envelope, making log aggregation and alerting easier to build later.

## Verification

- `.venv\Scripts\python -m pytest tests\integration\test_monitoring_api.py -q`
- `.venv\Scripts\python -m pytest tests\integration tests\e2e -q`
- `.venv\Scripts\python manage.py check` with `USE_SQLITE=True`
- `python -m compileall config data interface tests`

## Deferred

- Broker connectivity is currently validated as a configuration check rather than a live Redis ping.
- Long-window rate analytics and time-series export remain future operational enhancements outside this subphase.
