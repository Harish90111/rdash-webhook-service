"""Thin DRF view for tenant-scoped delivery attempt listing."""

from rest_framework.pagination import PageNumberPagination

from data.repositories import DjangoDeliveryAttemptRepository
from interface.responses import success_response
from interface.serializers import (
    DeliveryAttemptListQuerySerializer,
    DeliveryAttemptResponseSerializer,
)
from interface.use_cases import ListDeliveryAttempts
from interface.views.base import ThinAPIView


class DeliveryAttemptPagination(PageNumberPagination):
    """Conservative page-number pagination for delivery visibility."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class DeliveryCollectionView(ThinAPIView):
    """List delivery attempts for the authenticated tenant."""

    repository_class = DjangoDeliveryAttemptRepository
    pagination_class = DeliveryAttemptPagination

    def get(self, request):
        tenant_id = self.get_tenant_id()
        serializer = DeliveryAttemptListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data

        attempts = self.run_use_case(
            ListDeliveryAttempts(self.repository_class()),
            tenant_id=tenant_id,
            status=filters.get("status"),
            event_id=str(filters["event_id"]) if filters.get("event_id") else None,
            subscription_id=(
                str(filters["subscription_id"])
                if filters.get("subscription_id")
                else None
            ),
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(attempts, request, view=self)
        payload = [attempt.to_dict() for attempt in page]
        response_serializer = DeliveryAttemptResponseSerializer(payload, many=True)
        return success_response(
            response_serializer.data,
            meta={
                "pagination": {
                    "count": paginator.page.paginator.count,
                    "page": paginator.page.number,
                    "page_size": paginator.get_page_size(request) or len(payload),
                    "total_pages": paginator.page.paginator.num_pages,
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                }
            },
        )
