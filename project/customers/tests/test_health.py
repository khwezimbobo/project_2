"""Tests for the public /health/ endpoint."""
from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse


class HealthCheckTests(TestCase):

    def test_health_is_public_and_reports_ok(self):
        # No login: Docker and monitoring tools call this anonymously.
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})

    def test_health_returns_503_when_the_database_is_down(self):
        # Replace the database connection with one that always fails.
        with patch("customers.health.connection") as fake_connection:
            fake_connection.cursor.side_effect = OperationalError("database is down")
            response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["database"], "down")
