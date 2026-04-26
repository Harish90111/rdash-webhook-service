import hmac

from domain.services.signing import generate_signature, verify_signature


def test_generate_signature_uses_expected_prefix_and_digest_length():
    signature = generate_signature("secret", "1710000000", '{"ok":true}')

    assert signature.startswith("sha256=")
    assert len(signature) == len("sha256=") + 64


def test_generate_signature_matches_known_digest():
    signature = generate_signature("secret", "1710000000", '{"ok":true}')

    assert hmac.compare_digest(
        signature,
        "sha256=ebbb85d53a240b6568e6e3f9c851993b0a6f279362be8908dda3f9568189ebac",
    )


def test_verify_signature_accepts_valid_signature():
    signature = generate_signature("secret", "1710000000", b'{"ok":true}')

    assert verify_signature("secret", "1710000000", '{"ok":true}', signature) is True


def test_verify_signature_rejects_invalid_signature():
    assert verify_signature("secret", "1710000000", '{"ok":true}', "sha256=bad") is False
