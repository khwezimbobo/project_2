import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from .serializers import validate_phone_number


# ==================================================
# USER MODEL (adds the Admin / Agent role)
# ==================================================

class User(AbstractUser):
    """Project user. Django's own fields plus an application role."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        AGENT = "agent", "Agent"

    # Blank means "no application role" (for example a plain superuser).
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        blank=True,
        default="",
        db_index=True,
    )

    @property
    def is_agent_or_admin(self):
        """True for active superusers and staff users with the Agent or Admin role."""
        return self.is_active and (
            self.is_superuser
            or (
                self.is_staff
                and self.role in (self.Role.AGENT, self.Role.ADMIN)
            )
        )


# ==================================================
# CUSTOMER MODEL
# ==================================================

class Customer(models.Model):

    # Generate a unique UUID automatically for every customer.
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # Store the customer's personal details.
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    # Prevent duplicate email addresses.
    email = models.EmailField(unique=True)

    # Telephone numbers, including international and formatted numbers.
    phone = models.CharField(max_length=20, validators=[validate_phone_number])

    # Store the customer's physical or postal address.
    address = models.TextField()

    # Link each customer to the staff agent responsible for them.
    # PROTECT prevents deletion of an agent who still owns customers.
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_customers",
        db_index=True
    )

    # Automatically maintain record creation and update dates.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Stable default ordering keeps pagination consistent.
        ordering = ["last_name", "first_name"]

    @property # Allows access to the method like an attribute, without using parenthesis ()
    def full_name(self):
        """First and last name together, used in templates."""
        return f"{self.first_name} {self.last_name}".strip()

    def save(self, *args, **kwargs):
        # Store emails in one standard form so duplicates cannot differ by case.
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    # Provide a readable representation in Django Admin and debugging.
    def __str__(self):
        return f"{self.full_name} ({self.email})"
