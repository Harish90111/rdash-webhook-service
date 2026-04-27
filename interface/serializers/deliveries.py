"""Serializers for delivery-attempt listing endpoints."""

from rest_framework import serializers

from domain.entities import DeliveryStatus


DELIVERY_STATUS_CHOICES = [status.value for status in DeliveryStatus]


class DeliveryAttemptListQuerySerializer(serializers.Serializer):
    """Validate query parameters for delivery listing."""

    status = serializers.ChoiceField(choices=DELIVERY_STATUS_CHOICES, required=False)
    event_id = serializers.UUIDField(required=False)
    subscription_id = serializers.UUIDField(required=False)


class DeliveryAttemptResponseSerializer(serializers.Serializer):
    """Serialize tenant-scoped delivery attempts."""

    id = serializers.CharField()
    event_id = serializers.CharField()
    subscription_id = serializers.CharField()
    status = serializers.CharField()
    attempt_number = serializers.IntegerField()
    status_code = serializers.IntegerField(allow_null=True, required=False)
    response_body = serializers.CharField(allow_null=True, required=False)
    error_message = serializers.CharField(allow_null=True, required=False)
    next_retry_at = serializers.CharField(allow_null=True)
    created_at = serializers.CharField(allow_null=True)
    completed_at = serializers.CharField(allow_null=True)
