# testing - tasks.py
from datetime import timedelta
from unittest import mock
 
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
 
from customers.models import Customer
from packages.models import ContractTerm, Package
from subscriptions.models import Subscription, SubscriptionStatus
from subscriptions.services import create_subscription

from .models import RenewalAlert
from .tasks import check_expiring_subscriptions
 
 
class CheckExpiringSubscriptionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_data", verbosity=0)
        cls.today = timezone.localdate()
        cls.agent = User.objects.create_user("agent", password="pw")
        cls.customer = Customer.objects.create(
            name="Thandi", email="t@x.co", phone="0821234567", address="1 Long St", agent=cls.agent
        )
        cls.package = Package.objects.get(name="Home Basic")
        cls.term = ContractTerm.objects.get(name="12-Month")

    def make_subscription(self, days_until_end, status=SubscriptionStatus.ACTIVE):
        """Create a subscription with the service, ending days_until_end days from today.
 
        The service sets the end date to the installation date plus the term's length, so the
        installation date is worked out backwards from the end date we want.
        """
        subscription = create_subscription(
            customer=self.customer,
            package=self.package,
            contract_term=self.term,
            add_ons=[],
            installation_date=self.today + timedelta(days=days_until_end - self.term.duration_days),
            created_by=self.agent,
        )
        Subscription.objects.filter(pk=subscription.pk).update(status=status)  # new ones start Pending
        return subscription

    def test_alert_is_created_within_seven_days(self):
        sub = self.make_subscription(3)
        result = check_expiring_subscriptions()
        alert = RenewalAlert.objects.get(subscription=sub)
        self.assertEqual(alert.days_until_expiry, 3)
        self.assertEqual(alert.alert_date, self.today)
        self.assertEqual(alert.status, "Pending")
        self.assertEqual(result, {"created": 1, "errors": 0})
 
    def test_running_twice_does_not_duplicate(self):
        self.make_subscription(3)
        check_expiring_subscriptions()
        result = check_expiring_subscriptions()
        self.assertEqual(RenewalAlert.objects.count(), 1)
        self.assertEqual(result["created"], 0)
 
    def test_window_edges_and_status(self):
        on_edge = self.make_subscription(7)
        self.make_subscription(8)                                          # too far away
        self.make_subscription(3, status=SubscriptionStatus.PENDING)      # not Active
        self.make_subscription(3, status=SubscriptionStatus.SUSPENDED)
        self.make_subscription(3, status=SubscriptionStatus.CANCELLED)
        check_expiring_subscriptions()
        self.assertEqual(list(RenewalAlert.objects.values_list("subscription", flat=True)), [on_edge.pk])
 
    def test_overdue_active_subscription_still_gets_an_alert(self):
        sub = self.make_subscription(-5)
        check_expiring_subscriptions()
        self.assertEqual(RenewalAlert.objects.get(subscription=sub).days_until_expiry, -5)
 
    def test_one_failure_does_not_stop_the_others(self):
        self.make_subscription(2)
        self.make_subscription(4)
        real = RenewalAlert.objects.get_or_create
        calls = {"n": 0}
 
        def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("database hiccup")
            return real(*args, **kwargs)
 
        with mock.patch.object(RenewalAlert.objects, "get_or_create", side_effect=flaky):
            with self.assertLogs("celery.task", level="ERROR"):
                result = check_expiring_subscriptions()
        self.assertEqual(result, {"created": 1, "errors": 1})
        self.assertEqual(RenewalAlert.objects.count(), 1)
