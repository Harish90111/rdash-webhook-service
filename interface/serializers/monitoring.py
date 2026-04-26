"""Serializers for monitoring endpoints."""

from rest_framework import serializers


class HealthCheckResponseSerializer(serializers.Serializer):
    """Serialize service health snapshots."""

    service = serializers.CharField()
    version = serializers.CharField()
    environment = serializers.CharField()
    status = serializers.CharField()
    timestamp = serializers.CharField()
    checks = serializers.DictField()


class TenantMetricsResponseSerializer(serializers.Serializer):
    """Serialize tenant-scoped operational metrics."""

    tenant_id = serializers.CharField()
    captured_at = serializers.CharField()
    subscriptions = serializers.DictField()
    events = serializers.DictField()
    deliveries = serializers.DictField()
    outbox = serializers.DictField()
