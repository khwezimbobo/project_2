from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import AddOn, ContractTerm, Package

# Serializer classes for the packages API. They convert model instances to JSON for the client.


class ContractTermSerializer(serializers.ModelSerializer):
    """A contract term option, e.g. 24-Month x0.90."""

    class Meta:
        model = ContractTerm
        # The fields sent to the client when a contract term is shown.
        fields = ["contract_term_id", "name", "multiplier", "duration_days", "description"]


class AddOnSerializer(serializers.ModelSerializer):
    """An optional monthly add-on, e.g. Static IP R100."""

    class Meta:
        model = AddOn
        fields = ["add_on_id", "name", "monthly_rate", "description"]


class PackageSerializer(serializers.ModelSerializer):
    """Short version used on the list page: GET /api/packages/"""

    class Meta:
        model = Package
        fields = ["package_id", "name", "monthly_rate", "speed_mbps", "description"]


class PackageDetailSerializer(PackageSerializer):
    """Full version used on one package: GET /api/packages/{id}/

    Adds the contract terms and add-ons a customer can choose with this package,
    so staff have everything they need to quote a price (BRD section 12).
    """

    # SerializerMethodField: the value comes from the get_<field name> method below.
    contract_terms = serializers.SerializerMethodField()
    add_ons = serializers.SerializerMethodField()

    class Meta(PackageSerializer.Meta):
        fields = PackageSerializer.Meta.fields + ["contract_terms", "add_ons"]

    @extend_schema_field(ContractTermSerializer(many=True))   # tells Swagger the real shape (a list of terms)
    def get_contract_terms(self, obj):
        # Every package can be taken on any contract term.
        return ContractTermSerializer(ContractTerm.objects.all(), many=True).data

    @extend_schema_field(AddOnSerializer(many=True))
    def get_add_ons(self, obj):
        # Only add-ons that are currently on sale.
        return AddOnSerializer(AddOn.objects.filter(is_active=True), many=True).data