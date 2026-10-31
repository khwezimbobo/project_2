"""Tests for CustomerAdmin (row-level security in Django Admin)."""
from django.contrib import admin
from django.test import RequestFactory, TestCase
from django.urls import reverse

from customers.admin import CustomerAdmin
from customers.models import Customer, User

from .helpers import make_customer, make_user


def admin_url(action, *args):
    """Build an admin URL such as admin:customers_customer_changelist.

    Using _meta means the tests keep working if the app label changes.
    `action` is one of: changelist, add, change, delete.
    """
    meta = Customer._meta
    return reverse(f"admin:{meta.app_label}_{meta.model_name}_{action}", args=args)


class CustomerAdminTests(TestCase):

    # ------------------------------------------------------------------
    # Test data and helpers
    # ------------------------------------------------------------------
    @classmethod
    def setUpTestData(cls):
        # Runs once for the whole class; Django rolls back changes per test.
        cls.superuser = User.objects.create_superuser(
            username="root", email="root@example.com", password="pass12345"
        )
        cls.agent1 = make_user("agent1", role="agent", with_model_permissions=True)
        cls.agent2 = make_user("agent2", role="agent", with_model_permissions=True)
        # Staff with the right permissions but no Agent/Admin role.
        cls.other = make_user("support1", role="", with_model_permissions=True)

        # One customer for each agent, so tests can check who sees what.
        cls.customer1 = make_customer(cls.agent1, "Alice", email="alice@example.com")
        cls.customer2 = make_customer(cls.agent2, "Bob", email="bob@example.com")

    def _request_for(self, user):
        """A bare request with .user set, for calling admin methods directly."""
        request = RequestFactory().get("/")
        request.user = user
        return request

    def _new_customer_data(self, **extra):
        """Valid form data for creating a customer; extra keys are added on top."""
        data = {
            "first_name": "New",
            "last_name": "Customer",
            "email": "new@example.com",
            "phone": "0831234567",
            "address": "5 Test Street",
        }
        data.update(extra)
        return data

    # ------------------------------------------------------------------
    # Registration and access
    # ------------------------------------------------------------------
    def test_customer_is_registered_in_admin(self):
        self.assertTrue(admin.site.is_registered(Customer))

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(admin_url("changelist"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("admin:login")))

    # ------------------------------------------------------------------
    # Row-level security (the IDOR protection)
    # ------------------------------------------------------------------
    def test_superuser_sees_all_customers(self):
        self.client.force_login(self.superuser)
        response = self.client.get(admin_url("changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["cl"].queryset.count(), 2)

    def test_agent_sees_only_own_customers(self):
        self.client.force_login(self.agent1)
        response = self.client.get(admin_url("changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["cl"].queryset), [self.customer1])

    def test_agent_cannot_open_another_agents_customer(self):
        self.client.force_login(self.agent1)
        response = self.client.get(admin_url("change", self.customer2.pk))
        # Django redirects (302) or refuses (403/404). Anything but 200 is safe.
        self.assertIn(response.status_code, (302, 403, 404))

    def test_agent_cannot_edit_another_agents_customer(self):
        self.client.force_login(self.agent1)
        self.client.post(
            admin_url("change", self.customer2.pk),
            self._new_customer_data(first_name="Hacked", email="bob@example.com"),
        )
        self.customer2.refresh_from_db()
        self.assertEqual(self.customer2.first_name, "Bob")

    def test_agent_cannot_delete_another_agents_customer(self):
        # {"post": "yes"} is the admin's "Yes, I'm sure" confirmation.
        self.client.force_login(self.agent1)
        self.client.post(admin_url("delete", self.customer2.pk), {"post": "yes"})
        self.assertTrue(Customer.objects.filter(pk=self.customer2.pk).exists())

    def test_agent_can_delete_own_customer(self):
        # The opposite check: the restrictions must not block legitimate use.
        self.client.force_login(self.agent1)
        self.client.post(admin_url("delete", self.customer1.pk), {"post": "yes"})
        self.assertFalse(Customer.objects.filter(pk=self.customer1.pk).exists())

    # ------------------------------------------------------------------
    # Creating customers (save_model)
    # ------------------------------------------------------------------
    def test_agent_add_assigns_agent_to_themselves(self):
        self.client.force_login(self.agent1)
        response = self.client.post(admin_url("add"), self._new_customer_data())
        self.assertEqual(response.status_code, 302)  # redirect = saved OK
        customer = Customer.objects.get(email="new@example.com")
        self.assertEqual(customer.assigned_agent, self.agent1)

    def test_agent_cannot_forge_a_different_agent(self):
        # assigned_agent is read-only for agents, so this extra field is ignored.
        self.client.force_login(self.agent1)
        self.client.post(
            admin_url("add"), self._new_customer_data(assigned_agent=self.agent2.pk)
        )
        customer = Customer.objects.get(email="new@example.com")
        self.assertEqual(customer.assigned_agent, self.agent1)

    def test_superuser_keeps_the_agent_they_choose(self):
        self.client.force_login(self.superuser)
        self.client.post(
            admin_url("add"), self._new_customer_data(assigned_agent=self.agent2.pk)
        )
        customer = Customer.objects.get(email="new@example.com")
        self.assertEqual(customer.assigned_agent, self.agent2)

    def test_user_without_agent_role_cannot_add(self):
        self.client.force_login(self.other)
        response = self.client.get(admin_url("add"))
        self.assertEqual(response.status_code, 403)

    # ------------------------------------------------------------------
    # Per-role page layout (called directly on the ModelAdmin)
    # ------------------------------------------------------------------
    def test_agent_does_not_see_agent_column_or_filter(self):
        model_admin = CustomerAdmin(Customer, admin.site)
        request = self._request_for(self.agent1)
        self.assertNotIn("assigned_agent", model_admin.get_list_display(request))
        self.assertNotIn("assigned_agent", model_admin.get_list_filter(request))
        self.assertNotIn("assigned_agent__username", model_admin.get_search_fields(request))

    def test_superuser_sees_agent_column_filter_and_search(self):
        model_admin = CustomerAdmin(Customer, admin.site)
        request = self._request_for(self.superuser)
        self.assertIn("assigned_agent", model_admin.get_list_display(request))
        self.assertIn("assigned_agent", model_admin.get_list_filter(request))
        self.assertIn("assigned_agent__username", model_admin.get_search_fields(request))

    def test_agent_field_is_read_only_for_agents_only(self):
        model_admin = CustomerAdmin(Customer, admin.site)
        agent_readonly = model_admin.get_readonly_fields(self._request_for(self.agent1))
        superuser_readonly = model_admin.get_readonly_fields(self._request_for(self.superuser))
        self.assertIn("assigned_agent", agent_readonly)
        self.assertNotIn("assigned_agent", superuser_readonly)
