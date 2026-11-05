# Copy to reports/serializers.py
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from subscriptions.models import Subscription


class RevenueRowSerializer(serializers.Serializer):
    package = serializers.CharField()
    active_subscriptions = serializers.IntegerField()
    monthly_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)


class RevenueSummarySerializer(serializers.Serializer):
    total_monthly_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    packages = RevenueRowSerializer(many=True)


class ExpiringSubscriptionSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    package_name = serializers.CharField(source="package.name", read_only=True)
    contract_term_name = serializers.CharField(source="contract_term.name", read_only=True)
    days_left = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = (
            "subscription_id", "customer", "customer_name", "package_name", "contract_term_name",
            "monthly_total", "contract_end_date", "days_left", "status",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.IntegerField())
    def get_days_left(self, obj):
        """Negative once the end date has passed."""
        return (obj.contract_end_date - timezone.localdate()).days