"""drf-spectacular integration for custom authentication and schema polish."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class APIKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    """Describe the tenant API key auth scheme in generated OpenAPI docs."""

    target_class = "interface.authentication.APIKeyAuthentication"
    name = "TenantApiKeyAuth"
    priority = 1

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": (
                "Tenant-scoped API key. Preferred header format: "
                "`X-API-Key: <raw-key>`. "
                "The runtime API also accepts `Authorization: Api-Key <raw-key>`."
            ),
        }
