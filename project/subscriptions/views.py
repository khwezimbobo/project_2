from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Subscription
from .pagination import StandardPagination
from .permissions import IsAdminRole, is_admin
from .serializers import (
    AuditLogPageSerializer,
    AuditLogSerializer,
    StatusUpdateSerializer,
    SubscriptionFilterSerializer,
    SubscriptionSerializer,
)
from .services import change_status


# ---- Swagger documentation (ISP-15), shown at /api/docs/ under "Subscriptions" ----
# Example request and response for POST, using the worked example in docs/erd.md:
# a new customer on Home Standard, 12-Month, with Static IP and Router Rental.
CREATE_EXAMPLES = [
    OpenApiExample(
        "New customer, Home Standard, 12-Month, two add-ons",
        request_only=True,
        value={
            "customer": "6f1c2a9e-3b7d-4c55-9a0e-2d8f1b6c4e21",
            "package": 2,
            "contract_term": 2,
            "add_ons": [1, 2],
            "installation_date": "2026-11-15",
        },
    ),
    OpenApiExample(
        "Created: pricing calculated by the server",
        response_only=True,
        status_codes=["201"],
        value={
            "base_amount": "699.00",
            "add_on_total": "250.00",
            "subtotal": "949.00",
            "discount_name": "New Customer",
            "discount_amount": "94.90",
            "monthly_total": "854.10",
            "installation_fee": "500.00",
            "first_month_total": "1354.10",
            "contract_start_date": "2026-11-15",
            "contract_end_date": "2027-11-15",
            "status": "Pending",
        },
    ),
]

ERRORS = {
    400: OpenApiResponse(description="Invalid input, e.g. an unknown package or a filter that does not exist."),
    401: OpenApiResponse(description="No token, or the token has expired."),
    403: OpenApiResponse(description="Logged in, but not allowed (e.g. an agent using another agent's customer)."),
}

# The {id} in the URL is the subscription's UUID (subscription_id).
SUBSCRIPTION_ID = OpenApiParameter("id", OpenApiTypes.UUID, OpenApiParameter.PATH,
                                   description="The subscription's subscription_id (UUID).")


@extend_schema_view(
    create=extend_schema(
        tags=["Subscriptions"],
        summary="Create a subscription (pricing calculated server-side)",
        description=(
            "Agent (own customers only) or Admin. Send the customer, package, contract term, add-ons and "
            "installation date. The server calculates every price: base x term multiplier, plus add-ons, "
            "minus the single highest discount (Loyalty 15%, New Customer 10%, Multi Add-On 5%), plus the "
            "R500 installation fee on the first month. Any prices or dates sent by the client are ignored. "
            "The contract dates come from the installation date and the term length. New subscriptions "
            "start as Pending, and an audit log entry is written."
        ),
        examples=CREATE_EXAMPLES,
        responses={201: SubscriptionSerializer, **ERRORS},
    ),
    list=extend_schema(
        tags=["Subscriptions"],
        summary="List subscriptions (filterable, 20 per page)",
        description=(
            "Agent or Admin. Agents only see their own customers' subscriptions; Admins see all. "
            "Optional filters: status, package and contract_term. An invalid filter value returns 400 "
            "instead of being ignored."
        ),
        parameters=[SubscriptionFilterSerializer],   # documents ?status=&package=&contract_term=
        responses={200: SubscriptionSerializer(many=True), 400: ERRORS[400], 401: ERRORS[401]},
    ),
    retrieve=extend_schema(
        tags=["Subscriptions"],
        summary="Get one subscription with its full pricing breakdown",
        parameters=[SUBSCRIPTION_ID],
        description="Agent (own customers only) or Admin. Another agent's subscription returns 404, so its "
                    "existence is not revealed.",
        responses={200: SubscriptionSerializer, 401: ERRORS[401],
                   404: OpenApiResponse(description="Not found, or it belongs to another agent's customer.")},
    ),
    change_status=extend_schema(
        tags=["Subscriptions"],
        summary="Change a subscription's status (Admin only)",
        parameters=[SUBSCRIPTION_ID],
        description=(
            "Admin only. Allowed changes: Pending to Active or Cancelled; Active to Suspended or Cancelled; "
            "Suspended to Active or Cancelled. Cancelled is final. Any other change returns 400. Every change "
            "is recorded in the audit log with the admin's username and the optional notes."
        ),
        request=StatusUpdateSerializer,
        examples=[OpenApiExample("Activate after installation", request_only=True,
                                 value={"status": "Active", "notes": "Router installed and tested"})],
        responses={200: SubscriptionSerializer, **ERRORS,
                   404: OpenApiResponse(description="Subscription not found.")},
    ),
    logs=extend_schema(
        tags=["Subscriptions"],
        summary="Status history (audit log) of a subscription",
        parameters=[SUBSCRIPTION_ID],
        description="Agent (own customers only) or Admin. Newest first, 20 per page. changed_by is "
                    "\"System\" when Celery made the change (automatic suspension).",
        responses={200: AuditLogPageSerializer, 401: ERRORS[401],
                   404: OpenApiResponse(description="Not found, or it belongs to another agent's customer.")},
    ),
)


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
        # Swagger builds the docs without a logged-in user; give it an empty queryset so it can
        # still read the model (and show the id as a UUID).
        if getattr(self, "swagger_fake_view", False):
            return Subscription.objects.none()
        # select/prefetch_related avoid one extra query per row (the "N+1" problem).
        queryset = (Subscription.objects
                    .select_related("customer", "package", "contract_term", "created_by")
                    .prefetch_related("subscription_add_ons__add_on"))

        # IDOR prevention at queryset level (BRD 15): agents only see their own customers'
        # subscriptions; admins see everything.
        user = self.request.user
        if not is_admin(user):
            queryset = queryset.filter(customer__assigned_agent=user)

        # Filters only apply to the list (FR-15).
        if self.action == "list":
            filters = SubscriptionFilterSerializer(data=self.request.query_params)
            filters.is_valid(raise_exception=True)   # 400 if a filter value is invalid
            # Only the filters that were actually given are applied.
            queryset = queryset.filter(**filters.validated_data)

        return queryset

    # @action adds an extra URL for ONE subscription: /api/subscriptions/{id}/status/
    @action(detail=True, methods=["patch"], url_path="status",
            permission_classes=[IsAuthenticated, IsAdminRole])   # Admin only (FR-08)
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