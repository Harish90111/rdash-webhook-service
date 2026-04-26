"""Thin DRF views for subscription management."""

from rest_framework import status

from data.repositories import DjangoSubscriptionRepository
from interface.responses import success_response
from interface.serializers import (
    SubscriptionCreateSerializer,
    SubscriptionPatchSerializer,
    SubscriptionResponseSerializer,
)
from interface.use_cases import (
    CreateSubscription,
    DeleteSubscription,
    GetSubscription,
    ListSubscriptions,
    PatchSubscription,
)
from interface.views.base import ThinAPIView


class SubscriptionCollectionView(ThinAPIView):
    """List and create subscriptions for the authenticated tenant."""

    repository_class = DjangoSubscriptionRepository

    def get(self, request):
        tenant_id = self.get_tenant_id()
        subscriptions = self.run_use_case(
            ListSubscriptions(self.repository_class()),
            tenant_id=tenant_id,
        )
        serializer = SubscriptionResponseSerializer(
            [subscription.to_dict() for subscription in subscriptions],
            many=True,
        )
        return success_response(serializer.data)

    def post(self, request):
        tenant_id = self.get_tenant_id()
        serializer = SubscriptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = self.run_use_case(
            CreateSubscription(self.repository_class()),
            tenant_id=tenant_id,
            **serializer.validated_data,
        )
        response_payload = result.subscription.to_dict()
        response_payload["secret"] = result.secret
        response_serializer = SubscriptionResponseSerializer(response_payload)
        return success_response(response_serializer.data, status_code=status.HTTP_201_CREATED)


class SubscriptionDetailView(ThinAPIView):
    """Retrieve, patch, and delete one tenant-scoped subscription."""

    repository_class = DjangoSubscriptionRepository

    def get(self, request, subscription_id: str):
        tenant_id = self.get_tenant_id()
        subscription_id = str(subscription_id)
        subscription = self.run_use_case(
            GetSubscription(self.repository_class()),
            tenant_id=tenant_id,
            subscription_id=subscription_id,
        )
        serializer = SubscriptionResponseSerializer(subscription.to_dict())
        return success_response(serializer.data)

    def patch(self, request, subscription_id: str):
        tenant_id = self.get_tenant_id()
        subscription_id = str(subscription_id)
        serializer = SubscriptionPatchSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        subscription = self.run_use_case(
            PatchSubscription(self.repository_class()),
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            changes=serializer.validated_data,
        )
        response_serializer = SubscriptionResponseSerializer(subscription.to_dict())
        return success_response(response_serializer.data)

    def delete(self, request, subscription_id: str):
        tenant_id = self.get_tenant_id()
        subscription_id = str(subscription_id)
        self.run_use_case(
            DeleteSubscription(self.repository_class()),
            tenant_id=tenant_id,
            subscription_id=subscription_id,
        )
        return success_response(None, status_code=status.HTTP_204_NO_CONTENT)
