import logging

from django.db import OperationalError, connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------
def health(request):
    """
    Public endpoint used by Docker, CI and monitoring tools.

    Returns 200 when the app is running and the database answers,
    and 503 when the database cannot be reached.
    """

    try:
        # The cheapest possible query proves the database connection works.
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except OperationalError:
        logger.error("Health check failed: database unreachable.")
        return JsonResponse({"status": "unavailable", "database": "down"}, status=503)

    return JsonResponse({"status": "ok", "database": "ok"})
