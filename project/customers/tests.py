"""Tests for CustomerAdmin (customers/test.py).

Run with:  python manage.py test customers

ASSUMPTIONS (change them if your project differs):
  * AUTH_USER_MODEL is a custom user model with a `role` field
    (e.g. role="agent"). Django's built-in User has no `role`, so
    create_user(role=...) below would fail with a TypeError.
  * Customer has: name, email, phone, address, agent (ForeignKey to the
    user model), created_at, updated_at.
"""
# 1. Python only treats a string as the module docstring when it is the very
#    first statement, so the docstring was being ignored.
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .admin import CustomerAdmin
from .models import Customer

# get_user_model() returns whichever user model AUTH_USER_MODEL points to
# (your custom one with `role`), which is why we do not import User directly.
User = get_user_model()


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
        # Runs once for the whole class; Django rolls back changes per test,
        # so every test starts from this same clean data.
        # (`cls` is the class itself, because this is a @classmethod.)
        cls.superuser = User.objects.create_superuser(
            username="root", email="root@example.com", password="pass12345"
        )
        cls.agent1 = cls._make_user("agent1", role="agent")
        cls.agent2 = cls._make_user("agent2", role="agent")
        cls.other = cls._make_user("support1", role="support")  # not an agent

        # One customer for each agent, so tests can check who sees what.
        cls.customer1 = Customer.objects.create(
            name="Alice", email="alice@example.com", phone="0821234567",
            address="1 Main Road", agent=cls.agent1,
        )
        cls.customer2 = Customer.objects.create(
            name="Bob", email="bob@example.com", phone="0837654321",
            address="2 Side Street", agent=cls.agent2,
        )

    @staticmethod
    def _make_user(username, role):
        """Create a staff user with all Customer model permissions.

        Admin access needs is_staff=True plus the add/change/delete/view
        permissions. Without them even our overrides can't grant access.
        """
        user = User.objects.create_user(
            username=username, password="pass12345", role=role, is_staff=True
        )
        # All four permissions (add, change, delete, view) for Customer only.
        perms = Permission.objects.filter(
            content_type__app_label=Customer._meta.app_label,
            content_type__model=Customer._meta.model_name,
        )
        user.user_permissions.set(perms)
        return user

    def _request_for(self, user):
        """A bare request with .user set, for calling admin methods directly."""
        request = RequestFactory().get("/")
        request.user = user
        return request

    def _new_customer_data(self, **extra):
        """Valid form data for creating a customer; extra keys are added on top."""
        data = {"name": "New Customer", "email": "new@example.com",
                "phone": "0831234567", "address": "5 Test Street"}
        data.update(extra)
        return data

    # ------------------------------------------------------------------
    # Registration and access
    # ------------------------------------------------------------------
    def test_customer_is_registered_in_admin(self):
        # Fails if @admin.register(Customer) is missing or broken.
        self.assertTrue(admin.site.is_registered(Customer))

    def test_anonymous_user_is_redirected_to_login(self):
        # A visitor who is not logged in must be sent to the admin login.
        response = self.client.get(admin_url("changelist"))
        self.assertEqual(response.status_code, 302)
        
        self.assertTrue(response.url.startswith(reverse("admin:login")))

    # ------------------------------------------------------------------
    # Row-level security (the IDOR protection)
    # ------------------------------------------------------------------
    def test_superuser_sees_all_customers(self):
        # Superusers are not filtered, so both customers appear.
        self.client.force_login(self.superuser)
        response = self.client.get(admin_url("changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["cl"].queryset.count(), 2)

    def test_agent_sees_only_own_customers(self):
        # get_queryset() hides other agents' rows from the list page.
        self.client.force_login(self.agent1)
        response = self.client.get(admin_url("changelist"))
        self.assertEqual(response.status_code, 200)
        shown = list(response.context["cl"].queryset)
        self.assertEqual(shown, [self.customer1])

    def test_agent_cannot_open_another_agents_customer(self):
        # Typing another customer's ID into the URL must not show the form.
        self.client.force_login(self.agent1)
        response = self.client.get(admin_url("change", self.customer2.pk))
        # Django redirects (302) or refuses (403/404). Anything but 200 is safe.
        self.assertIn(response.status_code, (302, 403, 404))

    def test_agent_cannot_edit_another_agents_customer(self):
        # A forged POST to someone else's customer must change nothing.
        self.client.force_login(self.agent1)
        self.client.post(
            admin_url("change", self.customer2.pk),
            {"name": "Hacked", "email": "bob@example.com",
             "phone": "0837654321", "address": "2 Side Street"},
        )
        self.customer2.refresh_from_db()  # reload the row from the database
        self.assertEqual(self.customer2.name, "Bob")  # unchanged

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
        # Agents never choose the agent; save_model() assigns them.
        self.client.force_login(self.agent1)
        response = self.client.post(admin_url("add"), self._new_customer_data())
        self.assertEqual(response.status_code, 302)  # redirect = saved OK
        self.assertEqual(Customer.objects.get(email="new@example.com").agent, self.agent1)

    def test_agent_cannot_forge_a_different_agent(self):
        # 'agent' is read-only for agents, so this extra field must be ignored.
        self.client.force_login(self.agent1)
        self.client.post(
            admin_url("add"), self._new_customer_data(agent=self.agent2.pk)
        )
        self.assertEqual(Customer.objects.get(email="new@example.com").agent, self.agent1)

    def test_superuser_keeps_the_agent_they_choose(self):
        # Regression test for the save_model bug in the original code.
        self.client.force_login(self.superuser)
        self.client.post(
            admin_url("add"), self._new_customer_data(agent=self.agent2.pk)
        )
        self.assertEqual(Customer.objects.get(email="new@example.com").agent, self.agent2)

    def test_user_without_agent_role_cannot_add(self):
        # Staff with the right permissions but the wrong role get 403 Forbidden.
        self.client.force_login(self.other)
        response = self.client.get(admin_url("add"))
        self.assertEqual(response.status_code, 403)

    # ------------------------------------------------------------------
    # Per-role page layout (called directly on the ModelAdmin)
    # ------------------------------------------------------------------
    def test_agent_does_not_see_agent_column_or_filter(self):
        # Calls the admin methods directly instead of loading a page.
        model_admin = CustomerAdmin(Customer, admin.site)
        request = self._request_for(self.agent1)
        self.assertNotIn("agent", model_admin.get_list_display(request))
        self.assertNotIn("agent", model_admin.get_list_filter(request))
        self.assertNotIn("agent__username", model_admin.get_search_fields(request))

    def test_superuser_sees_agent_column_filter_and_search(self):
        model_admin = CustomerAdmin(Customer, admin.site)
        request = self._request_for(self.superuser)
        self.assertIn("agent", model_admin.get_list_display(request))
        self.assertIn("agent", model_admin.get_list_filter(request))
        self.assertIn("agent__username", model_admin.get_search_fields(request))

    def test_agent_field_is_read_only_for_agents_only(self):
        # Read-only for agents (cannot reassign), editable for superusers.
        model_admin = CustomerAdmin(Customer, admin.site)
        self.assertIn("agent", model_admin.get_readonly_fields(self._request_for(self.agent1)))
        self.assertNotIn("agent", model_admin.get_readonly_fields(self._request_for(self.superuser)))