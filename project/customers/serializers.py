from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

import re

from django.apps import apps
from django.core.exceptions import ValidationError

from .models import Customer


# ==================================================
# CUSTOMER SERIALIZER
# ==================================================

class CustomerSerializer(serializers.ModelSerializer):

    # Read-only convenience field so clients do not need a second request.
    assigned_agent_username = serializers.CharField(
        source="assigned_agent.username", read_only=True
    )

    class Meta:

        # Connect the serializer to the Customer model.
        model = Customer

        # Define the fields exposed through the API.
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "address",
            "assigned_agent",
            "assigned_agent_username",
            "created_at",
            "updated_at",
        ]

        # These values are controlled by the application.
        read_only_fields = [
            "id",
            "assigned_agent",
            "created_at",
            "updated_at",
        ]

# ==================================================
# PHONE NUMBER VALIDATION
# ==================================================

# Digits plus the usual formatting characters, with an optional leading "+".
PHONE_ALLOWED_CHARACTERS = re.compile(r"^\+?[\d\s\-().]+$")


def validate_phone_number(value):
    """
    Allow formatted phone numbers but require between
    10 and 15 actual digits.

    This is attached to the Customer.phone model field, so the API,
    the HTML forms and Django Admin all enforce the same rule.
    """

    value = (value or "").strip()

    # Reject letters and other unexpected symbols.
    if not PHONE_ALLOWED_CHARACTERS.match(value):
        raise ValidationError(
            "Phone number may only contain digits, spaces, brackets, "
            "hyphens, dots and a leading +."
        )

    # Ignore spaces, brackets, hyphens and other formatting.
    digits = "".join(character for character in value if character.isdigit())

    # Check the actual number of digits.
    if not 10 <= len(digits) <= 15:
        raise ValidationError(
            "Phone number must contain between 10 and 15 digits."
        )

    return value


# ==================================================
# EMAIL UNIQUENESS (case-insensitive)
# ==================================================

def validate_unique_email(value, instance=None):
    """
    Reject an email that already belongs to another customer.

    The comparison ignores letter case, and the customer being edited
    (instance) is excluded so saving without changing the email works.
    """

    # Looked up lazily to avoid a circular import with models.py.
    customer_model = apps.get_model("customers", "Customer")

    others = customer_model.objects.filter(email__iexact=value)
    if instance is not None and instance.pk is not None:
        others = others.exclude(pk=instance.pk)

    if others.exists():
        raise ValidationError("A customer with this email already exists.")

    return value

    # --------------------------------------------------
    # EMAIL VALIDATION
    # --------------------------------------------------

    def validate_email(self, value):

        # Remove unnecessary spaces and standardise email casing.
        email = value.strip().lower()

        # Reject duplicates regardless of letter case.
        validate_unique_email(email, instance=self.instance)

        return email

    # Phone validation is not repeated here: the Customer.phone model field
    # carries validate_phone_number and DRF applies it automatically.


# ==================================================
# JWT LOGIN SERIALIZER
# ==================================================

class RoleTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds the username and role to the JWT so clients can read them."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["role"] = user.role
        return token
