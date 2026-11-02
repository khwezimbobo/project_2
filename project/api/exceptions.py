import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.http import Http404, JsonResponse
from django.views import defaults
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

SERVER_ERROR_MESSAGE = "A server error occurred. Please try again later."


def custom_exception_handler(exc, context):
    """Give every API error the same JSON shape and never leak internals.

    Every error body has a human-readable "detail" and a machine-readable "code". Validation
    errors (400) also list the problem fields at the top level, for example:
        {"detail": "Invalid input.", "code": "validation_error", "email": ["Enter a valid ..."]}
    Unexpected exceptions return a generic 500 and the real traceback goes to the server log only.
    """
    view = context.get("view")
    view_name = view.__class__.__name__ if view else "unknown view"

    # A database constraint (such as a duplicate value) is the client's problem: 400, not 500.
    if isinstance(exc, IntegrityError):
        logger.warning("Integrity error in %s: %s", view_name, exc)
        return Response(
            {"detail": "This request conflicts with existing data.", "code": "integrity_error"},
            status=400,
        )

    # Errors raised by Django's own validation (model.full_clean()) become normal 400s.
    if isinstance(exc, DjangoValidationError):
        exc = ValidationError(exc.message_dict if hasattr(exc, "error_dict") else exc.messages)

    response = drf_exception_handler(exc, context)

    if response is None:  # not an error DRF knows about, so it would have been a bare 500
        logger.error("Unhandled error in %s", view_name, exc_info=exc)
        return Response({"detail": SERVER_ERROR_MESSAGE, "code": "server_error"}, status=500)

    if isinstance(exc, ValidationError):
        body = {"detail": "Invalid input.", "code": "validation_error"}
        if isinstance(response.data, dict):
            body.update(response.data)
        else:
            body["non_field_errors"] = response.data
        response.data = body
    else:
        detail = response.data.get("detail", "")
        # Django's own 404 message names the model ("No Customer matches ..."), so replace it.
        message = "Not found." if isinstance(exc, Http404) else str(detail)
        # simplejwt says why it refused a token ("Token is expired") in a "messages" list
        reasons = response.data.get("messages")
        if isinstance(reasons, list) and reasons and isinstance(reasons[0], dict):
            reason = reasons[0].get("message")
            if reason:
                message = f"{reason}. Please log in again."
        # simplejwt carries its own machine-readable code in the response data ("token_not_valid")
        code = response.data.get("code") or getattr(detail, "code", "error")
        response.data = {"detail": message, "code": str(code)}
    return response


# ---- Django-level 404 and 500 pages: JSON under /api/, Django's normal pages elsewhere ----
def json_not_found(request, exception, template_name="404.html"):
    if request.path.startswith("/api/"):
        return JsonResponse({"detail": "Not found.", "code": "not_found"}, status=404)
    return defaults.page_not_found(request, exception, template_name=template_name)


def json_server_error(request, template_name="500.html"):
    if request.path.startswith("/api/"):
        return JsonResponse({"detail": SERVER_ERROR_MESSAGE, "code": "server_error"}, status=500)
    return defaults.server_error(request, template_name=template_name)