import logging

from django_filters.rest_framework import DjangoFilterBackend

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



