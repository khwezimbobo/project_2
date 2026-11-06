from rest_framework import serializers

from packages.models import AddOn, ContractTerm, Package

from .models import Subscription, SubscriptionAddOn, SubscriptionAuditLog, SubscriptionStatus
from .permissions import is_admin
from .services import InvalidStatusTransition, check_transition, create_subscription

# --- Serializers (BRD 8.1) ----------------------------------------------------
class SubscriptionAddOnSerializer(serializers.ModelSerializer):
    """One add-on on a subscription, with the price it had at sign-up."""

    add_on_id = serializers.IntegerField(source="add_on.add_on_id", read_only=True)
    name = serializers.CharField(source="add_on.name", read_only=True)

    class Meta:
        model = SubscriptionAddOn   # The SubscriptionAddOn model is a through table that connects subscriptions to add-ons, and stores the price of the add-on at the time of subscription.
        fields = ["add_on_id", "name", "monthly_rate"]

class SubscriptionSerializer(serializers.ModelSerializer):
    """Create and view subscriptions.

    The client sends ONLY: customer, package, contract_term, add_ons, installation_date.
    Everything else (prices, contract dates, status, created_by) is read-only, so if the
    client sends those fields DRF simply ignores them (BRD 18: client pricing is ignored).
    """

    # Input: list of add-on IDs, e.g. "add_ons": [1, 2]. Only active add-ons are accepted.
    add_ons = serializers.PrimaryKeyRelatedField(
        queryset=AddOn.objects.filter(is_active=True), many=True, required=False, write_only=True,
    )
    # Output: the add-ons with their names and prices.
    add_on_details = SubscriptionAddOnSerializer(source="subscription_add_ons", many=True, read_only=True)
    # Only active packages can be chosen.
    package = serializers.PrimaryKeyRelatedField(queryset=Package.objects.filter(is_active=True))
    contract_term = serializers.PrimaryKeyRelatedField(queryset=ContractTerm.objects.all())
    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "subscription_id", "customer", "package", "contract_term", "add_ons", "add_on_details",
            "installation_date", "contract_start_date", "contract_end_date",
            "base_amount", "add_on_total", "subtotal", "discount_name", "discount_amount",
            "monthly_total", "installation_fee", "first_month_total",
            "status", "created_by", "created_at", "updated_at",
        ]
        read_only_fields = [
            "subscription_id", "contract_start_date", "contract_end_date",
            "base_amount", "add_on_total", "subtotal", "discount_name", "discount_amount",
            "monthly_total", "installation_fee", "first_month_total",
            "status", "created_by", "created_at", "updated_at",
        ]

    def validate_customer(self, customer):
        # Support Agents may only create subscriptions for their own customers (BRD 8.2).
        user = self.context["request"].user
        if not is_admin(user) and customer.assigned_agent_id != user.pk:
            raise serializers.ValidationError("You can only create subscriptions for your own customers.")
        return customer

    def validate_add_ons(self, add_ons):
        # The same add-on can't be picked twice.
        if len(add_ons) != len(set(add_ons)):
            raise serializers.ValidationError("Each add-on can only be selected once.")
        return add_ons

    def create(self, validated_data):
        # All pricing, dates and the audit log are handled by the service layer.
        return create_subscription(
            customer=validated_data["customer"],
            package=validated_data["package"],
            contract_term=validated_data["contract_term"],
            add_ons=validated_data.get("add_ons", []),
            installation_date=validated_data["installation_date"],
            created_by=self.context["request"].user,
        )

class StatusUpdateSerializer(serializers.Serializer):
    """Input for PATCH /api/subscriptions/{id}/status/ - the new status plus an optional note."""

    # ChoiceField: anything other than Pending/Active/Suspended/Cancelled is rejected with 400.
    status = serializers.ChoiceField(choices=SubscriptionStatus.choices)
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_status(self, new_status):
        # The subscription being changed is passed in by the view as "instance".
        try:
            check_transition(self.instance.status, new_status)
        except InvalidStatusTransition as error:
            # Turn the rule-breaking into a normal 400 with a clear message (BRD 18).
            raise serializers.ValidationError(str(error))
        return new_status

class SubscriptionFilterSerializer(serializers.Serializer):
    """Checks the filter values in the URL, e.g. ?status=Active&package=1&contract_term=2.

    All optional. An invalid value (unknown status, package that doesn't exist, not a number)
    makes the list endpoint return 400 with a clear message instead of silently ignoring it (BRD 18).
    """

    status = serializers.ChoiceField(choices=SubscriptionStatus.choices, required=False)
    package = serializers.PrimaryKeyRelatedField(queryset=Package.objects.all(), required=False)
    contract_term = serializers.PrimaryKeyRelatedField(queryset=ContractTerm.objects.all(), required=False)

class AuditLogSerializer(serializers.ModelSerializer):
    """One entry in a subscription's status history (GET /api/subscriptions/{id}/logs/)."""

    # Show the username, or "System" for automatic changes made by Celery (changed_by is empty).
    changed_by = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionAuditLog
        fields = ["log_id", "old_status", "new_status", "changed_by", "notes", "timestamp"]

    def get_changed_by(self, log):
        return log.changed_by.username if log.changed_by else "System"