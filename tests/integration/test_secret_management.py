from django.test import SimpleTestCase, override_settings

from data.security import DjangoSubscriptionSecretCipher


@override_settings(
    SECRET_KEY="django-insecure-test-secret",
    WEBHOOK_SECRET_ENCRYPTION_KEY="subscription-encryption-key",
)
class SubscriptionSecretCipherTests(SimpleTestCase):
    def test_encrypt_and_decrypt_round_trip(self):
        cipher = DjangoSubscriptionSecretCipher()

        encrypted_secret = cipher.encrypt("plain-secret")

        assert encrypted_secret != "plain-secret"
        assert cipher.decrypt(encrypted_secret) == "plain-secret"

    def test_secret_key_fallback_works_when_dedicated_key_missing(self):
        with override_settings(WEBHOOK_SECRET_ENCRYPTION_KEY=""):
            cipher = DjangoSubscriptionSecretCipher()
            encrypted_secret = cipher.encrypt("plain-secret")
            assert cipher.decrypt(encrypted_secret) == "plain-secret"

    def test_encrypt_rejects_blank_secret(self):
        cipher = DjangoSubscriptionSecretCipher()

        with self.assertRaises(ValueError):
            cipher.encrypt(" ")
