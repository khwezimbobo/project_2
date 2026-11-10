from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Package
from .serializers import PackageDetailSerializer, PackageSerializer


# Swagger text for each action (ISP-15). Shown at /api/docs/ under "Packages".
@extend_schema_view(
    list=extend_schema(
        tags=["Packages"],
        summary="List active packages",
        description="Agent or Admin. The four seeded fibre packages with their monthly rate and speed. "
                    "Inactive packages are hidden. Packages are read-only: they are managed in Django Admin.",
    ),
    retrieve=extend_schema(
        tags=["Packages"],
        summary="Get one package with its contract terms and add-ons",
        description="Agent or Admin. Includes every contract term (with its price multiplier) and every "
                    "active add-on, so staff have everything they need to quote a price.",
    ),
)
class PackageViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only package catalogue.

    GET /api/packages/       - list active packages
    GET /api/packages/{id}/  - one package with its contract terms and add-ons

    ReadOnlyModelViewSet only provides list and retrieve, so POST, PUT, PATCH
    and DELETE automatically return 405 Method Not Allowed. Packages are managed
    in Django Admin and loaded by seed_data, not through the API.
    """

    # Inactive packages are hidden from the API (BRD section 12: "active packages").
    queryset = Package.objects.filter(is_active=True)
    # Any logged-in staff member (Admin or Support Agent) may view packages.
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        # Short serializer for the list, full one (with terms and add-ons) for a single package.
        if self.action == "retrieve":
            return PackageDetailSerializer
        return PackageSerializer