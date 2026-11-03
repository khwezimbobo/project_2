"""
Tests for the subscription list filters, pagination and the audit log endpoint.
Covers FR-15, TC-08, BRD 8.2 (20 per page) and BRD 18 (invalid filters return 400).
"""

from datetime import date
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APITestCase

from customers.models import Customer
from packages.models import ContractTerm, Package

from .models import SubscriptionStatus
from .services import change_status, create_subscription

LIST_URL = "/api/subscriptions/"


class FilterAndLogsTests(APITestCase):

    def setUp(self):
        call_command("seed_data", stdout=StringIO())
        self.admin = User.objects.create_user(username="boss", password="pass12345")
        self.admin.groups.add(Group.objects.create(name="Admin"))
        self.agent = User.objects.create_user(username="agent", password="pass12345")
        self.other_agent = User.objects.create_user(username="other", password="pass12345")
        self.customer = Customer.objects.create(
            name="Thandi", email="thandi@example.com", phone="0821234567",
            address="1 Main Rd", agent=self.agent,
        )
        self.basic = Package.objects.get(name="Home Basic")
        self.premium = Package.objects.get(name="Home Premium")
        self.twelve = ContractTerm.objects.get(name="12-Month")
        self.monthly = ContractTerm.objects.get(name="Month-to-Month")
        self.client.force_authenticate(user=self.admin)

    def make(self, package, term, new_status=None):
        """Create a subscription (starts Pending) and optionally move it to Active."""
        sub = create_subscription(
            customer=self.customer, package=package, contract_term=term, add_ons=[],
            installation_date=date(2026, 11, 1), created_by=self.agent,
        )
        if new_status == SubscriptionStatus.ACTIVE:
            change_status(sub, SubscriptionStatus.ACTIVE, changed_by=self.admin, notes="Installed")
        return sub

    # --- Filters (FR-15, TC-08) -------------------------------------------------

    def test_filter_by_status_and_package(self):
        # TC-08: ?status=Active&package=<id> returns only Active subscriptions on that package.
        wanted = self.make(self.basic, self.twelve, SubscriptionStatus.ACTIVE)
        self.make(self.basic, self.twelve)                               # Pending - excluded
        self.make(self.premium, self.twelve, SubscriptionStatus.ACTIVE)  # other package - excluded
        response = self.client.get(LIST_URL, {"status": "Active", "package": self.basic.package_id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["subscription_id"], str(wanted.subscription_id))

    def test_filter_by_contract_term(self):
        self.make(self.basic, self.twelve)
        self.make(self.basic, self.monthly)
        response = self.client.get(LIST_URL, {"contract_term": self.monthly.contract_term_id})
        self.assertEqual(response.data["count"], 1)

    def test_no_filters_returns_everything(self):
        self.make(self.basic, self.twelve)
        self.make(self.premium, self.monthly)
        self.assertEqual(self.client.get(LIST_URL).data["count"], 2)

    def test_invalid_status_returns_400(self):
        response = self.client.get(LIST_URL, {"status": "Paused"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_unknown_package_returns_400(self):
        for bad in ["999", "abc"]:   # doesn't exist / not a number
            response = self.client.get(LIST_URL, {"package": bad})
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("package", response.data)

    # --- Pagination (BRD 8.2) ---------------------------------------------------

    def test_list_is_paginated_at_20(self):
        for _ in range(25):
            self.make(self.basic, self.twelve)
        first = self.client.get(LIST_URL)
        self.assertEqual(first.data["count"], 25)
        self.assertEqual(len(first.data["results"]), 20)
        self.assertIsNotNone(first.data["next"])
        second = self.client.get(LIST_URL, {"page": 2})
        self.assertEqual(len(second.data["results"]), 5)

    # --- Audit log endpoint -----------------------------------------------------

    def test_logs_show_history_newest_first(self):
        sub = self.make(self.basic, self.twelve, SubscriptionStatus.ACTIVE)
        change_status(sub, SubscriptionStatus.SUSPENDED, notes="Auto-suspended")   # by "System"
        response = self.client.get(f"{LIST_URL}{sub.subscription_id}/logs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual([r["new_status"] for r in results], ["Suspended", "Active", "Pending"])
        self.assertEqual(results[0]["changed_by"], "System")
        self.assertEqual(results[1]["changed_by"], "boss")
        self.assertEqual(results[2]["notes"], "Subscription created")

    def test_agent_can_see_logs_for_own_customer(self):
        sub = self.make(self.basic, self.twelve)
        self.client.force_authenticate(user=self.agent)
        response = self.client.get(f"{LIST_URL}{sub.subscription_id}/logs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_other_agent_gets_404_for_logs(self):
        # IDOR: another agent's subscription doesn't exist as far as they can tell.
        sub = self.make(self.basic, self.twelve)
        self.client.force_authenticate(user=self.other_agent)
        response = self.client.get(f"{LIST_URL}{sub.subscription_id}/logs/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)