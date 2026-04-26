# Phase 5.3 - Request Signing

Branch: `feature/p5-security-p5_3_Request_Signing`

## Objective

Standardize outbound webhook request signing so every delivery uses the same versioned header contract and `{timestamp}.{body}` HMAC payload.

## Changes

- Added canonical signing header constants for timestamp, signature, and signature version.
- Added `build_signature_headers()` and `verify_signature_headers()` to the pure domain signing service.
- Standardized outbound delivery requests to use the shared signing helper instead of hand-building headers inside the delivery use case.
- Added explicit signature-version header emission with `v1`.
- Expanded domain tests to cover the header contract and delivery-task tests to verify the generated request headers end to end.

## Architecture Notes

- The webhook signature still uses HMAC-SHA256 over `{timestamp}.{body}`.
- Header construction now lives in one reusable domain service so delivery code and verification code cannot drift.
- `X-Signature-Version: v1` makes the contract evolvable without guessing which signature format a receiver is validating.
- This subphase standardizes the outbound signing envelope; replay-window enforcement remains a consumer-side or future platform concern.

## Verification

- `python -m compileall domain data interface tests config`
- `.venv\Scripts\python -m pytest tests\domain\test_signing.py tests\domain\test_delivery_task_use_cases.py -q`
- `set USE_SQLITE=True && .venv\Scripts\python manage.py check`

## Deferred

- Signature replay-window validation is not enforced in this subphase.
- HTTP gateway integration tests remain separate from the pure signing tests.
