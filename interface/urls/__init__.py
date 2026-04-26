"""Interface URL routing."""

from django.urls import path

from interface.views import (
    APIRootView,
    EventIngestionView,
    SubscriptionCollectionView,
    SubscriptionDetailView,
)


app_name = "interface"

urlpatterns = [
    path("", APIRootView.as_view(), name="api-root"),
    path("events/", EventIngestionView.as_view(), name="event-ingestion"),
    path("subscriptions/", SubscriptionCollectionView.as_view(), name="subscription-list"),
    path(
        "subscriptions/<uuid:subscription_id>/",
        SubscriptionDetailView.as_view(),
        name="subscription-detail",
    ),
]
