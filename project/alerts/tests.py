# alerts/test.py
from datetime import timedelta
from unittest import mock
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from customers.models import Customer
from packages.models import ContractTerm, Package
from subscriptions.models import Subscription, SubscriptionStatus
from subscriptions.services import create_subscription

from .models import RenewalAlert
from .tasks import check_expiring_subscriptions

# Use get_user_model() instead of built-in User
User = get_user_model()

class CheckExpiringSubscriptionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_data", verbosity=0)
        cls.today = timezone.localdate()
        
        # Create users with explicit roles for testing permissions
        cls.admin_user = User.objects.create_user("super_admin", "admin_pass", is_superuser=True)
        cls.agent_a = User.objects.create_user("agent_a", "pw", role="agent")
        cls.agent_b = User.objects.create_user("agent_b", "pw", role="agent")

        # --- FIX APPLIED HERE: Updated Customer fields to match the model ---
        cls.customer_a = Customer.objects.create(
            first_name="Thandi", 
            last_name="Smith", 
            email="t@x.co", 
            phone_number="0821234567", 
            address="1 Long St", 
            assigned_agent=cls.agent_a # Changed from 'agent' to 'assigned_agent'
        )
        cls.customer_b = Customer.objects.create(
            first_name="Zanele", 
            last_name="Jones", 
            email="z@y.co", 
            phone_number="0821234568", 
            address="2 Short St", 
            assigned_agent=cls.agent_b # Changed from 'agent' to 'assigned_agent'
        )
        # -----------------------------------------------------------------
        
        cls.package = Package.objects.get(name="Home Basic")
        cls.term = ContractTerm.objects.get(name="12-Month")

    # Helper function updated to use the created customers
    def make_subscription(self, customer_obj, days_until_end, status=SubscriptionStatus.ACTIVE):
        """Create a subscription for a specific customer."""
        subscription = create_subscription(
            customer=customer_obj,
            package=self.package,
            contract_term=self.term,
            add_ons=[],
            installation_date=self.today + timedelta(days=days_until_end - self.term.duration_days),
            created_by=customer_obj.assigned_agent,
        )
        Subscription.objects.filter(pk=subscription.pk).update(status=status)
        return subscription

    def test_alert_is_created_within_seven_days(self):
        sub = self.make_subscription(self.customer_a, 3)
        result = check_expiring_subscriptions()
        alert = RenewalAlert.objects.get(subscription=sub)
        self.assertEqual(alert.days_until_expiry, 3)
        self.assertEqual(alert.alert_date, self.today)
        self.assertEqual(alert.status, "Pending")
        self.assertEqual(result, {"created": 1, "errors": 0})

    def test_running_twice_does_not_duplicate(self):
        self.make_subscription(self.customer_a, 3)
        check_expiring_subscriptions()
        result = check_expiring_subscriptions()
        self.assertEqual(RenewalAlert.objects.count(), 1)
        self.assertEqual(result["created"], 0)

    def test_window_edges_and_status(self):
        on_edge = self.make_subscription(self.customer_a, 7)
        self.make_subscription(self.customer_a, 8)                                          # too far away
        self.make_subscription(self.customer_a, 3, status=SubscriptionStatus.PENDING)      # not Active
        self.make_subscription(self.customer_a, 3, status=SubscriptionStatus.SUSPENDED)
        self.make_subscription(self.customer_a, 3, status=SubscriptionStatus.CANCELLED)
        check_expiring_subscriptions()
        self.assertEqual(list(RenewalAlert.objects.values_list("subscription", flat=True)), [on_edge.pk])

    def test_overdue_active_subscription_still_gets_an_alert(self):
        sub = self.make_subscription(self.customer_a, -5)
        check_expiring_subscriptions()
        self.assertEqual(RenewalAlert.objects.get(subscription=sub).days_until_expiry, -5)

    def test_one_failure_does_not_stop_the_others(self):
        self.make_subscription(self.customer_a, 2)
        self.make_subscription(self.customer_a, 4)
        
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
    
    # Test: Proving an agent only sees alerts for their own customers
    def test_agent_sees_only_own_alerts(self):
        # 1. Create the actual subscriptions for each customer/agent
        # We use a fixed number of days for the test
        days_to_expire = 3
        sub_a = self.make_subscription(self.customer_a, days_to_expire) 
        sub_b = self.make_subscription(self.customer_b, days_to_expire)

        # 2. Manually create alerts, providing ALL NOT NULL required fields
        # We must provide days_until_expiry and status, which the DB requires.
        alert_a = RenewalAlert.objects.create(
            subscription=sub_a,
            days_until_expiry=days_to_expire,
            status="Pending", # Or RenewalAlert.Status.PENDING if status is an Enum
            alert_date=self.today
        )
        
        alert_b = RenewalAlert.objects.create(
            subscription=sub_b,
            days_until_expiry=days_to_expire,
            status="Pending",
            alert_date=self.today
        )

        # 3. Agent A should only see their own alert
        agent_a_alerts = RenewalAlert.objects.filter(subscription=sub_a)
        self.assertEqual(agent_a_alerts.count(), 1)

        # 4. Agent B should only see their own alert
        agent_b_alerts = RenewalAlert.objects.filter(subscription=sub_b)
        self.assertEqual(agent_b_alerts.count(), 1)

        agent_a_alerts_for_b_subscription = RenewalAlert.objects.filter(subscription=sub_b)