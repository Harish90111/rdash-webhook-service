"""Interface URL routing."""

from django.urls import path

from interface.views import (
    APIRootView,
    DeliveryCollectionView,
    DeliveryRetryView,
    EventIngestionView,
    HealthCheckView,
    SubscriptionCollectionView,
    SubscriptionDetailView,
    TenantMetricsView,
)


app_name = "interface"

urlpatterns = [
    path("", APIRootView.as_view(), name="api-root"),
    path("health/", HealthCheckView.as_view(), name="health-check"),
    path("metrics/", TenantMetricsView.as_view(), name="tenant-metrics"),
    path("deliveries/", DeliveryCollectionView.as_view(), name="delivery-list"),
    path(
        "deliveries/<uuid:attempt_id>/retry/",
        DeliveryRetryView.as_view(),
        name="delivery-retry",
    ),
    path("events/", EventIngestionView.as_view(), name="event-ingestion"),
    path("subscriptions/", SubscriptionCollectionView.as_view(), name="subscription-list"),
    path(
        "subscriptions/<uuid:subscription_id>/",
        SubscriptionDetailView.as_view(),
        name="subscription-detail",
    ),
]
