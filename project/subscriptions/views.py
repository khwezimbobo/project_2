from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Subscription
from .pagination import StandardPagination
from .permissions import IsAdminGroup, is_admin
from .serializers import (
    AuditLogSerializer,
    StatusUpdateSerializer,
    SubscriptionFilterSerializer,
    SubscriptionSerializer,
)
from .services import change_status


class SubscriptionViewSet(mixins.CreateModelMixin,     # POST /api/subscriptions/
                          mixins.ListModelMixin,       # GET  /api/subscriptions/
                          mixins.RetrieveModelMixin,   # GET  /api/subscriptions/{id}/
                          viewsets.GenericViewSet):    # Base machinery; the mixins add the actions above
    """Subscriptions API.

    POST  /api/subscriptions/              - create (pricing calculated server-side)
    GET   /api/subscriptions/              - list, filterable by ?status=&package=&contract_term=
    GET   /api/subscriptions/{id}/         - one subscription with its full pricing breakdown
    PATCH /api/subscriptions/{id}/status/  - change status (Admin only), audit log written
    GET   /api/subscriptions/{id}/logs/    - status history (audit log)

    No PUT/PATCH/DELETE on the subscription itself: prices and dates never change after creation.
    """

    permission_classes = [IsAuthenticated]   # Must be logged in (FR-16)
    pagination_class = StandardPagination    # 20 per page (BRD 8.2)

    def get_serializer_class(self):
        # Each action gets the serializer that matches its input/output.
        # This also makes the browsable API form and Swagger show the right fields.
        if self.action == "change_status":
            return StatusUpdateSerializer
        if self.action == "logs":
            return AuditLogSerializer
        return SubscriptionSerializer

    def get_queryset(self):
        # select/prefetch_related avoid one extra query per row (the "N+1" problem).
        queryset = (Subscription.objects
                    .select_related("customer", "package", "contract_term", "created_by")
                    .prefetch_related("subscription_add_ons__add_on"))

        # IDOR prevention at queryset level (BRD 15): agents only see their own customers'
        # subscriptions; admins see everything.
        user = self.request.user
        if not is_admin(user):
            queryset = queryset.filter(customer__agent=user)

        # Filters only apply to the list (FR-15).
        if self.action == "list":
            filters = SubscriptionFilterSerializer(data=self.request.query_params)
            filters.is_valid(raise_exception=True)   # 400 if a filter value is invalid
            # Only the filters that were actually given are applied.
            queryset = queryset.filter(**filters.validated_data)

        return queryset

    # @action adds an extra URL for ONE subscription: /api/subscriptions/{id}/status/
    @action(detail=True, methods=["patch"], url_path="status",
            permission_classes=[IsAuthenticated, IsAdminGroup])   # Admin only (FR-08)
    def change_status(self, request, pk=None):
        """PATCH /api/subscriptions/{id}/status/  body: {"status": "Active", "notes": "..."}

        Admin only (FR-08). Invalid transitions return 400 (BRD 18).
        """
        subscription = self.get_object()   # 404 if it doesn't exist
        serializer = StatusUpdateSerializer(instance=subscription, data=request.data)
        serializer.is_valid(raise_exception=True)   # 400 with a clear message if not allowed

        # The service updates the status AND writes the audit log entry (FR-09).
        change_status(
            subscription,
            serializer.validated_data["status"],
            changed_by=request.user,
            notes=serializer.validated_data["notes"],
        )
        return Response(SubscriptionSerializer(subscription).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        """GET /api/subscriptions/{id}/logs/ - the subscription's status history, newest first.

        Agents can only see logs for their own customers' subscriptions: get_object() uses
        get_queryset(), so another agent's subscription returns 404 (IDOR prevention).
        """
        subscription = self.get_object()
        logs = subscription.audit_logs.select_related("changed_by").order_by("-timestamp")
        page = self.paginate_queryset(logs)   # 20 per page, like every list
        return self.get_paginated_response(AuditLogSerializer(page, many=True).data)