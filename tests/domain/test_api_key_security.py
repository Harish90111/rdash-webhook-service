import pytest

from domain.services import generate_api_key, get_api_key_prefix, hash_api_key


def test_generate_api_key_uses_expected_scheme_and_prefix():
    raw_key = generate_api_key()

    assert raw_key.startswith("rdwh_")
    assert get_api_key_prefix(raw_key).startswith("rdwh_")


def test_hash_api_key_is_stable_for_same_input():
    raw_key = "rdwh_abcd123456_secret-value"

    assert hash_api_key(raw_key) == hash_api_key(raw_key)


def test_get_api_key_prefix_rejects_invalid_keys():
    with pytest.raises(ValueError, match="valid API key"):
        get_api_key_prefix("invalid-key")


def test_hash_api_key_requires_non_empty_key():
    with pytest.raises(ValueError, match="raw_key is required"):
        hash_api_key("  ")
