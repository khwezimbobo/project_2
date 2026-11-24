# Copy to alerts/test_api.py (replaces the earlier version)
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from customers.models import Customer
from packages.models import ContractTerm, Package
from subscriptions.services import create_subscription

from .models import RenewalAlert

User = get_user_model()
URL = "/api/alerts/"


class AlertApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_data", verbosity=0)
        cls.today = timezone.localdate()
        cls.agent1 = User.objects.create_user("agent1", password="pw", role="agent")
        cls.agent2 = User.objects.create_user("agent2", password="pw", role="agent")
        cls.boss = User.objects.create_user("boss", password="pw", role="admin")
        cls.cust1 = cls.make_customer("one@x.co", cls.agent1)
        cls.cust2 = cls.make_customer("two@x.co", cls.agent2)
        cls.alert1 = cls.make_alert(cls.cust1, days=2)
        cls.alert1b = cls.make_alert(cls.cust1, days=6)
        cls.alert2 = cls.make_alert(cls.cust2, days=4)

    @staticmethod
    def make_customer(email, agent):
        return Customer.objects.create(
            first_name=f"Customer {email}", email=email, phone_number="0821234567", address="1 Long St",
            assigned_agent=agent,
        )

    @classmethod
    def make_alert(cls, customer, days):
        term = ContractTerm.objects.get(name="12-Month")
        subscription = create_subscription(
            customer=customer,
            package=Package.objects.get(name="Home Basic"),
            contract_term=term,
            add_ons=[],
            installation_date=cls.today + timedelta(days=days - term.duration_days),
            created_by=cls.boss,
        )
        return RenewalAlert.objects.create(
            subscription=subscription, days_until_expiry=days, alert_date=cls.today
        )

    def client_for(self, user=None):
        client = APIClient()
        if user:
            client.force_authenticate(user)
        return client

    def ack_url(self, alert):
        return f"{URL}{alert.pk}/acknowledge/"

    # ---- list ----
    def test_agent_only_sees_alerts_for_their_own_customers(self):
        # Only the role decides what a user can see. Even an agent with the staff flag set must
        # not see other agents' alerts.
        staff_agent = User.objects.create_user("staff_agent", password="pw", role="agent", is_staff=True)
        # Use the actual UUID strings from your setup objects
        expected_agent1_subs = {str(self.alert1.subscription_id), str(self.alert1b.subscription_id)}
        expected_agent2_subs = {str(self.alert2.subscription_id)}
        expected_staff_subs = set()

        # Define all test cases
        tests = [
            (self.agent1, expected_agent1_subs, "agent1"),
            (self.agent2, expected_agent2_subs, "agent2"),
            (staff_agent, expected_staff_subs, "staff_agent"),
        ]

        for user, expected_subs, username in tests:
            response = self.client_for(user).get(URL).json()
            actual_subs = {row["subscription"] for row in response["results"]}
            # FIX: Both sides of comparison MUST be strings
            self.assertEqual(actual_subs, expected_subs, f"User {username} sees incorrect subscriptions")

    def test_lists_are_scoped_and_most_urgent_first(self):
        agent1 = self.client_for(self.agent1).get(URL).json()
        self.assertEqual(agent1["count"], 2)
        self.assertEqual([a["days_until_expiry"] for a in agent1["results"]], [2, 6])
        self.assertEqual(self.client_for(self.agent2).get(URL).json()["count"], 1)
        self.assertEqual(self.client_for(self.boss).get(URL).json()["count"], 3)

    def test_list_shows_useful_fields(self):
        # Dynamically get the subscription ID from the alert we created in setUpTestData
        expected_sub_id = str(self.alert1.subscription_id)
        row = self.client_for(self.agent1).get(URL).json()["results"][0]
        # FIX: Use the dynamic ID instead of the hardcoded ID ('9a66da7f...')
        self.assertEqual(row["subscription"], expected_sub_id,
                         "Subscription ID in response does not match the created alert's subscription")
        # Now the rest of your assertions should pass:
        self.assertEqual(row["package_name"], "Home Basic")
        self.assertEqual(row["status"], "Pending")
        self.assertIsNone(row["acknowledged_by"])

    def test_status_filter(self):
        RenewalAlert.objects.filter(pk=self.alert1.pk).update(status="Acknowledged")
        agent = self.client_for(self.agent1)
        self.assertEqual(agent.get(URL, {"status": "Pending"}).json()["count"], 1)
        self.assertEqual(agent.get(URL, {"status": "Acknowledged"}).json()["count"], 1)
        response = agent.get(URL, {"status": "Bogus"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("status", response.json())

    def test_unauthenticated_is_refused(self):
        self.assertEqual(self.client_for().get(URL).status_code, 401)

    # ---- acknowledge ----
    def test_agent_acknowledges_own_alert(self):
        response = self.client_for(self.agent1).patch(self.ack_url(self.alert1))
        self.assertEqual(response.status_code, 200, response.json())
        body = response.json()
        self.assertEqual(body["status"], "Acknowledged")
        self.assertEqual(body["acknowledged_by"], self.agent1.pk)
        self.assertEqual(body["acknowledged_by_username"], "agent1")
        self.assertIsNotNone(body["acknowledged_at"])
        self.alert1.refresh_from_db()
        self.assertEqual(self.alert1.status, "Acknowledged")

    def test_acknowledging_twice_is_a_400(self):
        agent = self.client_for(self.agent1)
        agent.patch(self.ack_url(self.alert1))
        response = agent.patch(self.ack_url(self.alert1))
        self.assertEqual(response.status_code, 400)
        self.assertIn("already been acknowledged", response.json()["status"][0])

    def test_other_agents_alert_is_a_403_and_unchanged(self):
        response = self.client_for(self.agent2).patch(self.ack_url(self.alert1))
        self.assertEqual(response.status_code, 403)
        self.alert1.refresh_from_db()
        self.assertEqual(self.alert1.status, "Pending")

    def test_admin_can_acknowledge_any_alert(self):
        response = self.client_for(self.boss).patch(self.ack_url(self.alert2))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["acknowledged_by"], self.boss.pk)

    def test_unauthenticated_cannot_acknowledge(self):
        self.assertEqual(self.client_for().patch(self.ack_url(self.alert1)).status_code, 401)

    def test_alerts_cannot_be_created_edited_or_deleted_through_the_api(self):
        admin = self.client_for(self.boss)
        self.assertEqual(admin.post(URL, {}, format="json").status_code, 405)
        self.assertEqual(admin.put(f"{URL}{self.alert1.pk}/", {}, format="json").status_code, 405)
        self.assertEqual(admin.patch(f"{URL}{self.alert1.pk}/", {}, format="json").status_code, 405)
        self.assertEqual(admin.delete(f"{URL}{self.alert1.pk}/").status_code, 405)
