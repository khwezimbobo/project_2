# Copy to subscriptions/tasks.py
from datetime import timedelta

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

from .models import Subscription, SubscriptionStatus
from .services import InvalidStatusTransition, change_status

logger = get_task_logger(__name__)

GRACE_PERIOD_DAYS = 30
AUTO_SUSPEND_NOTE = "Auto-suspended: contract expired beyond grace period"


@shared_task
def auto_suspend_overdue_subscriptions():
    """Suspend Active subscriptions more than 30 days past their end date (BRD 14.2).

    Each subscription is handled on its own, so one failure is logged and the task carries on.
    """
    today = timezone.localdate()
    cutoff = today - timedelta(days=GRACE_PERIOD_DAYS)

    overdue = Subscription.objects.filter(
        status=SubscriptionStatus.ACTIVE, contract_end_date__lt=cutoff
    )

    suspended = skipped = errors = 0
    for subscription in overdue:
        try:
            change_status(
                subscription,
                SubscriptionStatus.SUSPENDED,
                changed_by=None,  # shown as "system" in the audit log
                notes=AUTO_SUSPEND_NOTE,
            )
            suspended += 1
        except InvalidStatusTransition:
            skipped += 1  # someone changed its status after the query ran
            logger.warning("Skipped subscription %s: its status changed meanwhile", subscription.pk)
        except Exception:
            errors += 1
            logger.exception("Could not auto-suspend subscription %s", subscription.pk)

    logger.info(
        "auto_suspend_overdue_subscriptions finished: %s suspended, %s skipped, %s error(s)",
        suspended, skipped, errors,
    )
    return {"suspended": suspended, "skipped": skipped, "errors": errors}
