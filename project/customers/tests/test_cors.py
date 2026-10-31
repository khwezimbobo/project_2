"""Tests that only the configured front-end origin may call the API from a browser."""
from django.test import TestCase
from django.urls import reverse


class CorsTests(TestCase):

    def test_allowed_origin_gets_cors_headers_on_api_routes(self):
        response = self.client.get(
            reverse("api_login"), headers={"Origin": "http://localhost:3000"}
        )
        self.assertEqual(
            response.headers.get("Access-Control-Allow-Origin"), "http://localhost:3000"
        )

    def test_unknown_origin_gets_no_cors_headers(self):
        response = self.client.get(
            reverse("api_login"), headers={"Origin": "https://evil.example.com"}
        )
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_html_pages_never_get_cors_headers(self):
        response = self.client.get(reverse("login"), headers={"Origin": "http://localhost:3000"})
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)
