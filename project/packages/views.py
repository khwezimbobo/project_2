from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Package
from .serializers import PackageDetailSerializer, PackageSerializer


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