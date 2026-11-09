# ===  ISP-1 / ISP-21    ===
# uuid lets us generate a random, unguessable primary key for each customer.
import uuid

# settings lets the FK refer to the user model by configuration.
from django.conf import settings
# AbstractUser is Django's full user (username, password, email, ...).
from django.contrib.auth.models import AbstractUser, Group

# models provides the Model base class and the field types.
from django.db import models

# ==================================================
# USER MODEL (adds the Support Agent / Agent role)
# ==================================================
# ===  ISP-1 / ISP-22    ===
class User(AbstractUser):
    """Project user: Django's own fields plus an application role."""

    # TextChoices defines the allowed role values in one place.
    class Role(models.TextChoices):
        # Stored value "admin", shown as "Admin"
        ADMIN = "admin", "Admin"
        # Stored value "agent", shown as "Support Agent".
        AGENT = "agent", "Support Agent"

    # The role column; blank means "no application role" (e.g. a plain superuser).
    role = models.CharField(
        max_length=20,            # longer than any role value we store
        choices=Role.choices,     # restrict values to the Role options
        blank=True,               # the field may be left empty in forms
        default="",               # new users start with no role
        db_index=True,            # index it because permission checks read it often
    )

    class Meta:
        # Name the table auth_user so the customers FK points at "auth_user",
        # as the SQL spec requires.
        db_table = "auth_user"

    @property
    def can_view_all(self):
        """
        Admins and superusers may see every customer.
        """
        return self.is_superuser or self.role == self.Role.ADMIN

    @property  # lets code write user.is_agent_or_admin without parentheses
    def is_agent_or_admin(self):
        """True for active superusers and staff users with the Agent or Admin role."""
        # Inactive accounts never pass; superusers always pass; everyone else
        # must be staff AND hold one of the two roles.
        return self.is_active and (
            self.is_superuser
            or (self.is_staff and self.role in (self.Role.AGENT, self.Role.ADMIN))
        )
    
    # Maps each role value to the Django group with the same meaning.
    # Names must match create_groups and the subscriptions app.    
    ROLE_GROUPS = {
        "admin": "Admin",
        "agent": "Support Agent",
    }
        
    def save(self, *args, **kwargs):
        # Save first: a user needs a primary key before groups can be linked.
        super().save(*args, **kwargs)
        self.sync_role_group()

    def sync_role_group(self):
        """Put the user in the group that matches their role.

        Keeps the Django groups consistent with the role column that
        can_view_all reads. Users with no role (or an unknown one) are left
        alone, so groups assigned by hand are never stripped.
        """
        # .get() returns None for a blank or unknown role instead of raising KeyError.
        wanted = self.ROLE_GROUPS.get(self.role)
        if not wanted:
            return
        # Look up the group for this role, creating it if the data migration has not run.
        group, _ = Group.objects.get_or_create(name=wanted)
        self.groups.add(group)
        # Remove the other role's group so a promoted or demoted user is
        # never in both.
        other = [name for r, name in self.ROLE_GROUPS.items() if r != self.role]
        self.groups.remove(*Group.objects.filter(name__in=other))
# ==================================================
# CUSTOMER MODEL (table: customers)
# ==================================================
# ===  ISP-1 / ISP-22    ===
class Customer(models.Model):
    """An ISP customer, owned by one staff agent."""

    # customer_id (PK, UUID): random id, so ids cannot be guessed or counted.
    customer_id = models.UUIDField(
        primary_key=True,    # this column is the primary key
        default=uuid.uuid4,  # generate a new random UUID for each customer
        editable=False,      # never shown in forms and never user-editable
    )

    # first_name / last_name: stored separately so we can sort by surname
    # and search either part.
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    
    # phone_number: a string, because numbers may start with 0 or "+".
    phone_number = models.CharField(max_length=20)

    # email: unique=True makes the DATABASE refuse duplicates, even if
    # application code forgets to check.
    email = models.EmailField(unique=True)

    # address: free text, because addresses vary in length and format.
    address = models.TextField()
    
# ===  ISP-1 / ISP-23    ===
    # assigned_agent (FK -> auth_user): the staff member responsible.
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,          # the project's User model
        on_delete=models.PROTECT,          # block deleting an agent who owns customers
        related_name="assigned_customers", # user.assigned_customers gives their customers
    )  # Django indexes foreign keys automatically, so no db_index is needed.

    # created_at: set once, automatically, when the row is first saved.
    created_at = models.DateTimeField(auto_now_add=True)

    # updated_at: refreshed automatically on every save.
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customers"
        # Sort by surname, then first name; created_at breaks ties so
        # pagination never repeats or skips rows.
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
        # Trim stray spaces from both names.
        self.first_name = self.first_name.strip()
        self.last_name = self.last_name.strip()
        # Store emails lowercase so "A@x.com" and "a@x.com" cannot both exist.
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.email})"