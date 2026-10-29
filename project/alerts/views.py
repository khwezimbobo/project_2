from django.utils import timezone
from rest_framework import filters, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import RenewalAlert
from .permissions import IsAlertAgentOrAdmin
from .serializers import RenewalAlertSerializer

class AlertViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """/api/alerts/ and /api/alerts/{id}/acknowledge/. Alerts are created by the Celery task."""
    serializer_class = RenewalAlertSerializer
    permission_classes = [IsAuthenticated, IsAlertAgentOrAdmin]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ("days_until_expiry", "alert_date", "created_at")
    ordering = ("days_until_expiry", "-created_at")  # most urgent first

    def get_queryset(self):
        queryset = RenewalAlert.objects.select_related(
            "subscription__customer", "subscription__package", "acknowledged_by"
        )
        if self.action != "list":
            return queryset  # detail routes: the object permission returns 403 for other agents

        if not self.request.user.is_staff:
            queryset = queryset.filter(subscription__customer__agent=self.request.user)

        status = self.request.query_params.get("status")
        if status:
            if status not in RenewalAlert.Status.values:
                choices = ", ".join(RenewalAlert.Status.values)
                raise ValidationError({"status": [f"Choose one of: {choices}."]})
            queryset = queryset.filter(status=status)
        return queryset

    @action(detail=True, methods=["patch"], url_path="acknowledge")
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        if alert.status == RenewalAlert.Status.ACKNOWLEDGED:
            raise ValidationError({"status": ["This alert has already been acknowledged."]})

        alert.status = RenewalAlert.Status.ACKNOWLEDGED
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.save(update_fields=["status", "acknowledged_by", "acknowledged_at"])
        return Response(self.get_serializer(alert).data)