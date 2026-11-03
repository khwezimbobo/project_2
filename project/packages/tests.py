from decimal import Decimal
from io import StringIO     # for capturing management command output

from django.contrib.auth.models import User         # for creating a test user
from django.core.management import call_command     # for loading the BRD catalogue into the test database
from rest_framework import status                   # for HTTP status codes
from rest_framework.test import APITestCase         # for testing the API

from .models import Package


class PackageApiTests(APITestCase):
    """Tests for the read-only packages API (GET /api/packages/)."""

    def setUp(self):
        # Load the real BRD catalogue, then hide one package to test the active filter.
        call_command("seed_data", stdout=StringIO())                                        # load the BRD catalogue (Seed_data file)
        Package.objects.create(name="Old Package", monthly_rate=Decimal("199.00"),          # create an inactive package to test the active filter
                               speed_mbps=5, is_active=False)
        self.user = User.objects.create_user(username="agent", password="pass12345")
        self.client.force_authenticate(user=self.user)

    def test_list_shows_only_active_packages(self):
        response = self.client.get("/api/packages/")                                        # GET request to the packages API endpoint
        self.assertEqual(response.status_code, status.HTTP_200_OK)                          # check that the response status code is 200 OK
        names = [p["name"] for p in response.data]                                          # extract the names of the packages from the response data
        self.assertEqual(len(names), 4)                                                     # the 4 BRD packages
        self.assertNotIn("Old Package", names)                                              # inactive one is hidden

    def test_detail_includes_contract_terms_and_add_ons(self):
        package = Package.objects.get(name="Home Standard")                                 # get the Home Standard package from the database
        response = self.client.get(f"/api/packages/{package.package_id}/")                  # GET request to the package detail API endpoint for the Home Standard package
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["monthly_rate"], "699.00")
        self.assertEqual(len(response.data["contract_terms"]), 3)
        self.assertEqual(len(response.data["add_ons"]), 3)

    def test_writes_are_not_allowed(self):                                                  # test that POST requests are not allowed on the packages API endpoint
        response = self.client.post("/api/packages/", {"name": "Hack"})                     # send a POST request to the packages API endpoint with a new package name
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)          # check that the response status code is 405 Method Not Allowed, indicating that writes are not allowed

    def test_login_required(self):                                                          # test that login is required to access the packages API endpoint
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/packages/")
        # 403 with session auth today; becomes 401 once JWT is added (FR-16).
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])