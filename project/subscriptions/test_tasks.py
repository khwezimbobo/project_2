from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from customers.models import Customer
from packages.models import ContractTerm, Package

from .models import Subscription, SubscriptionAuditLog, SubscriptionStatus
from .services import change_status as real_change_status
from .services import create_subscription
from .tasks import AUTO_SUSPEND_NOTE, auto_suspend_overdue_subscriptions

User = get_user_model()


class AutoSuspendTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_data", verbosity=0)
        cls.today = timezone.localdate()
        cls.agent = User.objects.create_user("agent", password="pw", role="agent")
        cls.customer = Customer.objects.create(
            name="Thandi", email="t@x.co", phone="0821234567", address="1 Long St",
            assigned_agent=cls.agent,
        )
        cls.package = Package.objects.get(name="Home Basic")
        cls.term = ContractTerm.objects.get(name="12-Month")

    def make_subscription(self, days_past_end, status=SubscriptionStatus.ACTIVE):
        """Create a subscription with the service whose end date was days_past_end days ago.

        The service sets the end date to the installation date plus the term's length, so the
        installation date is worked out backwards from the end date we want.
        """
        subscription = create_subscription(
            customer=self.customer,
            package=self.package,
            contract_term=self.term,
            add_ons=[],
            installation_date=self.today - timedelta(days=days_past_end + self.term.duration_days),
            created_by=self.agent,
        )
        Subscription.objects.filter(pk=subscription.pk).update(status=status)  # new ones start Pending
        return subscription

    @staticmethod
    def suspension_logs():
        """The audit rows written by a suspension (creating a subscription writes its own row)."""
        return SubscriptionAuditLog.objects.filter(new_status=SubscriptionStatus.SUSPENDED)

    def test_35_days_overdue_is_suspended_with_an_audit_log(self):  # BRD test case TC-07
        sub = self.make_subscription(35)
        result = auto_suspend_overdue_subscriptions()
        sub.refresh_from_db()
        self.assertEqual(sub.status, "Suspended")
        log = self.suspension_logs().get(subscription=sub)
        self.assertEqual((log.old_status, log.new_status), ("Active", "Suspended"))
        self.assertEqual(log.notes, AUTO_SUSPEND_NOTE)
        self.assertEqual(AUTO_SUSPEND_NOTE, "Auto-suspended: contract expired beyond grace period")
        self.assertIsNone(log.changed_by)
        self.assertEqual(result, {"suspended": 1, "skipped": 0, "errors": 0})

    def test_grace_period_boundary(self):
        within_grace = self.make_subscription(20)
        exactly_30 = self.make_subscription(30)   # "more than 30 days": not yet
        past_31 = self.make_subscription(31)
        auto_suspend_overdue_subscriptions()
        for sub, expected in ((within_grace, "Active"), (exactly_30, "Active"), (past_31, "Suspended")):
            sub.refresh_from_db()
            self.assertEqual(sub.status, expected)

    def test_only_active_subscriptions_are_touched(self):
        others = [self.make_subscription(40, status=s) for s in ("Pending", "Suspended", "Cancelled")]
        result = auto_suspend_overdue_subscriptions()
        self.assertEqual(result["suspended"], 0)
        self.assertEqual(self.suspension_logs().count(), 0)
        for sub, expected in zip(others, ("Pending", "Suspended", "Cancelled")):
            sub.refresh_from_db()
            self.assertEqual(sub.status, expected)

    def test_running_again_does_nothing(self):
        self.make_subscription(40)
        auto_suspend_overdue_subscriptions()
        result = auto_suspend_overdue_subscriptions()
        self.assertEqual(result["suspended"], 0)
        self.assertEqual(self.suspension_logs().count(), 1)

    def test_one_failure_does_not_stop_the_others(self):
        self.make_subscription(40)
        self.make_subscription(41)
        calls = {"n": 0}

        def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("database hiccup")
            return real_change_status(*args, **kwargs)

        with mock.patch("subscriptions.tasks.change_status", side_effect=flaky):
            with self.assertLogs("celery.task", level="ERROR"):
                result = auto_suspend_overdue_subscriptions()
        self.assertEqual(result["suspended"], 1)
        self.assertEqual(result["errors"], 1)
        self.assertEqual(Subscription.objects.filter(status="Suspended").count(), 1)
