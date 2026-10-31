from rest_framework.throttling import UserRateThrottle


# --------------------------------------------------
# CUSTOMER SUBMISSION THROTTLE
# --------------------------------------------------
class SubmissionBurstThrottle(UserRateThrottle):
    """
    Limits each authenticated user to 5 customer submissions (POST requests)
    per minute. The 6th POST inside a minute gets 429 Too Many Requests, and
    DRF adds a Retry-After header saying how many seconds to wait.

    Reading (GET) and editing (PUT, PATCH, DELETE) are NOT counted here, so
    browsing the customer list is never slowed down by this class.
    """

    scope = "customer_submission"

    # The rate is set directly here, so settings.py does not need an entry
    # for "customer_submission". Format: "<number>/<second|minute|hour|day>".
    rate = "5/minute"

    def allow_request(self, request, view):
        # Only POST requests are counted against the throttle.
        if request.method != "POST":
            return True

        # POST: let DRF do the normal counting against the cache.
        return super().allow_request(request, view)
