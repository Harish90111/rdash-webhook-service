from domain.services.idempotency import (
    build_idempotency_key,
    is_duplicate_submission,
    normalize_idempotency_key,
)


def test_normalize_idempotency_key_strips_blank_values():
    assert normalize_idempotency_key("  abc  ") == "abc"
    assert normalize_idempotency_key("   ") is None
    assert normalize_idempotency_key(None) is None


def test_build_idempotency_key_is_stable_for_payload_key_order():
    left = build_idempotency_key("tenant-1", "po.created", {"b": 2, "a": 1})
    right = build_idempotency_key("tenant-1", "po.created", {"a": 1, "b": 2})

    assert left == right


def test_build_idempotency_key_changes_across_tenants():
    left = build_idempotency_key("tenant-1", "po.created", {"id": 42})
    right = build_idempotency_key("tenant-2", "po.created", {"id": 42})

    assert left != right


def test_is_duplicate_submission_uses_normalized_keys():
    existing_keys = ["first", " second "]

    assert is_duplicate_submission("second", existing_keys) is True
    assert is_duplicate_submission("missing", existing_keys) is False
    assert is_duplicate_submission(None, existing_keys) is False
