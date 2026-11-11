# ===  ISP-1 / ISP-91    ===
# ProtectedError is raised when a customer still has subscriptions pointing at it.
from django.db.models import ProtectedError
# OpenApi* helpers describe the endpoints in Swagger (/api/docs/), as in subscriptions/views.py.
from drf_spectacular.utils import (
    OpenApiExample, 
    OpenApiResponse, 
    extend_schema, 
    extend_schema_view,
)
# viewsets gives ModelViewSet; status gives readable HTTP codes.
from rest_framework import status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import Customer
from .permissions import AgentScopedMixin, IsAdminOrSupportAgent
from .serializers import CustomerSerializer


# ======================================================================
# PAGINATION (lives here, so no separate pagination.py)
# ======================================================================

class StandardPagination(PageNumberPagination):
    """20 records per page; clients may ask for fewer or more with ?page_size=."""

    page_size = 20                       # the brief: 20 per page on every list
    page_size_query_param = "page_size"  # lets clients choose with ?page_size=
    max_page_size = 100                  # stops one request fetching the whole table


# ======================================================================
# SWAGGER DOCUMENTATION (ISP-15), shown at /api/docs/ under "Customers"
# ======================================================================

# Example request and response for POST.
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
]

# Error responses shared by every action (same wording style as subscriptions).
ERRORS = {
    400: OpenApiResponse(description="Invalid input, e.g. a phone number outside 10-15 digits, an invalid or duplicate email, or a filter that does not exist."),
    401: OpenApiResponse(description="No token, or the token has expired."),
    403: OpenApiResponse(description="Logged in, but not allowed (e.g. an agent using another agent's customer, or an agent deleting)."),
}
NOT_FOUND = OpenApiResponse(description="No customer with that id.")

# The customer id in the URL needs no manual parameter: drf-spectacular reads it
# from the model's UUID primary key, so Swagger shows one UUID path parameter.

# ======================================================================
# CUSTOMER VIEWSET
#   GET, POST          /api/customers/        list (search, filter, order) / create
#   GET, PUT, PATCH    /api/customers/<id>/   retrieve / update
#   DELETE             /api/customers/<id>/   Admin only (agents get 403)
# ======================================================================

@extend_schema_view(
    list=extend_schema(
        tags=["Customers"],
        summary="List customers (searchable, filterable, 20 per page)",
        description=(
            "Agent or Admin. Agents only see their own customers; Admins see all. "
            "Search with ?search= (name, email, phone), sort with ?ordering= "
            "(first_name, last_name, email, created_at; prefix - for descending), "
            "filter with ?assigned_agent= and ?created_at__gte= / ?created_at__lte=, "
            "and change the page length with ?page_size= (max 100)."
        ),
        responses={200: CustomerSerializer(many=True), 400: ERRORS[400], 401: ERRORS[401], 403: ERRORS[403]},
    ),
    create=extend_schema(
        tags=["Customers"],
        summary="Create a customer (assigned to the requesting user)",
        description=(
            "Agent or Admin. The customer is assigned to whoever creates it; any assigned_agent sent by "
            "the client is ignored. The phone number needs 10-15 digits and the email must be valid and "
            "unique (ignoring letter case); otherwise the request returns 400 with a clear message."
        ),
        examples=CREATE_EXAMPLES,
        responses={201: CustomerSerializer, **ERRORS},
    ),
    retrieve=extend_schema(
        tags=["Customers"],
        summary="Get one customer",
        description="Agent (own customers only) or Admin. Another agent's customer returns 403.",
        responses={200: CustomerSerializer, 401: ERRORS[401], 403: ERRORS[403], 404: NOT_FOUND},
    ),
    update=extend_schema(
        tags=["Customers"],
        summary="Replace a customer (PUT, all fields)",
        description=(
            "Agent (own customers only) or Admin. Send every field. assigned_agent cannot be changed "
            "through the API."
        ),
        responses={200: CustomerSerializer, **ERRORS, 404: NOT_FOUND},
    ),
    partial_update=extend_schema(
        tags=["Customers"],
        summary="Update part of a customer (PATCH)",
        description=(
            "Agent (own customers only) or Admin. Send only the fields to change, for example "
            "{\"address\": \"9 New Rd\"}."
        ),
        responses={200: CustomerSerializer, **ERRORS, 404: NOT_FOUND},
    ),
    destroy=extend_schema(
        tags=["Customers"],
        summary="Delete a customer (Admin only)",
        description=(
            "Admin only; agents get 403. A customer that still has subscriptions cannot be deleted "
            "and returns 400."
        ),
        responses={204: OpenApiResponse(description="Deleted."), **ERRORS, 404: NOT_FOUND},
    ),
)
# AgentScopedMixin comes FIRST so its get_queryset() runs before the default one.
class CustomerViewSet(AgentScopedMixin, viewsets.ModelViewSet):
    # Base queryset; the mixin narrows it for agents on list requests.
    queryset = Customer.objects.select_related("assigned_agent")
    # Validates input and formats output.
    serializer_class = CustomerSerializer
    # Role gate, per-record ownership (403) and agents-cannot-delete.
    permission_classes = [IsAdminOrSupportAgent]
    # 20 per page.
    pagination_class = StandardPagination

    # ORM path to the owning agent; used by the mixin and the permission class.
    agent_field = "assigned_agent"

    # UUID ids only: a malformed id such as /customers/abc/ gets a clean 404.
    lookup_value_regex = "[0-9a-fA-F-]{36}"

    # The filter backends come from settings.py (DEFAULT_FILTER_BACKENDS),
    # so this class only declares WHICH fields each one may use.
    # drf-spectacular documents these parameters automatically.
    filterset_fields = {
        "assigned_agent": ["exact"],     # ?assigned_agent=3
        "created_at": ["gte", "lte"],    # ?created_at__gte=2026-10-01
    }
    # ?search=zulu matches name, email or phone.
    search_fields = ["first_name", "last_name", "email", "phone_number"]
    # ?ordering=-created_at
    ordering_fields = ["first_name", "last_name", "email", "created_at"]
    # Default order; pagination needs a stable order to avoid repeats.
    ordering = ["last_name", "first_name"]

    def get_queryset(self):
        # drf-spectacular builds the docs with no real user; return an empty
        # queryset then, so the role/ownership filter is never run on an anonymous user.
        if getattr(self, "swagger_fake_view", False):
            return Customer.objects.none()
        return super().get_queryset()

    def perform_create(self, serializer):
        # assigned_agent defaults to the requesting user; never trust the client.
        serializer.save(assigned_agent=self.request.user)

    def destroy(self, request, *args, **kwargs):
        # A customer with subscriptions cannot be deleted (PROTECT). Return a
        # clean 400 in the shared error shape instead of a 500.
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "This customer still has subscriptions and cannot be deleted.",
                 "code": "protected"},
                status=status.HTTP_400_BAD_REQUEST,
            )