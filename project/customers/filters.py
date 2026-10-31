import django_filters

from .models import Customer


# --------------------------------------------------
# CUSTOMER API FILTERS
# --------------------------------------------------
class CustomerFilter(django_filters.FilterSet):
    """
    Query-string filters for /api/customers/.

    Examples:
        ?first_name=ali           (contains, case-insensitive)
        ?email=example.com
        ?agent=agent1             (assigned agent's username)
        ?created_after=2026-01-01T00:00:00Z
    """

    first_name = django_filters.CharFilter(lookup_expr="icontains")
    last_name = django_filters.CharFilter(lookup_expr="icontains")
    email = django_filters.CharFilter(lookup_expr="icontains")
    phone = django_filters.CharFilter(lookup_expr="icontains")
    agent = django_filters.CharFilter(
        field_name="assigned_agent__username", lookup_expr="iexact"
    )
    created_after = django_filters.IsoDateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.IsoDateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model = Customer
        # Every filter is declared explicitly above, so none are generated here.
        fields = []
