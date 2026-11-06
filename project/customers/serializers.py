from django.core.exceptions import ValidationError
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import Customer

# ==================================================
# SHARED VALIDATION RULES (used by the API and by admin.py)
# Plain string checks, no regular expressions.
# ==================================================

DIGITS = "0123456789"
PHONE_FORMATTING = " -()."
MIN_PHONE_DIGITS = 10
MAX_PHONE_DIGITS = 15

# ===  ISP-1 / ISP-55    ===
# Phone and email validation
def clean_phone_number(value):
    """Allow formatted numbers with 10-15 digits; return the trimmed value."""
pass


# ===  ISP-1 / ISP-54    ===
# ==================================================
# CUSTOMER SERIALIZER
# ==================================================

class CustomerSerializer(serializers.ModelSerializer):
    """Validates incoming JSON and formats Customer rows as JSON."""

    # Read-only extra so clients need no second request for the agent's name.
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
        # user in the ViewSet (perform_create), never from the client.
        read_only_fields = ["customer_id", "assigned_agent", "created_at", "updated_at"]
        extra_kwargs = {
            # Case-insensitive unique check: "A@X.com" clashes with "a@x.com".
            # EmailField already rejects invalid addresses with a 400.
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

    # DRF calls validate_<field> automatically; Django's ValidationError
    # from the shared rules becomes a 400 with the message.
    def validate_first_name(self, value):
        return clean_name(value, "First name")

    def validate_last_name(self, value):
        return clean_name(value, "Last name")

    def validate_phone_number(self, value):
        return clean_phone_number(value)

    def validate_email(self, value):
        # Runs after the unique check; store emails lowercase.
        return value.strip().lower()