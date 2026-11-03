from django.urls import path

from .views import ExpiringReportView, RevenueSummaryView

urlpatterns = [
    path("revenue-summary/", RevenueSummaryView.as_view(), name="revenue-summary"),
    path("expiring/", ExpiringReportView.as_view(), name="expiring-report"),
]