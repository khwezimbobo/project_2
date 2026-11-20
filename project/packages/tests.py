from decimal import Decimal
from io import StringIO     # for capturing management command output

from django.contrib.auth import get_user_model
from django.core.management import call_command     # for loading the BRD catalogue into the test database
from rest_framework import status                   # for HTTP status codes
from rest_framework.test import APITestCase         # for testing the API

from .models import Package

User = get_user_model()


class PackageApiTests(APITestCase):
    """Tests for the read-only packages API (GET /api/packages/)."""

    def setUp(self):
        # Load the real BRD catalogue (seed_data), then hide one package to test the active filter.
        call_command("seed_data", stdout=StringIO())
        # create an inactive package to test the active filter
        Package.objects.create(name="Old Package", monthly_rate=Decimal("199.00"),
                               speed_mbps=5, is_active=False)
        self.user = User.objects.create_user(username="agent", password="pass12345")
        self.client.force_authenticate(user=self.user)

    def test_list_shows_only_active_packages(self):
        # GET request to the packages API endpoint
        response = self.client.get("/api/packages/")
        # check that the response status code is 200 OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # list is paginated: packages are under "results"
        names = [p["name"] for p in response.data["results"]]
        self.assertEqual(len(names), 4)           # the 4 BRD packages
        self.assertNotIn("Old Package", names)    # inactive one is hidden

    def test_detail_includes_contract_terms_and_add_ons(self):
        # get the Home Standard package from the database
        package = Package.objects.get(name="Home Standard")
        # GET request to the package detail API endpoint for the Home Standard package
        response = self.client.get(f"/api/packages/{package.package_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["monthly_rate"], "699.00")
        self.assertEqual(len(response.data["contract_terms"]), 3)
        self.assertEqual(len(response.data["add_ons"]), 3)

    # test that POST requests are not allowed on the packages API endpoint
    def test_writes_are_not_allowed(self):
        # send a POST request to the packages API endpoint with a new package name
        response = self.client.post("/api/packages/", {"name": "Hack"})
        # 405 Method Not Allowed: the packages API is read-only
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # test that login is required to access the packages API endpoint
    def test_login_required(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/packages/")
        # 401 with JWT; 403 with session auth.
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
