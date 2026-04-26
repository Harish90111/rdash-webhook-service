"""Serializers for event ingestion endpoints."""

from rest_framework import serializers


class EventIngestSerializer(serializers.Serializer):
    """Validate event ingestion requests."""

    event_type = serializers.CharField(max_length=255, trim_whitespace=True)
    payload = serializers.DictField()
    idempotency_key = serializers.CharField(
        max_length=255,
        trim_whitespace=True,
        required=False,
        allow_blank=True,
    )

    def validate(self, attrs):
        if "tenant_id" in self.initial_data:
            raise serializers.ValidationError("tenant_id must come from authentication.")
        return attrs


class EventResponseSerializer(serializers.Serializer):
    """Serialize ingested event responses."""

    id = serializers.CharField()
    tenant_id = serializers.CharField()
    event_type = serializers.CharField()
    payload = serializers.DictField()
    idempotency_key = serializers.CharField(allow_null=True, required=False)
    timestamp = serializers.CharField(allow_null=True)
    processed = serializers.BooleanField()
