from datetime import timedelta
from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

from subscriptions.models import Subscription
from .models import RenewalAlert

logger = get_task_logger(__name__)

ALERT_WINDOW_DAYS = 7

@shared_task
def check_expiring_subscriptions():
    """Create one renewal alert for each Active subscription ending within 7 days (BRD 14.1).
    Subscriptions that already have an alert are skipped, so running it every day is safe.
    Subscriptions already past their end date (still Active, waiting for auto-suspend) are
    included, with a negative days_until_expiry.
    """
    today = timezone.localdate()
    cutoff = today + timedelta(days=ALERT_WINDOW_DAYS)

    candidates = Subscription.objects.filter(
        status=Subscription.Status.ACTIVE,
        contract_end_date__lte=cutoff,
        renewal_alert__isnull=True,
    )

    created = errors = 0
    for subscription in candidates:
        try:
            _, was_created = RenewalAlert.objects.get_or_create(
                subscription=subscription,
                defaults={
                    "days_until_expiry": (subscription.contract_end_date - today).days,
                    "alert_date": today,
                },
            )
            created += int(was_created)
        except Exception:
            errors += 1
            logger.exception("Could not create a renewal alert for subscription %s", subscription.pk)

    logger.info(
        "check_expiring_subscriptions finished: %s alert(s) created, %s error(s)", created, errors
    )
    return {"created": created, "errors": errors}