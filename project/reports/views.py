# Create your views here.
from decimal import Decimal

from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic import TemplateView
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView, status

from .permissions import IsAdminGroup
from .queries import revenue_by_package
from .serializers import (
    ExpiringSubscriptionSerializer,
    RevenueRowSerializer,
    RevenueSummarySerializer,
)
from .services import expiring_subscriptions, get_dashboard_data


# ---- HTML dashboard (Admin, session login) ----
class StaffRequiredMixin(UserPassesTestMixin):
    """Anonymous users go to the login page; logged-in non-staff users get a 403."""

    def test_func(self):
        user = self.request.user
        return user.is_active and user.is_superuser


class DashboardView(StaffRequiredMixin, TemplateView):
    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_dashboard_data())
        return context


# ---- API reports ----
class RevenueSummaryView(APIView):
    """GET /api/reports/revenue-summary/ (Admin): active monthly revenue per package, raw SQL."""

    permission_classes = [IsAuthenticated, IsAdminGroup]

    @extend_schema(
        tags=["Reports"],
        summary="Active monthly revenue by package",
        description=(
            "Admin only. Total monthly revenue of Active subscriptions, grouped by package, with "
            "an overall total. Packages with no active subscriptions are listed with zero."
        ),
        responses=RevenueSummarySerializer,
    )
    def get(self, request):
        try:
            rows = RevenueRowSerializer(revenue_by_package(), many=True).data
            total = sum((Decimal(row["monthly_revenue"]) for row in rows), Decimal("0"))
        except Exception:
            # If the database or query fails, return a safe structure instead of crashing
            return Response({"detail": "Query failed to execute."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
        return Response(
            {
                "total_monthly_revenue": str(total.quantize(Decimal("0.01"))),
                "packages": rows,
            }
        )


@extend_schema(
    tags=["Reports"],
    summary="Subscriptions expiring within 30 days",
    description=(
        "Active subscriptions ending within the next 30 days, soonest first. Ones already past "
        "their end date (waiting for auto-suspend) are included with a negative `days_left`. "
        "Agents see only their own customers' subscriptions; Admins see all."
    ),
)
class ExpiringReportView(generics.ListAPIView):
    """GET /api/reports/expiring/ (Agent, Admin): subscriptions ending within 30 days."""

    serializer_class = ExpiringSubscriptionSerializer
    permission_classes = [IsAuthenticated, IsAdminGroup]

    def get_queryset(self):
        queryset = expiring_subscriptions()
        if not self.request.user.is_superuser and not self.request.user.groups.filter(name="Admin").exists():
            queryset = queryset.filter(customer__agent=self.request.user)
        return queryset