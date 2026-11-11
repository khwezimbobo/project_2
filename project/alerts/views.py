# alerts/views.py (Refined for IsAdminOrSupportAgent)
from django.utils import timezone
from rest_framework import filters, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import RenewalAlert
from .permissions import IsAdminOrSupportAgent # <-- Using the new class
from .serializers import RenewalAlertSerializer

class AlertViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    /api/alerts/ and /api/alerts/{id}/acknowledge/. Alerts are created by the Celery task.
    """
    serializer_class = RenewalAlertSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSupportAgent] # <-- Using the new class
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ("days_until_expiry", "alert_date", "created_at")
    ordering = ("days_until_expiry", "-created_at")

    def get_queryset(self):
        queryset = RenewalAlert.objects.select_related(
            "subscription__customer", "subscription__package", "acknowledged_by"
        )

        # SECURITY CHECK: This filters the *list* view based on ownership
        # Admins bypass this filter, agents are filtered to only see their own customers.
        if not self.request.user.can_view_all: 
            # This uses the correct ORM path defined in your permission logic.
            queryset = queryset.filter(subscription__customer__assigned_agent=self.request.user)

        # Status filtering (unchanged)
        status = self.request.query_params.get("status")
        if status:
            if status not in RenewalAlert.Status.values:
                choices = ", ".join(RenewalAlert.Status.values)
                raise ValidationError({"status": [f"Choose one of: {choices}."]})
            queryset = queryset.filter(status=status)
            
        return queryset

    @action(detail=True, methods=["patch"], url_path="acknowledge")
    def acknowledge(self, request, pk=None):
        # DANGER ZONE: self.get_object() performs the HAS_OBJECT_PERMISSION check 
        # automatically using IsAdminOrSupportAgent. If the user isn't the owner,
        # this line raises a 404 error before execution.
        alert = self.get_object() 

        if alert.status == RenewalAlert.Status.ACKNOWLEDGED:
            raise ValidationError({"status": ["This alert has already been acknowledged."]})

        alert.status = RenewalAlert.Status.ACKNOWLEDGED
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.save(update_fields=["status", "acknowledged_by", "acknowledged_at"])
        return Response(self.get_serializer(alert).data)