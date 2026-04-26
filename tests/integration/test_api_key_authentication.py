from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from interface.authentication import APIKeyAuthentication
from interface.responses import success_response
from interface.views.base import ThinAPIView


class StubTenantAPIKeyRepository:
    authenticated_key = None

    def authenticate(self, raw_key):
        if raw_key == "rdwh_publicid_secret":
            return self.__class__.authenticated_key
        return None


class TestAPIKeyAuthentication(APIKeyAuthentication):
    repository_class = StubTenantAPIKeyRepository


class ProtectedTenantEchoView(ThinAPIView):
    """Small protected view used to verify authentication wiring."""

    authentication_classes = [TestAPIKeyAuthentication]

    def get(self, request):
        return success_response({"tenant_id": self.get_tenant_id()})


class APIKeyAuthenticationTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        StubTenantAPIKeyRepository.authenticated_key = SimpleNamespace(
            id="key-1",
            tenant_id="tenant-1",
            tenant_name="Acme",
            tenant_slug="acme",
            name="Primary",
            key_prefix="rdwh_publicid",
        )

    def test_api_key_authentication_accepts_x_api_key_header(self):
        request = self.factory.get(
            "/api/protected/",
            HTTP_X_API_KEY="rdwh_publicid_secret",
        )

        response = ProtectedTenantEchoView.as_view()(request)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["tenant_id"] == "tenant-1"

    def test_api_key_authentication_accepts_authorization_header(self):
        request = self.factory.get(
            "/api/protected/",
            HTTP_AUTHORIZATION="Api-Key rdwh_publicid_secret",
        )

        response = ProtectedTenantEchoView.as_view()(request)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["tenant_id"] == "tenant-1"

    def test_invalid_api_key_returns_unauthorized(self):
        request = self.factory.get(
            "/api/protected/",
            HTTP_X_API_KEY="rdwh_badprefix_secret",
        )

        response = ProtectedTenantEchoView.as_view()(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_malformed_authorization_header_returns_unauthorized(self):
        request = self.factory.get(
            "/api/protected/",
            HTTP_AUTHORIZATION="Api-Key",
        )

        response = ProtectedTenantEchoView.as_view()(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_api_key_command_prints_raw_key_once(self):
        issued_key = SimpleNamespace(
            tenant_id="tenant-1",
            name="Operations",
            key_prefix="rdwh_publicid",
            raw_key="rdwh_publicid_secret",
        )

        with patch(
            "interface.management.commands.create_api_key.IssueTenantAPIKey",
        ) as issue_use_case:
            issue_use_case.return_value.return_value = issued_key
            with patch(
                "interface.management.commands.create_api_key.DjangoTenantAPIKeyRepository",
                return_value=object(),
            ):
                with patch("sys.stdout") as _:
                    from io import StringIO

                    output = StringIO()
                    call_command(
                        "create_api_key",
                        tenant_id="tenant-1",
                        name="Operations",
                        stdout=output,
                    )

        command_output = output.getvalue()
        assert "API Key: rdwh_publicid_secret" in command_output
        assert "Prefix: rdwh_publicid" in command_output
