import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.exceptions import APIException
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView

from . import lockout
from .exceptions import AccountLocked
from .filters import CustomerFilter
from .models import Customer
from .permissions import IsAuthenticatedAndAgent, customers_for
from .serializers import CustomerSerializer, RoleTokenObtainPairSerializer
from .throttles import SubmissionBurstThrottle

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# JWT LOGIN
# ----------------------------------------------------------------------
class LoginView(TokenObtainPairView):
    """POST username + password, receive an access and a refresh token."""

    serializer_class = RoleTokenObtainPairSerializer

    # Slows down password-guessing (rate "login" is set in settings.py).
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        # A malformed body (such as a JSON list) has no .get(); treat it as "no username".
        data = request.data if hasattr(request.data, "get") else {}
        username = str(data.get("username", ""))

        # Too many recent failures for this username and IP: refuse before checking the password.
        if lockout.is_locked(request, username):
            logger.warning("API login refused (locked) for username '%s'.", username)
            raise AccountLocked(lockout.lockout_message())

        try:
            response = super().post(request, *args, **kwargs)
        except APIException:
            # Count the failure and log the attempt (never the password).
            lockout.record_failure(request, username)
            logger.warning("Failed API login for username '%s'.", username)
            raise

        # A good login wipes the failure counter.
        lockout.clear_failures(request, username)
        logger.info("API login succeeded for username '%s'.", username)
        return response


# ----------------------------------------------------------------------
# REST API
# ----------------------------------------------------------------------
class CustomerViewSet(viewsets.ModelViewSet):

    serializer_class = CustomerSerializer

    # Only authenticated Agents/Admins; object permission enforces ownership.
    permission_classes = [IsAuthenticatedAndAgent]

    # Filtering (?agent=), searching (?search=) and ordering (?ordering=).
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CustomerFilter
    search_fields = [
        "first_name", "last_name", "email", "phone", "assigned_agent__username",
    ]
    ordering_fields = ["first_name", "last_name", "email", "created_at"]
    ordering = ["last_name", "first_name"]   # default order; pagination needs a stable order

    # General per-scope limit plus the 5-POSTs-per-minute burst limit.
    throttle_classes = [ScopedRateThrottle, SubmissionBurstThrottle]
    throttle_scope = "customer"

    def get_queryset(self):
        # Used when API documentation tools inspect the view without a real user.
        if getattr(self, "swagger_fake_view", False):
            return Customer.objects.none()

        # LIST: each agent only receives their own customers (admins get all).
        if self.action == "list":
            return customers_for(self.request.user)

        # DETAIL actions search every customer so that a record owned by
        # another agent is found and then refused with 403 by
        # IsAuthenticatedAndAgent.has_object_permission.
        return Customer.objects.select_related("assigned_agent")

    def perform_create(self, serializer):
        # New customers are assigned to whoever creates them.
        customer = serializer.save(assigned_agent=self.request.user)
        logger.info(
            "Customer %s created by user id %s.", customer.pk, self.request.user.pk
        )

    def perform_destroy(self, instance):
        logger.info("Customer %s deleted by user id %s.", instance.pk, self.request.user.pk)
        instance.delete()
