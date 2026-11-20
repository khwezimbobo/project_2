# Customer input validation (BRD s15: validation lives in serializers; BRD s18).
# The same rules are reused by admin.py, so the API and the Admin agree.
from django.core.exceptions import ValidationError
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import Customer


# ==================================================
# SHARED VALIDATION RULES (BRD s18)
# ==================================================

DIGITS = "0123456789"
PHONE_FORMATTING = " -()."   # allowed, but not counted as digits
MIN_PHONE_DIGITS = 10        # BRD s18: minimum length 10 digits
MAX_PHONE_DIGITS = 15        # international maximum


def clean_phone_number(value):
    """Accept formatted numbers with 10 to 15 digits; return the trimmed value."""
    value = (value or "").strip()
    digit_count = 0
    for position, character in enumerate(value):
        if character in DIGITS:
            digit_count += 1
        elif character == "+" and position == 0:
            continue                         # + only as the first character
        elif character in PHONE_FORMATTING:
            continue
        else:
            raise ValidationError(
                "Phone number may only contain digits, spaces, brackets, "
                "hyphens, dots and a leading +."
            )
    # Count digits only, so formatting never changes the result.
    if not MIN_PHONE_DIGITS <= digit_count <= MAX_PHONE_DIGITS:
        raise ValidationError(
            f"Phone number must contain between {MIN_PHONE_DIGITS} "
            f"and {MAX_PHONE_DIGITS} digits."
        )
    return value


def clean_name(value, label):
    """Trim a name and refuse one made only of spaces."""
    value = (value or "").strip()
    if not value:
        raise ValidationError(f"{label} cannot be blank.")
    return value


# ==================================================
# CUSTOMER SERIALIZER (FR-03 create, FR-04 list)
# ==================================================
class CustomerSerializer(serializers.ModelSerializer):
    """Validates incoming JSON and formats Customer rows as JSON."""

    # Read-only extra: the agent's name, so clients need no second request.
    assigned_agent_username = serializers.CharField(
        source="assigned_agent.username", read_only=True
    )

    class Meta:
        model = Customer
        fields = [
            "customer_id", "first_name", "last_name", "email", "phone_number",
            "address", "assigned_agent", "assigned_agent_username",
            "created_at", "updated_at",
        ]
        # The server controls these. assigned_agent is set from the logged-in
        # user in views.py, so a client value is ignored (BRD s15).
        read_only_fields = ["customer_id", "assigned_agent", "created_at", "updated_at"]
        extra_kwargs = {
            # BRD s18: a duplicate email returns 400, ignoring letter case.
            # An invalid email format is already rejected by EmailField.
            "email": {
                "validators": [
                    UniqueValidator(
                        queryset=Customer.objects.all(),
                        lookup="iexact",
                        message="A customer with this email already exists.",
                    )
                ]
            },
        }

    # DRF calls validate_<field> for each field.
    def validate_first_name(self, value):
        return clean_name(value, "First name")

    def validate_last_name(self, value):
        return clean_name(value, "Last name")

    def validate_phone_number(self, value):
        return clean_phone_number(value)

    def validate_email(self, value):
        return value.strip().lower()
