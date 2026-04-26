"""Small API root view for routing sanity checks."""

from rest_framework.permissions import AllowAny

from interface.responses import success_response
from interface.views.base import ThinAPIView


class APIRootView(ThinAPIView):
    """Return basic service metadata without embedding business logic."""

    permission_classes = [AllowAny]

    def get(self, request):
        return success_response(
            {
                "service": "rdash-webhook-service",
                "version": "v1",
                "endpoints": {
                    "health": "/api/health/",
                    "metrics": "/api/metrics/",
                    "deliveries": "/api/deliveries/",
                    "events": "/api/events/",
                    "subscriptions": "/api/subscriptions/",
                },
            }
        )
