"""
API tests for Person A.

    TC-01  JWT login
    TC-04  an agent is blocked from another agent's records
    TC-05  requests without a token are rejected
"""
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from customers.models import Customer

from .helpers import PASSWORD, make_customer, make_user


class CustomerApiTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("admin1", role="admin")
        cls.agent1 = make_user("agent1", role="agent")
        cls.agent2 = make_user("agent2", role="agent")
        cls.no_role = make_user("norole", role="")

        cls.customer1 = make_customer(cls.agent1, "Alice", email="alice@example.com")
        cls.customer2 = make_customer(cls.agent2, "Bob", email="bob@example.com")

    def setUp(self):
        # Throttle counters live in the cache; start every test from zero.
        cache.clear()

    def authenticate(self, user):
        """Send this user's JWT access token with every following request."""
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def payload(self, **extra):
        """Valid customer data; extra keys override the defaults."""
        data = {
            "first_name": "New",
            "last_name": "Customer",
            "email": "new@example.com",
            "phone": "083 123 4567",
            "address": "5 Test Street",
        }
        data.update(extra)
        return data

    # ------------------------------------------------------------------
    # TC-01: JWT login
    # ------------------------------------------------------------------
    def test_tc01_login_returns_access_and_refresh_tokens(self):
        response = self.client.post(
            reverse("api_login"), {"username": "agent1", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_tc01_login_with_wrong_password_is_rejected(self):
        response = self.client.post(
            reverse("api_login"), {"username": "agent1", "password": "wrong-password"}
        )
        self.assertEqual(response.status_code, 401)

    def test_tc01_issued_token_works_on_the_api(self):
        login = self.client.post(
            reverse("api_login"), {"username": "agent1", "password": PASSWORD}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        response = self.client.get(reverse("customer-list"))
        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------
    # TC-04: blocked agent access
    # ------------------------------------------------------------------
    def test_tc04_agent_list_contains_only_own_customers(self):
        self.authenticate(self.agent1)
        response = self.client.get(reverse("customer-list"))
        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [str(self.customer1.pk)])

    def test_tc04_agent_cannot_read_another_agents_customer(self):
        self.authenticate(self.agent1)
        response = self.client.get(reverse("customer-detail", args=[self.customer2.pk]))
        self.assertEqual(response.status_code, 403)

    def test_tc04_agent_cannot_edit_another_agents_customer(self):
        self.authenticate(self.agent1)
        response = self.client.patch(
            reverse("customer-detail", args=[self.customer2.pk]), {"first_name": "Hacked"}
        )
        self.assertEqual(response.status_code, 403)
        self.customer2.refresh_from_db()
        self.assertEqual(self.customer2.first_name, "Bob")

    def test_tc04_agent_cannot_delete_another_agents_customer(self):
        self.authenticate(self.agent1)
        response = self.client.delete(reverse("customer-detail", args=[self.customer2.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Customer.objects.filter(pk=self.customer2.pk).exists())

    def test_tc04_user_without_role_is_blocked(self):
        self.authenticate(self.no_role)
        response = self.client.get(reverse("customer-list"))
        self.assertEqual(response.status_code, 403)

    def test_admin_sees_every_customer(self):
        self.authenticate(self.admin)
        response = self.client.get(reverse("customer-list"))
        self.assertEqual(response.data["count"], 2)

    def test_agent_can_read_own_customer(self):
        self.authenticate(self.agent1)
        response = self.client.get(reverse("customer-detail", args=[self.customer1.pk]))
        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------
    # TC-05: no token
    # ------------------------------------------------------------------
    def test_tc05_request_without_token_is_unauthorised(self):
        response = self.client.get(reverse("customer-list"))
        self.assertEqual(response.status_code, 401)

    def test_tc05_request_with_invalid_token_is_unauthorised(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        response = self.client.get(reverse("customer-list"))
        self.assertEqual(response.status_code, 401)

    def test_tc05_detail_without_token_is_unauthorised(self):
        response = self.client.get(reverse("customer-detail", args=[self.customer1.pk]))
        self.assertEqual(response.status_code, 401)

    # ------------------------------------------------------------------
    # Create, validation, search, filters, pagination
    # ------------------------------------------------------------------
    def test_create_assigns_the_logged_in_agent(self):
        self.authenticate(self.agent1)
        response = self.client.post(reverse("customer-list"), self.payload())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Customer.objects.get(email="new@example.com").assigned_agent, self.agent1)

    def test_client_cannot_choose_the_assigned_agent(self):
        self.authenticate(self.agent1)
        self.client.post(
            reverse("customer-list"), self.payload(assigned_agent=self.agent2.pk)
        )
        self.assertEqual(Customer.objects.get(email="new@example.com").assigned_agent, self.agent1)

    def test_email_is_lowercased_and_duplicates_rejected_ignoring_case(self):
        self.authenticate(self.agent1)
        response = self.client.post(
            reverse("customer-list"), self.payload(email="ALICE@Example.com")
        )
        self.assertEqual(response.status_code, 400)

    def test_phone_with_too_few_digits_is_rejected(self):
        self.authenticate(self.agent1)
        response = self.client.post(reverse("customer-list"), self.payload(phone="12345"))
        self.assertEqual(response.status_code, 400)

    def test_error_response_uses_the_standard_error_shape(self):
        self.authenticate(self.agent1)
        response = self.client.post(reverse("customer-list"), self.payload(phone="12345"))
        self.assertEqual(response.data["error"]["status_code"], 400)
        self.assertIn("phone", response.data["error"]["details"])

    def test_search_filters_by_name(self):
        self.authenticate(self.admin)
        response = self.client.get(reverse("customer-list"), {"search": "bob"})
        self.assertEqual(response.data["count"], 1)

    def test_filter_by_agent_username(self):
        self.authenticate(self.admin)
        response = self.client.get(reverse("customer-list"), {"agent": "agent1"})
        self.assertEqual(response.data["count"], 1)

    def test_pagination_returns_twenty_per_page(self):
        for number in range(25):
            make_customer(self.agent1, f"Person{number}", email=f"p{number}@example.com")
        self.authenticate(self.agent1)
        response = self.client.get(reverse("customer-list"))
        self.assertEqual(len(response.data["results"]), 20)
        self.assertEqual(response.data["count"], 26)

    # ------------------------------------------------------------------
    # Throttling
    # ------------------------------------------------------------------
    def test_sixth_post_within_a_minute_is_throttled(self):
        self.authenticate(self.agent1)
        for number in range(5):
            response = self.client.post(
                reverse("customer-list"), self.payload(email=f"t{number}@example.com")
            )
            self.assertEqual(response.status_code, 201)

        response = self.client.post(
            reverse("customer-list"), self.payload(email="t5@example.com")
        )
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)

    def test_reads_are_not_counted_by_the_burst_throttle(self):
        self.authenticate(self.agent1)
        for _ in range(10):
            response = self.client.get(reverse("customer-list"))
            self.assertEqual(response.status_code, 200)
