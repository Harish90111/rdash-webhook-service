"""Interface URL routing."""

from django.urls import path

from interface.views import APIRootView


app_name = "interface"

urlpatterns = [
    path("", APIRootView.as_view(), name="api-root"),
]
