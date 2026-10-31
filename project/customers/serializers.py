from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Customer
from .validation import validate_unique_email


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
