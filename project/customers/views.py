# Customer API (BRD FR-03 create, FR-04 list/search/filter, s12 endpoints).
# ProtectedError is raised when a customer still has subscriptions.
from django.db.models import ProtectedError
# OpenApi* helpers describe the endpoints in Swagger (BRD FR-17, /api/docs/).
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample, OpenApiParameter, OpenApiResponse,
    extend_schema, extend_schema_view,
)
from rest_framework import status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import Customer
from .permissions import AgentScopedMixin, IsAdminOrSupportAgent
from .serializers import CustomerSerializer


# ======================================================================
# PAGINATION (BRD s8.2: 20 records per page on every list)
# ======================================================================
class StandardPagination(PageNumberPagination):
    """20 records per page; clients may use ?page_size= (maximum 100)."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


# ======================================================================
# SWAGGER DOCS (BRD FR-17, s17): shown at /api/docs/ under "Customers"
# ======================================================================

# ---- Input examples ----
# The body fields come from CustomerSerializer. These examples pre-fill
# "Try it out" so a tester can press Execute without typing everything.
# request_only=True: shown in the request, not the response.

# POST /api/customers/ (FR-03)
CREATE_EXAMPLES = [
    OpenApiExample(
        "New customer",
        request_only=True,
        value={
            "first_name": "Kylian",
            "last_name": "Mbappé",
            "email": "kylian.mbappe@example.com",
            "phone_number": "0821234567",
            "address": "1 Long St, Johannesburg",
        },
    ),
    # What the API returns after a successful create (201).
    OpenApiExample(
        "Created: assigned to the requesting user",
        response_only=True,
        status_codes=["201"],
        value={
            "customer_id": "6f1c2a9e-3b7d-4c55-9a0e-2d8f1b6c4e21",
            "first_name": "Kylian",
            "last_name": "Mbappé",
            "email": "kylian.mbappe@example.com",
            "phone_number": "0821234567",
            "address": "1 Long St, Johannesburg",
            "assigned_agent": 2,
            "assigned_agent_username": "agent1",
            "created_at": "2026-11-10T08:30:00Z",
            "updated_at": "2026-11-10T08:30:00Z",
        },
    ),
    # A validation error (BRD s18: invalid input returns 400).
    OpenApiExample(
        "Invalid input",
        response_only=True,
        status_codes=["400"],
        value={"phone_number": [
            "Phone number must contain between 10 and 15 digits."
        ]},
    ),
]

# PUT /api/customers/{id}/ (replace: send every field)
UPDATE_EXAMPLES = [
    OpenApiExample(
        "Replace a customer (all fields)",
        request_only=True,
        value={
            "first_name": "Kylian",
            "last_name": "Mbappé",
            "email": "kylian.mbappe@example.com",
            "phone_number": "0821234567",
            "address": "9 New Rd, Johannesburg",
        },
    ),
]

# PATCH /api/customers/{id}/ (partial: send only the fields to change)
PATCH_EXAMPLES = [
    OpenApiExample(
        "Change the address only",
        request_only=True,
        value={"address": "9 New Rd, Johannesburg"},
    ),
    OpenApiExample(
        "Change the phone number only",
        request_only=True,
        value={"phone_number": "0831112222"},
    ),
]

# ---- Query inputs for GET /api/customers/ (FR-04) ----
# Filters, search and ordering are documented automatically. These two add a
# clearer description and examples.
SEARCH_PARAM = OpenApiParameter(
    "search", OpenApiTypes.STR, OpenApiParameter.QUERY,
    description="Matches first name, last name, email or phone number.",
    examples=[
        OpenApiExample("By surname", value="Mbappé"),
        OpenApiExample("By email", value="kylian.mbappe@example.com"),
    ],
)
ORDERING_PARAM = OpenApiParameter(
    "ordering", OpenApiTypes.STR, OpenApiParameter.QUERY,
    description=(
        "Sort field: first_name, last_name, email or created_at. "
        "Prefix with - for descending."
    ),
    examples=[
        OpenApiExample("Newest first", value="-created_at"),
        OpenApiExample("Surname A to Z", value="last_name"),
    ],
)

# ---- Error responses shared by every action (BRD s15, s18) ----
ERRORS = {
    400: OpenApiResponse(description=(
        "Invalid input, e.g. a phone number outside 10-15 digits, an "
        "invalid or duplicate email, or a filter that does not exist."
    )),
    401: OpenApiResponse(description="No token, or the token has expired."),
    403: OpenApiResponse(description=(
        "Logged in, but not allowed (e.g. an agent using another agent's "
        "customer, or an agent deleting)."
    )),
}
NOT_FOUND = OpenApiResponse(description="No customer with that id.")

# The id in the URL is read from the model's UUID primary key, so no manual
# path parameter is needed.


# ======================================================================
# CUSTOMER VIEWSET (BRD s12)
#   GET, POST          /api/customers/        list (search, filter) / create
#   GET, PUT, PATCH    /api/customers/<id>/   retrieve / update
#   DELETE             /api/customers/<id>/   Admin only (agents get 403)
# ======================================================================
@extend_schema_view(
    list=extend_schema(
        tags=["Customers"],
        summary="List customers (searchable, filterable, 20 per page)",
        description=(
            "Agent or Admin. Agents only see their own customers; Admins "
            "see all. Search with ?search= (name, email, phone), sort with "
            "?ordering= (first_name, last_name, email, created_at; prefix - "
            "for descending), filter with ?assigned_agent= and "
            "?created_at__gte= / ?created_at__lte=, and change the page "
            "length with ?page_size= (max 100)."
        ),
        parameters=[SEARCH_PARAM, ORDERING_PARAM],
        responses={
            200: CustomerSerializer(many=True),
            400: ERRORS[400], 401: ERRORS[401], 403: ERRORS[403],
        },
    ),
    create=extend_schema(
        tags=["Customers"],
        summary="Create a customer (assigned to the requesting user)",
        description=(
            "Agent or Admin. The customer is assigned to whoever creates "
            "it; any assigned_agent sent by the client is ignored. The "
            "phone number needs 10-15 digits and the email must be valid "
            "and unique (ignoring letter case); otherwise the request "
            "returns 400 with a clear message."
        ),
        request=CustomerSerializer,      # the request body shown in Swagger
        examples=CREATE_EXAMPLES,
        responses={201: CustomerSerializer, **ERRORS},
    ),
    retrieve=extend_schema(
        tags=["Customers"],
        summary="Get one customer",
        description=(
            "Agent (own customers only) or Admin. Another agent's customer "
            "returns 403."
        ),
        responses={
            200: CustomerSerializer,
            401: ERRORS[401], 403: ERRORS[403], 404: NOT_FOUND,
        },
    ),
    update=extend_schema(
        tags=["Customers"],
        summary="Replace a customer (PUT, all fields)",
        description=(
            "Agent (own customers only) or Admin. Send every field. "
            "assigned_agent cannot be changed through the API."
        ),
        request=CustomerSerializer,
        examples=UPDATE_EXAMPLES,
        responses={200: CustomerSerializer, **ERRORS, 404: NOT_FOUND},
    ),
    partial_update=extend_schema(
        tags=["Customers"],
        summary="Update part of a customer (PATCH)",
        description=(
            "Agent (own customers only) or Admin. Send only the fields to "
            "change, for example {\"address\": \"9 New Rd\"}."
        ),
        request=CustomerSerializer,
        examples=PATCH_EXAMPLES,
        responses={200: CustomerSerializer, **ERRORS, 404: NOT_FOUND},
    ),
    destroy=extend_schema(
        tags=["Customers"],
        summary="Delete a customer (Admin only)",
        description=(
            "Admin only; agents get 403. A customer that still has "
            "subscriptions cannot be deleted and returns 400."
        ),
        responses={
            204: OpenApiResponse(description="Deleted."),
            **ERRORS, 404: NOT_FOUND,
        },
    ),
)
# AgentScopedMixin goes first, so its get_queryset() runs first (BRD s15).
class CustomerViewSet(AgentScopedMixin, viewsets.ModelViewSet):
    queryset = Customer.objects.select_related("assigned_agent")
    serializer_class = CustomerSerializer
    # Role check, ownership check (403) and agents-cannot-delete (BRD s7).
    permission_classes = [IsAdminOrSupportAgent]
    pagination_class = StandardPagination

    # Path to the owning agent; used by the mixin and the permission class.
    agent_field = "assigned_agent"

    # UUID ids only: a malformed id such as /customers/abc/ gets a clean 404.
    lookup_value_regex = "[0-9a-fA-F-]{36}"

    # The filter backends come from settings (DEFAULT_FILTER_BACKENDS); here
    # we only choose the fields (BRD FR-04).
    filterset_fields = {
        "assigned_agent": ["exact"],     # ?assigned_agent=3
        "created_at": ["gte", "lte"],    # ?created_at__gte=2026-10-01
    }
    search_fields = ["first_name", "last_name", "email", "phone_number"]
    ordering_fields = ["first_name", "last_name", "email", "created_at"]
    # Default order keeps pagination stable.
    ordering = ["last_name", "first_name"]

    def perform_create(self, serializer):
        # The customer belongs to whoever creates it. Never trust the client.
        serializer.save(assigned_agent=self.request.user)

    def destroy(self, request, *args, **kwargs):
        # BRD s18: database errors return 400, not 500. A customer that still
        # has subscriptions cannot be deleted (on_delete=PROTECT).
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "This customer still has subscriptions and "
                           "cannot be deleted.",
                 "code": "protected"},
                status=status.HTTP_400_BAD_REQUEST,
            )