"""Tests for the HTML pages: login, customers, dashboard."""
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer

from .helpers import PASSWORD, make_customer, make_user


class PageTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("admin1", role="admin")
        cls.agent1 = make_user("agent1", role="agent")
        cls.agent2 = make_user("agent2", role="agent")
        cls.no_role = make_user("norole", role="")

        cls.customer1 = make_customer(cls.agent1, "Alice", email="alice@example.com")
        cls.customer2 = make_customer(cls.agent2, "Bob", email="bob@example.com")

    def setUp(self):
        cache.clear()

    # ------------------------------------------------------------------
    # Login and logout
    # ------------------------------------------------------------------
    def test_login_page_loads(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)

    def test_login_with_correct_details_redirects_to_customers(self):
        response = self.client.post(
            reverse("login"), {"username": "agent1", "password": PASSWORD}
        )
        self.assertRedirects(response, reverse("customer_list"))

    def test_login_with_wrong_password_shows_the_form_again(self):
        response = self.client.post(
            reverse("login"), {"username": "agent1", "password": "nope"}
        )
        self.assertEqual(response.status_code, 200)

    def test_login_ignores_an_external_next_url(self):
        response = self.client.post(
            reverse("login") + "?next=https://evil.example.com/",
            {"username": "agent1", "password": PASSWORD},
        )
        self.assertRedirects(response, reverse("customer_list"))

    def test_logout_requires_post(self):
        self.client.force_login(self.agent1)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)

    def test_logout_with_post_ends_the_session(self):
        self.client.force_login(self.agent1)
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(reverse("customer_list")).status_code, 302)

    # ------------------------------------------------------------------
    # Customer pages
    # ------------------------------------------------------------------
    def test_anonymous_visitor_is_sent_to_login(self):
        response = self.client.get(reverse("customer_list"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("login")))

    def test_agent_list_shows_only_own_customers(self):
        self.client.force_login(self.agent1)
        response = self.client.get(reverse("customer_list"))
        self.assertContains(response, "Alice")
        self.assertNotContains(response, "Bob")

    def test_admin_list_shows_every_customer(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("customer_list"))
        self.assertContains(response, "Alice")
        self.assertContains(response, "Bob")

    def test_list_search_filters_results(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("customer_list"), {"q": "bob"})
        self.assertContains(response, "Bob")
        self.assertNotContains(response, "Alice")

    def test_agent_can_open_own_customer(self):
        self.client.force_login(self.agent1)
        response = self.client.get(reverse("customer_detail", args=[self.customer1.pk]))
        self.assertEqual(response.status_code, 200)

    def test_agent_is_blocked_from_another_agents_customer_page(self):
        self.client.force_login(self.agent1)
        response = self.client.get(reverse("customer_detail", args=[self.customer2.pk]))
        self.assertEqual(response.status_code, 403)

    def test_user_without_role_gets_403_on_customer_list(self):
        self.client.force_login(self.no_role)
        self.assertEqual(self.client.get(reverse("customer_list")).status_code, 403)

    def test_agent_can_create_a_customer_through_the_form(self):
        self.client.force_login(self.agent1)
        response = self.client.post(
            reverse("customer_create"),
            {
                "first_name": "Carol",
                "last_name": "Jones",
                "email": "Carol@Example.com",
                "phone": "+27 82 123 4567",
                "address": "3 Long Street",
            },
        )
        customer = Customer.objects.get(email="carol@example.com")
        self.assertRedirects(response, reverse("customer_detail", args=[customer.pk]))
        self.assertEqual(customer.assigned_agent, self.agent1)

    def test_create_form_rejects_an_invalid_phone(self):
        self.client.force_login(self.agent1)
        response = self.client.post(
            reverse("customer_create"),
            {
                "first_name": "Carol",
                "last_name": "Jones",
                "email": "carol@example.com",
                "phone": "123",
                "address": "3 Long Street",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Customer.objects.filter(email="carol@example.com").exists())

    def test_agent_cannot_edit_another_agents_customer(self):
        self.client.force_login(self.agent1)
        response = self.client.post(
            reverse("customer_edit", args=[self.customer2.pk]),
            {
                "first_name": "Hacked",
                "last_name": "Smith",
                "email": "bob@example.com",
                "phone": "0821234567",
                "address": "1 Main Road",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.customer2.refresh_from_db()
        self.assertEqual(self.customer2.first_name, "Bob")

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_loads_for_an_agent(self):
        self.client.force_login(self.agent1)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_customers"], 1)
        self.assertIsNone(response.context["active_agents"])

    def test_dashboard_shows_all_customers_and_agent_count_to_an_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["total_customers"], 2)
        self.assertEqual(response.context["active_agents"], 2)

    def test_dashboard_is_forbidden_without_a_role(self):
        self.client.force_login(self.no_role)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)

    def test_dashboard_is_forbidden_for_non_staff(self):
        outsider = make_user("outsider", role="agent", is_staff=False)
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)
