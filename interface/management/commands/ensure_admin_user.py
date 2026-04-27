"""Ensure a development Django admin user exists."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from config.env import env_bool, env_str


class Command(BaseCommand):
    help = "Create or update the local Django admin user idempotently."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            required=False,
            help="Admin username override",
        )
        parser.add_argument(
            "--password",
            required=False,
            help="Admin password override",
        )
        parser.add_argument(
            "--email",
            required=False,
            help="Admin email override",
        )

    def handle(self, *args, **options):
        if not env_bool(
            "DJANGO_SUPERUSER_BOOTSTRAP",
            getattr(settings, "APP_ENV", "development") != "production",
        ):
            self.stdout.write("Skipping admin bootstrap because DJANGO_SUPERUSER_BOOTSTRAP is disabled.")
            return

        username = (options.get("username") or env_str("DJANGO_SUPERUSER_USERNAME", "admin")).strip()
        password = (options.get("password") or env_str("DJANGO_SUPERUSER_PASSWORD", "admin")).strip()
        email = (options.get("email") or env_str("DJANGO_SUPERUSER_EMAIL", "admin@example.com")).strip()

        if not username:
            raise CommandError("username is required")
        if not password:
            raise CommandError("password is required")
        if not email:
            raise CommandError("email is required")

        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        changes = []
        if user.email != email:
            user.email = email
            changes.append("email")
        if not user.is_staff:
            user.is_staff = True
            changes.append("is_staff")
        if not user.is_superuser:
            user.is_superuser = True
            changes.append("is_superuser")
        if not user.is_active:
            user.is_active = True
            changes.append("is_active")
        if not user.check_password(password):
            user.set_password(password)
            changes.append("password")

        if created or changes:
            user.save()

        if created:
            self.stdout.write(
                "Created admin user '{username}' with email '{email}'.".format(
                    username=username,
                    email=email,
                )
            )
            return

        if changes:
            self.stdout.write(
                "Updated admin user '{username}' fields: {changes}.".format(
                    username=username,
                    changes=", ".join(changes),
                )
            )
            return

        self.stdout.write(
            "Admin user '{username}' already matches the requested bootstrap state.".format(
                username=username,
            )
        )
