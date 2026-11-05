import inspect
import re
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from customers.models import Customer
from packages.models import ContractTerm, Package
from subscriptions.models import Subscription
from subscriptions.services import create_subscription

from . import queries
from .queries import revenue_by_package

REVENUE_URL = "/api/reports/revenue-summary/"
EXPIRING_URL = "/api/reports/expiring/"


class ReportsTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_data", verbosity=0)
        cls.today = timezone.localdate()
        cls.agent1 = User.objects.create_user("agent1", password="pw")
        cls.agent2 = User.objects.create_user("agent2", password="pw")
        cls.boss = User.objects.create_user("boss", password="pw", is_staff=True)
        cls.cust1 = cls.make_customer("one@x.co", cls.agent1)
        cls.cust2 = cls.make_customer("two@x.co", cls.agent2)
        cls.twelve = ContractTerm.objects.get(name="12-Month")

    @staticmethod
    def make_customer(email, agent):
        return Customer.objects.create(
            name=f"Customer {email}", email=email, phone="0821234567", address="1 Long St", agent=agent
        )

    @classmethod
    def make_subscription(cls, customer, package_name, status="Active", days_until_end=100):
        """Create a subscription with the service, ending days_until_end days from today.

        The service sets the end date to the installation date plus the term's length, so the
        installation date is worked out backwards. Prices come from the service (discounts
        included), so the tests below compare against the subscription's own monthly_total
        instead of a hard-coded number.
        """
        subscription = create_subscription(
            customer=customer,
            package=Package.objects.get(name=package_name),
            contract_term=cls.twelve,
            add_ons=[],
            installation_date=cls.today + timedelta(days=days_until_end - cls.twelve.duration_days),
            created_by=cls.boss,
        )
        Subscription.objects.filter(pk=subscription.pk).update(status=status)  # new ones start Pending
        return subscription

    def client_for(self, user=None):
        client = APIClient()
        if user:
            client.force_authenticate(user)
        return client


class RevenueSummaryTests(ReportsTestBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.standard_1 = cls.make_subscription(cls.cust1, "Home Standard")          # counted
        cls.standard_2 = cls.make_subscription(cls.cust2, "Home Standard")          # counted
        cls.basic = cls.make_subscription(cls.cust1, "Home Basic")                  # counted
        cls.make_subscription(cls.cust1, "Home Premium", status="Pending")         # not counted
        cls.make_subscription(cls.cust2, "Business Fibre", status="Suspended")     # not counted
        cls.make_subscription(cls.cust2, "Business Fibre", status="Cancelled")     # not counted
        cls.standard_total = cls.standard_1.monthly_total + cls.standard_2.monthly_total
        cls.active_total = cls.standard_total + cls.basic.monthly_total

    def test_admin_gets_active_revenue_grouped_by_package(self):  # BRD test case TC-09
        response = self.client_for(self.boss).get(REVENUE_URL)
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["total_monthly_revenue"], str(self.active_total))
        rows = {row["package"]: row for row in body["packages"]}
        self.assertEqual(rows["Home Standard"]["monthly_revenue"], str(self.standard_total))
        self.assertEqual(rows["Home Standard"]["active_subscriptions"], 2)
        self.assertEqual(rows["Home Basic"]["monthly_revenue"], str(self.basic.monthly_total))
        self.assertEqual(rows["Home Basic"]["active_subscriptions"], 1)

    def test_packages_without_active_subscriptions_are_listed_with_zero(self):
        rows = {r["package"]: r for r in self.client_for(self.boss).get(REVENUE_URL).json()["packages"]}
        self.assertEqual(set(rows), {"Home Basic", "Home Standard", "Home Premium", "Business Fibre"})
        self.assertEqual(rows["Home Premium"]["monthly_revenue"], "0.00")
        self.assertEqual(rows["Business Fibre"]["active_subscriptions"], 0)

    def test_highest_revenue_first(self):
        packages = self.client_for(self.boss).get(REVENUE_URL).json()["packages"]
        self.assertEqual([p["package"] for p in packages][:2], ["Home Standard", "Home Basic"])

    def test_only_admins_can_read_it(self):
        self.assertEqual(self.client_for(self.agent1).get(REVENUE_URL).status_code, 403)
        self.assertEqual(self.client_for().get(REVENUE_URL).status_code, 401)

    def test_sql_is_parameterised(self):
        # A value that would break out of a quoted string is treated as plain text.
        rows = revenue_by_package("Active' OR '1'='1")
        self.assertTrue(rows)
        self.assertTrue(all(Decimal(str(r["monthly_revenue"])) == 0 for r in rows))

    def test_query_source_has_a_placeholder_and_no_string_formatting(self):
        source = inspect.getsource(queries)
        self.assertIn("cursor.execute(", source)
        self.assertIn("%s", source)
        self.assertIsNone(re.search(r"""\bf["']""", source), "f-string found in queries.py")
        self.assertNotIn(".format(", source)


class ExpiringReportTests(ReportsTestBase):
    def test_window_status_and_order(self):
        soon = self.make_subscription(self.cust1, "Home Basic", days_until_end=10)
        sooner = self.make_subscription(self.cust1, "Home Standard", days_until_end=3)
        overdue = self.make_subscription(self.cust1, "Home Premium", days_until_end=-4)
        self.make_subscription(self.cust1, "Home Basic", days_until_end=45)                    # too far
        self.make_subscription(self.cust1, "Home Basic", status="Pending", days_until_end=5)   # not Active
        self.make_subscription(self.cust1, "Home Basic", status="Suspended", days_until_end=5)
        body = self.client_for(self.boss).get(EXPIRING_URL).json()
        self.assertEqual(body["count"], 3)
        self.assertEqual(
            [r["subscription_id"] for r in body["results"]],
            [str(overdue.pk), str(sooner.pk), str(soon.pk)],  # soonest first
        )
        self.assertEqual([r["days_left"] for r in body["results"]], [-4, 3, 10])
        first = body["results"][0]
        self.assertEqual(first["customer_name"], "Customer one@x.co")
        self.assertEqual(first["package_name"], "Home Premium")
        self.assertEqual(first["monthly_total"], str(overdue.monthly_total))

    def test_window_includes_day_30(self):
        self.make_subscription(self.cust1, "Home Basic", days_until_end=30)
        self.assertEqual(self.client_for(self.boss).get(EXPIRING_URL).json()["count"], 1)

    def test_agents_only_see_their_own_customers(self):
        self.make_subscription(self.cust1, "Home Basic", days_until_end=5)
        self.make_subscription(self.cust2, "Home Basic", days_until_end=6)
        self.assertEqual(self.client_for(self.agent1).get(EXPIRING_URL).json()["count"], 1)
        self.assertEqual(self.client_for(self.agent2).get(EXPIRING_URL).json()["count"], 1)
        self.assertEqual(self.client_for(self.boss).get(EXPIRING_URL).json()["count"], 2)

    def test_paginated_at_20(self):
        for _ in range(25):
            self.make_subscription(self.cust1, "Home Basic", days_until_end=5)
        client = self.client_for(self.boss)
        first = client.get(EXPIRING_URL).json()
        self.assertEqual((first["count"], len(first["results"])), (25, 20))
        self.assertIsNotNone(first["next"])
        self.assertEqual(len(client.get(EXPIRING_URL, {"page": 2}).json()["results"]), 5)

    def test_unauthenticated_is_refused(self):
        self.assertEqual(self.client_for().get(EXPIRING_URL).status_code, 401)