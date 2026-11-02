# Copy to reports/services.py (replaces the earlier version)
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from alerts.models import RenewalAlert
from subscriptions.models import Subscription

EXPIRY_WINDOW_DAYS = 30


def expiring_subscriptions(today=None):
    """Active subscriptions ending within the next 30 days, soonest first.

    Ones already past their end date (still Active, waiting for the auto-suspend task) are
    included so they stay visible. Used by the dashboard and by /api/reports/expiring/.
    """
    today = today or timezone.localdate()
    return (
        Subscription.objects.filter(
            status=Subscription.Status.ACTIVE,
            contract_end_date__lte=today + timedelta(days=EXPIRY_WINDOW_DAYS),
        )
        .select_related("customer", "package", "contract_term")
        .order_by("contract_end_date", "pk")
    )


def get_dashboard_data(today=None):
    """Everything the staff dashboard shows, calculated with ORM aggregates."""
    today = today or timezone.localdate()
    active = Subscription.objects.filter(status=Subscription.Status.ACTIVE)

    monthly_revenue = active.aggregate(total=Sum("monthly_total"))["total"] or Decimal("0.00")

    expiring = list(expiring_subscriptions(today))
    for subscription in expiring:
        subscription.days_left = (subscription.contract_end_date - today).days

    return {
        "active_count": active.count(),
        "monthly_revenue": monthly_revenue,
        "expiring_subscriptions": expiring,
        "expiry_window_days": EXPIRY_WINDOW_DAYS,
        "pending_alerts": RenewalAlert.objects.filter(
            status=RenewalAlert.Status.PENDING
        ).count(),
    }