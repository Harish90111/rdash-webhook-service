"""Serializers for subscription management endpoints."""

from rest_framework import serializers


class SubscriptionCreateSerializer(serializers.Serializer):
    """Validate create-subscription requests."""

    event_type = serializers.CharField(max_length=255, trim_whitespace=True)
    target_url = serializers.URLField(max_length=2048)
    active = serializers.BooleanField(default=True, required=False)

    def validate(self, attrs):
        if "tenant_id" in self.initial_data:
            raise serializers.ValidationError("tenant_id must come from authentication.")
        return attrs


class SubscriptionPatchSerializer(serializers.Serializer):
    """Validate partial subscription updates."""

    event_type = serializers.CharField(max_length=255, trim_whitespace=True, required=False)
    target_url = serializers.URLField(max_length=2048, required=False)
    active = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if "tenant_id" in self.initial_data:
            raise serializers.ValidationError("tenant_id must come from authentication.")
        if not attrs:
            raise serializers.ValidationError("At least one field must be provided.")
        return attrs


class SubscriptionResponseSerializer(serializers.Serializer):
    """Serialize subscription responses without exposing stored secrets."""

    id = serializers.CharField()
    tenant_id = serializers.CharField()
    event_type = serializers.CharField()
    target_url = serializers.URLField()
    active = serializers.BooleanField()
    created_at = serializers.CharField(allow_null=True)
    updated_at = serializers.CharField(allow_null=True)
    secret = serializers.CharField(required=False, write_only=False)
