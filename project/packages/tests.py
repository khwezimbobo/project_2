from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Package


class PackageApiTests(APITestCase):
    """Tests for the read-only packages API (GET /api/packages/)."""

    def setUp(self):
        # Load the real BRD catalogue, then hide one package to test the active filter.
        call_command("seed_data", stdout=StringIO())
        Package.objects.create(name="Old Package", monthly_rate=Decimal("199.00"),
                               speed_mbps=5, is_active=False)
        self.user = User.objects.create_user(username="agent", password="pass12345")
        self.client.force_authenticate(user=self.user)

    def test_list_shows_only_active_packages(self):
        response = self.client.get("/api/packages/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [p["name"] for p in response.data]
        self.assertEqual(len(names), 4)               # the 4 BRD packages
        self.assertNotIn("Old Package", names)        # inactive one is hidden

    def test_detail_includes_contract_terms_and_add_ons(self):
        package = Package.objects.get(name="Home Standard")
        response = self.client.get(f"/api/packages/{package.package_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["monthly_rate"], "699.00")
        self.assertEqual(len(response.data["contract_terms"]), 3)
        self.assertEqual(len(response.data["add_ons"]), 3)

    def test_writes_are_not_allowed(self):
        response = self.client.post("/api/packages/", {"name": "Hack"})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_login_required(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/packages/")
        # 403 with session auth today; becomes 401 once JWT is added (FR-16).
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])