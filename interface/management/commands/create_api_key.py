"""Create a tenant API key from the command line."""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from data.repositories import DjangoTenantAPIKeyRepository
from interface.use_cases import IssueTenantAPIKey


class Command(BaseCommand):
    help = "Create a tenant API key and print the raw token once."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", required=True, help="Tenant UUID")
        parser.add_argument("--name", required=True, help="Human-friendly API key name")
        parser.add_argument(
            "--expires-at",
            required=False,
            help="Optional ISO-8601 expiry timestamp",
        )

    def handle(self, *args, **options):
        expires_at = self._parse_expires_at(options.get("expires_at"))
        try:
            issued_key = IssueTenantAPIKey(DjangoTenantAPIKeyRepository())(
                tenant_id=options["tenant_id"],
                name=options["name"],
                expires_at=expires_at,
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write("Tenant ID: {tenant_id}".format(tenant_id=issued_key.tenant_id))
        self.stdout.write("Name: {name}".format(name=issued_key.name))
        self.stdout.write("Prefix: {prefix}".format(prefix=issued_key.key_prefix))
        self.stdout.write("API Key: {raw_key}".format(raw_key=issued_key.raw_key))

    @staticmethod
    def _parse_expires_at(raw_value):
        if not raw_value:
            return None

        parsed_value = parse_datetime(raw_value)
        if parsed_value is None:
            raise CommandError("expires-at must be a valid ISO-8601 datetime")
        if timezone.is_naive(parsed_value):
            parsed_value = timezone.make_aware(
                parsed_value,
                timezone.get_current_timezone(),
            )
        return parsed_value
