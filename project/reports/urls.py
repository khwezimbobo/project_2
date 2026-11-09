from django.urls import path

from .views import ExpiringReportView, RevenueSummaryView, DashboardView

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'), # The route for /dashboard/
    path("revenue-summary/", RevenueSummaryView.as_view(), name="revenue-summary"),
    path("expiring/", ExpiringReportView.as_view(), name="expiring-report"),
]