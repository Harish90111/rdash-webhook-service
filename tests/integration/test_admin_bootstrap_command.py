from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase


class EnsureAdminUserCommandTests(TestCase):
    def test_command_creates_admin_user_from_environment_defaults(self):
        stdout = StringIO()

        with patch.dict(
            "os.environ",
            {
                "DJANGO_SUPERUSER_BOOTSTRAP": "True",
                "DJANGO_SUPERUSER_USERNAME": "admin",
                "DJANGO_SUPERUSER_PASSWORD": "admin",
                "DJANGO_SUPERUSER_EMAIL": "admin@example.com",
            },
            clear=False,
        ):
            call_command("ensure_admin_user", stdout=stdout)

        user_model = get_user_model()
        user = user_model.objects.get(username="admin")
        assert user.is_superuser
        assert user.is_staff
        assert user.is_active
        assert user.email == "admin@example.com"
        assert user.check_password("admin")
        assert "Created admin user 'admin'" in stdout.getvalue()

    def test_command_updates_existing_user_idempotently(self):
        user_model = get_user_model()
        user_model.objects.create_user(
            username="admin",
            email="legacy@example.com",
            password="legacy-password",
        )
        stdout = StringIO()

        with patch.dict(
            "os.environ",
            {
                "DJANGO_SUPERUSER_BOOTSTRAP": "True",
                "DJANGO_SUPERUSER_USERNAME": "admin",
                "DJANGO_SUPERUSER_PASSWORD": "admin",
                "DJANGO_SUPERUSER_EMAIL": "admin@example.com",
            },
            clear=False,
        ):
            call_command("ensure_admin_user", stdout=stdout)

        user = user_model.objects.get(username="admin")
        assert user.is_superuser
        assert user.is_staff
        assert user.is_active
        assert user.email == "admin@example.com"
        assert user.check_password("admin")
        assert "Updated admin user 'admin' fields:" in stdout.getvalue()
