"""Shared helpers for the customers test modules."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

from customers.models import Customer

User = get_user_model()

PASSWORD = "pass12345"


def make_user(username, role, is_staff=True, with_model_permissions=False):
    """Create a user with a role. Optionally grant Customer admin permissions."""
    user = User.objects.create_user(
        username=username, password=PASSWORD, role=role, is_staff=is_staff
    )

    if with_model_permissions:
        # All four permissions (add, change, delete, view) for Customer only.
        permissions = Permission.objects.filter(
            content_type__app_label=Customer._meta.app_label,
            content_type__model=Customer._meta.model_name,
        )
        user.user_permissions.set(permissions)

    return user


def make_customer(agent, first_name="Alice", last_name="Smith", email=None, phone="0821234567"):
    """Create a customer owned by the given agent."""
    return Customer.objects.create(
        first_name=first_name,
        last_name=last_name,
        email=email or f"{first_name.lower()}@example.com",
        phone=phone,
        address="1 Main Road",
        assigned_agent=agent,
    )
