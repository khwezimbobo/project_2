# ===  ISP-1 / ISP-91    ===
# ProtectedError is raised when a customer still has subscriptions pointing at it.
from django.db.models import ProtectedError
# viewsets gives ModelViewSet; status gives readable HTTP codes.
from rest_framework import status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import Customer
from .permissions import AgentScopedMixin, IsAdminOrSupportAgent
from .serializers import CustomerSerializer

# Example request and response for POST.
CREATE_EXAMPLES = [
    OpenApiExample(
        "New customer",
        request_only=True,
        value={
            "first_name": "Siseko",
            "last_name": "Mtebele",
            "email": "siseko.mtebele@example.com",
            "phone_number": "0821234567",
            "address": "1 Long St, Cape Town",
        },
    ),
]

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
@extend_schema_view(
    list=extend_schema(
        tags=["Customers"],
        summary="List customers",
        description=(
            "Returns customers, 20 per page. Support Agents see only their own "
            "customers; Admins see all. Supports ?search= (name, email, phone), "
            "?ordering= (first_name, last_name, email, created_at), "
            "?assigned_agent= and ?created_at__gte= / ?created_at__lte=, "
            "and ?page_size= (max 100)."
        ),
    ),
)

class CustomerViewSet(AgentScopedMixin, viewsets.ModelViewSet):

# ======================================================================
# CUSTOMER VIEWSET
#   GET, POST          /api/customers/        list (search, filter, order) / create
#   GET, PUT, PATCH    /api/customers/<id>/   retrieve / update
#   DELETE             /api/customers/<id>/   Admin only (agents get 403)
# ======================================================================

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

    def perform_create(self, serializer):
        # assigned_agent defaults to the requesting user; never trust the client.
        serializer.save(assigned_agent=self.request.user)

    def destroy(self, request, *args, **kwargs):
        # A customer with subscriptions cannot be deleted (PROTECT). Return a
        # clean 400 instead of a 500, as the brief requires for DB constraints.
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "This customer still has subscriptions and cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
            
