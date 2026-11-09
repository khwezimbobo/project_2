"""
Tests for the staff dashboard (/dashboard/) and the login page (/accounts/login/) - ISP-49.
"""

from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from alerts.models import RenewalAlert
from customers.models import Customer
from packages.models import ContractTerm, Package
from subscriptions.models import SubscriptionStatus
from subscriptions.services import change_status, create_subscription

User = get_user_model()   # the project's user model (customers.User)


class DashboardPageTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_user("manager", password="pass12345", role="admin", is_staff=True)
        self.agent = User.objects.create_user("agent", password="pass12345", role="agent", is_staff=True)

    def test_logged_out_users_are_sent_to_login(self):
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/accounts/login/"))
        self.assertIn("next=/dashboard/", response["Location"])   # comes back here after login

    def test_support_agents_get_403(self):
        # BRD section 12: the dashboard is Admin only.
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get("/dashboard/").status_code, 403)

    def test_admins_see_the_dashboard_with_kpi_cards(self):
        self.client.force_login(self.admin)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/index.html")
        self.assertTemplateUsed(response, "base.html")             # shared layout
        for label in ["Active subscribers", "Monthly revenue", "Pending renewal alerts"]:
            self.assertContains(response, label)
        self.assertContains(response, "bootstrap@5")                # Bootstrap 5 CDN
        self.assertContains(response, "Signed in as")


class DashboardKpiTests(TestCase):
    """ISP-26: the dashboard shows real numbers from the database."""

    def setUp(self):
        call_command("seed_data", stdout=StringIO())   # packages, terms and add-ons
        self.admin = User.objects.create_user("manager", password="pass12345", role="admin", is_staff=True)
        self.agent = User.objects.create_user("agent", password="pass12345", role="agent", is_staff=True)
        self.customer = Customer.objects.create(
            first_name="Thandi", last_name="Mokoena", email="thandi@example.com",
            phone_number="0821234567", address="1 Main Rd", assigned_agent=self.agent,
        )
        self.basic = Package.objects.get(name="Home Basic")
        self.monthly = ContractTerm.objects.get(name="Month-to-Month")   # 30-day contract
        self.twelve = ContractTerm.objects.get(name="12-Month")          # 365-day contract
        self.client.force_login(self.admin)

    def make(self, term, ends_in_days, active=True):
        """Create a subscription whose contract ends `ends_in_days` from today."""
        today = timezone.localdate()
        installed = today + timedelta(days=ends_in_days - term.duration_days)
        sub = create_subscription(
            customer=self.customer, package=self.basic, contract_term=term, add_ons=[],
            installation_date=installed, created_by=self.agent,
        )
        if active:
            change_status(sub, SubscriptionStatus.ACTIVE, changed_by=self.admin, notes="Installed")
        return sub

    def test_numbers_come_from_active_subscriptions_only(self):
        soon = self.make(self.monthly, ends_in_days=5)          # Active, ends in 5 days
        later = self.make(self.twelve, ends_in_days=200)        # Active, outside the 30-day window
        self.make(self.monthly, ends_in_days=10, active=False)  # Pending: not counted anywhere

        context = self.client.get("/dashboard/").context
        self.assertEqual(context["active_count"], 2)
        self.assertEqual(context["monthly_revenue"], soon.monthly_total + later.monthly_total)
        self.assertEqual([s.pk for s in context["expiring_subscriptions"]], [soon.pk])
        self.assertEqual(context["expiring_subscriptions"][0].days_left, 5)

    def test_expiring_table_shows_time_left(self):
        self.make(self.monthly, ends_in_days=3)
        self.make(self.monthly, ends_in_days=-4)   # ended, still Active (waiting for auto-suspend)
        response = self.client.get("/dashboard/")
        self.assertContains(response, "Thandi Mokoena")
        self.assertContains(response, "3 days")
        self.assertContains(response, "Ended 4 days ago")

    def test_pending_alerts_are_counted(self):
        sub = self.make(self.monthly, ends_in_days=6)
        RenewalAlert.objects.create(subscription=sub, days_until_expiry=6, alert_date=timezone.localdate())
        self.assertEqual(self.client.get("/dashboard/").context["pending_alerts"], 1)

    def test_empty_database_shows_zeros_and_the_empty_message(self):
        response = self.client.get("/dashboard/")
        self.assertEqual(response.context["active_count"], 0)
        self.assertEqual(response.context["monthly_revenue"], Decimal("0.00"))
        self.assertContains(response, "Nothing to renew yet.")


class LoginPageTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_user("manager", password="pass12345", role="admin", is_staff=True)

    def test_login_page_renders(self):
        response = self.client.get("/accounts/login/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")
        self.assertContains(response, "Staff login")

    def test_correct_login_goes_to_the_dashboard(self):
        response = self.client.post("/accounts/login/", {"username": "manager", "password": "pass12345"})
        self.assertRedirects(response, "/dashboard/")

    def test_wrong_password_shows_an_error(self):
        response = self.client.post("/accounts/login/", {"username": "manager", "password": "nope"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "alert-danger")