from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import filters, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
 
from .models import RenewalAlert
from .permissions import IsAlertAgentOrAdmin
from .serializers import RenewalAlertSerializer
 
 
# The {id} in /api/alerts/{id}/ and /api/alerts/{id}/acknowledge/
ALERT_ID = OpenApiParameter(
    "id", OpenApiTypes.UUID, OpenApiParameter.PATH, description="The id of the renewal alert."
)
 
 
@extend_schema(tags=["Alerts"])
@extend_schema_view(
    list=extend_schema(
        summary="List renewal alerts",
        description=(
            "Created each morning for Active subscriptions ending within 7 days. Agents see only "
            "alerts for their own customers; Admins see all. Most urgent first."
        ),
        parameters=[
            OpenApiParameter(
                "status", OpenApiTypes.STR, enum=RenewalAlert.Status.values,
                description="Only alerts with this status.",
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Get a renewal alert",
        description="Returns 403 for another agent's customer.",
        parameters=[ALERT_ID],
    ),
)
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
 
    @extend_schema(
        summary="Acknowledge a renewal alert",
        description=(
            "Marks the alert as handled and records who acknowledged it and when. "
            "No request body is needed. Acknowledging twice returns 400."
        ),
        request=None,
        responses=RenewalAlertSerializer,
        parameters=[ALERT_ID],
    )
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