from importlib.util import find_spec

from django.test import TestCase
from rest_framework.test import APIClient


class APIDocumentationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_schema_and_docs_endpoints_render_when_spectacular_is_installed(self):
        if find_spec("drf_spectacular") is None:
            self.skipTest("drf-spectacular is not installed")

        schema_response = self.client.get("/api/schema/")
        docs_response = self.client.get("/api/docs/")

        assert schema_response.status_code == 200
        assert docs_response.status_code == 200
        assert "openapi" in schema_response.content.decode("utf-8")
        assert "SwaggerUIBundle" in docs_response.content.decode("utf-8")
