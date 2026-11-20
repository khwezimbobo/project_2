# Customers app models.
# BRD s13: customers table. BRD s7: Admin and Support Agent roles.
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group
from django.db import models


# ==================================================
# USER (BRD s7 roles, s15 role-based permissions, FR-02)
# ==================================================
class User(AbstractUser):
    """Staff user with one role: Admin or Support Agent."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        AGENT = "agent", "Support Agent"

    # Blank means no application role (e.g. a plain superuser).
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        blank=True,
        default="",
        db_index=True,   # BRD s10: fields used in checks and filters are indexed
    )

    class Meta:
        # BRD s13: customers.assigned_agent is a foreign key to auth_user.
        db_table = "auth_user"

    @property
    def can_view_all(self):
        """Admins and superusers see every record (BRD s8.2)."""
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def is_agent_or_admin(self):
        """True for active superusers and staff with the Agent or Admin role."""
        return self.is_active and (
            self.is_superuser
            or (self.is_staff and self.role in (self.Role.AGENT, self.Role.ADMIN))
        )

    # Role value -> Django group. Names match migration 0002 and the other apps.
    ROLE_GROUPS = {
        "admin": "Admin",
        "agent": "Support Agent",
    }

    def save(self, *args, **kwargs):
        # Save first: the user needs an id before groups can be linked.
        super().save(*args, **kwargs)
        self.sync_role_group()

    def sync_role_group(self):
        """Put the user in the group that matches their role.

        Users with no role (or an unknown one) are left alone, so groups
        assigned by hand are never removed.
        """
        # .get() returns None for a blank or unknown role instead of raising.
        wanted = self.ROLE_GROUPS.get(self.role)
        if not wanted:
            return
        group, _ = Group.objects.get_or_create(name=wanted)
        self.groups.add(group)
        # Remove the other role's group, so a promoted user is in only one.
        other = [name for r, name in self.ROLE_GROUPS.items() if r != self.role]
        self.groups.remove(*Group.objects.filter(name__in=other))


# ==================================================
# CUSTOMER (BRD s13: customers table, FR-03, FR-04)
# ==================================================
class Customer(models.Model):
    """An ISP customer, owned by one staff agent."""

    # customer_id (PK, UUID): random, so ids cannot be guessed (BRD s13, s15).
    customer_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    # A string, because numbers can start with 0 or +.
    # The 10-digit rule (BRD s18) is checked in serializers.py and admin.py.
    phone_number = models.CharField(max_length=20)

    # unique=True: the database itself refuses duplicates (BRD s18).
    email = models.EmailField(unique=True)

    address = models.TextField()

    # BRD s13: assigned_agent (FK to auth_user). Foreign keys are indexed
    # automatically, which meets BRD s13.1 (index customers.assigned_agent).
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,           # cannot delete an agent who owns customers
        related_name="assigned_customers",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customers"
        # Stable order, so pagination (BRD s8.2) never repeats or skips rows.
        ordering = ["last_name", "first_name", "created_at"]
        indexes = [
            models.Index(fields=["last_name", "first_name"], name="customers_name_idx"),
            models.Index(fields=["created_at"], name="customers_created_idx"),
        ]

    @property
    def full_name(self):
        """First and last name together (not a database column)."""
        return f"{self.first_name} {self.last_name}".strip()

    def save(self, *args, **kwargs):
        # Trim names and lowercase the email so "A@x.com" and "a@x.com" match.
        self.first_name = self.first_name.strip()
        self.last_name = self.last_name.strip()
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.email})"
