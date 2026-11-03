"""
API tests for POST/GET /api/subscriptions/ (ISP-69).

Unlike the pricing tests in tests.py, these use APITestCase, which creates a
temporary test database, so they test the full path:
request -> serializer -> PricingService -> database -> JSON response.

Run with:
    docker compose exec django python manage.py test subscriptions --settings=project.settings.test
"""

from io import StringIO   # A "fake file" to swallow the seed command's printed output

from django.contrib.auth.models import Group, User
from django.core.management import call_command   # Lets a test run a manage.py command
from rest_framework import status                 # Named HTTP codes, e.g. status.HTTP_201_CREATED
from rest_framework.test import APITestCase       # TestCase plus an API client (self.client)

from customers.models import Customer
from packages.models import AddOn, ContractTerm, Package

from .models import Subscription, SubscriptionAuditLog


class CreateSubscriptionApiTests(APITestCase):
    """POST /api/subscriptions/ - pricing and dates are calculated on the server."""

    def setUp(self):
        # setUp runs before EVERY test, and each test gets a fresh, empty database, so tests can't affect each other.

        # Load the real BRD catalogue: 4 packages, 3 contract terms, 3 add-ons.
        call_command("seed_data", stdout=StringIO())

        # Two Support Agents, so we can test that one can't touch the other's customers.
        self.agent = User.objects.create_user(username="agent", password="pass12345")
        self.other_agent = User.objects.create_user(username="other", password="pass12345")

        # Example customer belonging to self.agent (not other_agent).
        self.customer = Customer.objects.create(
            name="Thandi", email="thandi@example.com", phone="0821234567",
            address="1 Main Rd", agent=self.agent,
        )

        # Look up the catalogue rows used in the worked example.
        self.package = Package.objects.get(name="Home Standard")   # R699
        self.term = ContractTerm.objects.get(name="12-Month")      # x1.00, 365 days
        self.static_ip = AddOn.objects.get(name="Static IP")       # R100
        self.router = AddOn.objects.get(name="Router Rental")      # R150

        # Log the test client in as self.agent - skips the real login/JWT step.
        self.client.force_authenticate(user=self.agent)

    def payload(self, **extra):
        """A valid request body; pass keyword arguments to add or override fields.

        Only these 5 fields are inputs - everything else is calculated by the server.
        """
        data = {
            "customer": self.customer.id,
            "package": self.package.package_id,
            "contract_term": self.term.contract_term_id,
            "add_ons": [self.static_ip.add_on_id, self.router.add_on_id],
            "installation_date": "2026-11-01",
        }
        data.update(extra)   # e.g. payload(monthly_total="1.00") adds a fake price
        return data

    # --- Creating a subscription --------------------------------------------

    def test_create_calculates_pricing_and_dates(self):
        # The worked example from docs/erd.md (BRD test case TC-02).
        response = self.client.post("/api/subscriptions/", self.payload(), format="json")
        # Third argument: if this fails, print the response so we can see why.
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["subtotal"], "949.00")             # 699 + 100 + 150
        self.assertEqual(response.data["discount_name"], "New Customer")  # first subscription
        self.assertEqual(response.data["monthly_total"], "854.10")        # 949 - 10%
        self.assertEqual(response.data["first_month_total"], "1354.10")   # + R500 installation
        self.assertEqual(response.data["contract_start_date"], "2026-11-01")  # = installation date
        self.assertEqual(response.data["contract_end_date"], "2027-11-01")    # + 365 days
        self.assertEqual(response.data["status"], "Pending")              # every new subscription starts Pending
        self.assertEqual(len(response.data["add_on_details"]), 2)         # both add-ons saved

    def test_client_sent_pricing_is_ignored(self):
        # BRD 18: prices and dates from the client must be ignored.
        # Try to cheat: send a R1 price, a far-future end date and an Active status.
        response = self.client.post("/api/subscriptions/", self.payload(
            monthly_total="1.00", contract_end_date="2099-01-01", status="Active",
        ), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # The server's own values win.
        self.assertEqual(response.data["monthly_total"], "854.10")
        self.assertEqual(response.data["contract_end_date"], "2027-11-01")
        self.assertEqual(response.data["status"], "Pending")

    def test_creation_is_logged_in_audit_log(self):
        # FR-09: creating a subscription writes its first audit log entry.
        response = self.client.post("/api/subscriptions/", self.payload(), format="json")
        log = SubscriptionAuditLog.objects.get(subscription_id=response.data["subscription_id"])
        self.assertEqual(log.new_status, "Pending")
        self.assertEqual(log.changed_by, self.agent)   # records WHO created it

    def test_second_subscription_is_not_new_customer(self):
        # The New Customer discount only applies to a customer's FIRST subscription.
        self.client.post("/api/subscriptions/", self.payload(), format="json")
        response = self.client.post("/api/subscriptions/", self.payload(), format="json")
        # Not new any more; 2 add-ons -> Multi Add-On 5% of 949 = 47.45.
        self.assertEqual(response.data["discount_name"], "Multi Add-On")
        self.assertEqual(response.data["discount_amount"], "47.45")

    # --- Security: who can create and see what (BRD 8.2, 15) ---------------

    def test_agent_cannot_create_for_another_agents_customer(self):
        # Switch to the OTHER agent and try to use self.agent's customer.
        self.client.force_authenticate(user=self.other_agent)
        response = self.client.post("/api/subscriptions/", self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("customer", response.data)               # error points at the customer field
        self.assertEqual(Subscription.objects.count(), 0)      # nothing was saved

    def test_agents_only_see_their_own_subscriptions(self):
        # self.agent creates one; other_agent should see an empty list (IDOR prevention).
        self.client.post("/api/subscriptions/", self.payload(), format="json")
        self.client.force_authenticate(user=self.other_agent)
        response = self.client.get("/api/subscriptions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
        # NOTE: once pagination is on (Khwezi's PR #21), use len(response.data["results"]).

    def test_admin_sees_all_subscriptions(self):
        # A user in the "Admin" group sees every agent's subscriptions.
        self.client.post("/api/subscriptions/", self.payload(), format="json")
        admin = User.objects.create_user(username="boss", password="pass12345")
        admin.groups.add(Group.objects.create(name="Admin"))
        self.client.force_authenticate(user=admin)
        response = self.client.get("/api/subscriptions/")
        self.assertEqual(len(response.data), 1)
        # NOTE: once pagination is on, use len(response.data["results"]).

    # --- Validation and login -----------------------------------------------

    def test_missing_fields_return_400(self):
        # An empty request must fail with a 400 that names every missing required field.
        response = self.client.post("/api/subscriptions/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for field in ["customer", "package", "contract_term", "installation_date"]:
            self.assertIn(field, response.data)

    def test_login_required(self):
        # force_authenticate(user=None) logs the client out.
        self.client.force_authenticate(user=None)
        response = self.client.post("/api/subscriptions/", self.payload(), format="json")
        # 403 with session login today; 401 once JWT is the default (FR-16). Both mean "refused".
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])