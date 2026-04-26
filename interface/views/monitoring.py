"""Monitoring and operational visibility endpoints."""

from rest_framework import status
from rest_framework.permissions import AllowAny

from data.monitoring import ServiceHealthService, TenantMetricsService
from interface.responses import success_response
from interface.serializers import HealthCheckResponseSerializer, TenantMetricsResponseSerializer
from interface.views.base import ThinAPIView


class HealthCheckView(ThinAPIView):
    """Return a lightweight service health snapshot."""

    authentication_classes = []
    permission_classes = [AllowAny]
    health_service_class = ServiceHealthService

    def get(self, request):
        snapshot = self.health_service_class().snapshot()
        serializer = HealthCheckResponseSerializer(snapshot)
        status_code = (
            status.HTTP_200_OK
            if snapshot["status"] == "ok"
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return success_response(serializer.data, status_code=status_code)


class TenantMetricsView(ThinAPIView):
    """Return tenant-scoped delivery and queue metrics."""

    metrics_service_class = TenantMetricsService

    def get(self, request):
        tenant_id = self.get_tenant_id()
        snapshot = self.metrics_service_class().snapshot(tenant_id)
        serializer = TenantMetricsResponseSerializer(snapshot)
        return success_response(serializer.data)
