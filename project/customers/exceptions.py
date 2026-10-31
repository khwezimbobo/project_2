import logging

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


# --------------------------------------------------
# CUSTOM DASHBOARD ACCESS EXCEPTION
# --------------------------------------------------

class DashboardAccessDenied(PermissionDenied):
    """
    Custom exception raised when a user attempts
    to access the staff dashboard without permission.

    Inheriting from PermissionDenied allows Django
    to handle this as a standard HTTP 403 response.
    """

    default_message = "You do not have permission to access the dashboard."

    def __init__(self, message=None):
        # Use the supplied message or the default message.
        super().__init__(message or self.default_message)


# --------------------------------------------------
# LOGIN LOCKOUT EXCEPTION (API)
# --------------------------------------------------

class AccountLocked(APIException):
    """Raised when too many failed logins were made; becomes HTTP 429."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Too many failed login attempts. Please try again later."
    default_code = "account_locked"


# --------------------------------------------------
# API ERROR HANDLER
# --------------------------------------------------

# Fallback machine-readable codes for errors that are not DRF APIExceptions
# (for example Django's Http404), keyed by HTTP status.
_STATUS_CODES = {
    400: "bad_request",
    401: "not_authenticated",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    429: "throttled",
}


def _error_body(status_code, message, details=None, code="error"):
    """Build the one JSON shape every API error uses."""
    return {
        "error": {
            "code": code,
            "status_code": status_code,
            "message": message,
            "details": details,
        }
    }


def custom_exception_handler(exc, context):
    """
    Turn every API error into the same JSON shape and log server errors.

    Registered in settings.py as REST_FRAMEWORK["EXCEPTION_HANDLER"].
    """

    # Let DRF handle the errors it already understands (400, 401, 403, 404, 429...).
    response = drf_exception_handler(exc, context)

    if response is not None:
        data = response.data

        # DRF wraps simple errors as {"detail": "..."}; field errors are richer.
        if isinstance(data, dict) and set(data.keys()) == {"detail"}:
            message, details = str(data["detail"]), None
        else:
            message, details = "The request could not be processed.", data

        if isinstance(exc, APIException):
            code = exc.default_code
        else:
            code = _STATUS_CODES.get(response.status_code, "error")

        response.data = _error_body(response.status_code, message, details, code)
        return response

    # A Django validation error that escaped a serializer is a client mistake.
    if isinstance(exc, DjangoValidationError):
        return Response(
            _error_body(
                status.HTTP_400_BAD_REQUEST,
                "The request could not be processed.",
                exc.messages,
                code="validation_error",
            ),
            status=status.HTTP_400_BAD_REQUEST,
        )

    # A database constraint (for example a duplicate email) is also a 400, not a 500.
    if isinstance(exc, IntegrityError):
        logger.warning("Database integrity error: %s", exc)
        return Response(
            _error_body(
                status.HTTP_400_BAD_REQUEST,
                "The data conflicts with an existing record.",
                code="integrity_error",
            ),
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Anything else is a bug: log the full traceback, hide the details from the client.
    view = context.get("view")
    logger.exception("Unhandled error in %s", type(view).__name__ if view else "unknown view")
    return Response(
        _error_body(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "An unexpected server error occurred.",
            code="internal_server_error",
        ),
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
