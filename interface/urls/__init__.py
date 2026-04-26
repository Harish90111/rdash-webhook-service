"""Interface URL routing."""

from django.urls import path

from interface.views import APIRootView, SubscriptionCollectionView, SubscriptionDetailView


app_name = "interface"

urlpatterns = [
    path("", APIRootView.as_view(), name="api-root"),
    path("subscriptions/", SubscriptionCollectionView.as_view(), name="subscription-list"),
    path(
        "subscriptions/<uuid:subscription_id>/",
        SubscriptionDetailView.as_view(),
        name="subscription-detail",
    ),
]
