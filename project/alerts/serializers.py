from rest_framework import serializers

from .models import RenewalAlert

class RenewalAlertSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="subscription.customer.name", read_only=True)
    package_name = serializers.CharField(source="subscription.package.name", read_only=True)
    contract_end_date = serializers.DateField(source="subscription.contract_end_date", read_only=True)
    acknowledged_by_username = serializers.CharField(
        source="acknowledged_by.username", read_only=True, default=None
    )

    class Meta:
        model = RenewalAlert
        fields = (
            "alert_id", "subscription", "customer_name", "package_name", "contract_end_date",
            "days_until_expiry", "alert_date", "status",
            "acknowledged_by", "acknowledged_by_username", "acknowledged_at", "created_at",
        )
        read_only_fields = fields