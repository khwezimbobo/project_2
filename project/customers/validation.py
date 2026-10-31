import re

from django.apps import apps
from django.core.exceptions import ValidationError


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
