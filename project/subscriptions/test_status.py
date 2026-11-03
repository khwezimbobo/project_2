"""
Tests for PATCH /api/subscriptions/{id}/status/ and the change_status() service.
Covers FR-08 (Admin only), FR-09 (audit log), BRD 18 (allowed transitions) and TC-03.
"""

from datetime import date
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APITestCase

from customers.models import Customer
from packages.models import ContractTerm, Package

from .models import SubscriptionAuditLog, SubscriptionStatus
from .services import InvalidStatusTransition, change_status, create_subscription


class StatusChangeTests(APITestCase):
    """PATCH /api/subscriptions/{id}/status/ (FR-08, FR-09, BRD 18, TC-03)."""

    def setUp(self):
        call_command("seed_data", stdout=StringIO())
        # An Admin (in the "Admin" group) and a Support Agent.
        self.admin = User.objects.create_user(username="boss", password="pass12345")
        self.admin.groups.add(Group.objects.create(name="Admin"))
        self.agent = User.objects.create_user(username="agent", password="pass12345")
        customer = Customer.objects.create(
            name="Thandi", email="thandi@example.com", phone="0821234567",
            address="1 Main Rd", agent=self.agent,
        )
        # A real subscription, created the same way the API does (starts Pending).
        self.subscription = create_subscription(
            customer=customer,
            package=Package.objects.get(name="Home Basic"),
            contract_term=ContractTerm.objects.get(name="12-Month"),
            add_ons=[],
            installation_date=date(2026, 11, 1),
            created_by=self.agent,
        )
        self.url = f"/api/subscriptions/{self.subscription.subscription_id}/status/"
        self.client.force_authenticate(user=self.admin)

    def test_admin_can_activate_and_it_is_logged(self):
        response = self.client.patch(self.url, {"status": "Active", "notes": "Installed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["status"], "Active")
        # The newest audit log entry records the change, who made it and the note.
        log = SubscriptionAuditLog.objects.filter(subscription=self.subscription).order_by("-timestamp").first()
        self.assertEqual((log.old_status, log.new_status), ("Pending", "Active"))
        self.assertEqual(log.changed_by, self.admin)
        self.assertEqual(log.notes, "Installed")

    def test_cancelled_cannot_be_reactivated(self):
        # TC-03: an invalid transition returns 400 with a clear message.
        self.client.patch(self.url, {"status": "Cancelled"}, format="json")
        response = self.client.patch(self.url, {"status": "Active"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cancelled", str(response.data["status"]))

    def test_pending_cannot_jump_to_suspended(self):
        response = self.client.patch(self.url, {"status": "Suspended"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.subscription.refresh_from_db()                     # Re-read from the database
        self.assertEqual(self.subscription.status, "Pending")   # unchanged

    def test_suspended_can_go_back_to_active(self):
        for new in ["Active", "Suspended", "Active"]:
            response = self.client.patch(self.url, {"status": new}, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        # 1 creation entry + 3 changes.
        self.assertEqual(SubscriptionAuditLog.objects.filter(subscription=self.subscription).count(), 4)

    def test_unknown_status_returns_400(self):
        response = self.client.patch(self.url, {"status": "Paused"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_support_agent_cannot_change_status(self):
        # FR-08: Admin only - even for the agent's own customer.
        self.client.force_authenticate(user=self.agent)
        response = self.client.patch(self.url, {"status": "Active"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_service_used_by_celery_logs_system_change(self):
        # Khwezi's auto-suspend task can call change_status() with no user.
        change_status(self.subscription, SubscriptionStatus.ACTIVE)
        change_status(self.subscription, SubscriptionStatus.SUSPENDED, notes="Auto-suspended")
        log = SubscriptionAuditLog.objects.filter(subscription=self.subscription).order_by("-timestamp").first()
        self.assertIsNone(log.changed_by)              # None = "System"
        self.assertEqual(log.new_status, "Suspended")
        # The same rules apply to automatic changes.
        with self.assertRaises(InvalidStatusTransition):
            change_status(self.subscription, SubscriptionStatus.PENDING)