"""Tests for the login lockout on both the web login and the API login."""
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from .helpers import PASSWORD, make_user


@override_settings(LOCKOUT_MAX_ATTEMPTS=3, LOCKOUT_SECONDS=900)
class ApiLockoutTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.agent = make_user("agent1", role="agent")

    def setUp(self):
        # Failure counters live in the cache; start every test from zero.
        cache.clear()

    def bad_login(self, username="agent1"):
        return self.client.post(
            reverse("api_login"), {"username": username, "password": "wrong-password"}
        )

    def test_correct_password_is_refused_after_too_many_failures(self):
        for _ in range(3):
            self.assertEqual(self.bad_login().status_code, 401)

        response = self.client.post(
            reverse("api_login"), {"username": "agent1", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["error"]["status_code"], 429)

    def test_fewer_failures_than_the_limit_do_not_lock(self):
        for _ in range(2):
            self.bad_login()

        response = self.client.post(
            reverse("api_login"), {"username": "agent1", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 200)

    def test_successful_login_resets_the_counter(self):
        for _ in range(2):
            self.bad_login()
        self.client.post(reverse("api_login"), {"username": "agent1", "password": PASSWORD})

        # Two more failures after the reset are still under the limit of three.
        for _ in range(2):
            self.assertEqual(self.bad_login().status_code, 401)

    def test_lockout_is_per_username(self):
        for _ in range(3):
            self.bad_login("agent1")

        make_user("agent2", role="agent")
        response = self.client.post(
            reverse("api_login"), {"username": "agent2", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 200)


@override_settings(LOCKOUT_MAX_ATTEMPTS=3, LOCKOUT_SECONDS=900)
class WebLockoutTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.agent = make_user("agent1", role="agent")

    def setUp(self):
        cache.clear()

    def test_web_login_is_locked_after_too_many_failures(self):
        for _ in range(3):
            self.client.post(reverse("login"), {"username": "agent1", "password": "nope"})

        # Even the right password is refused while locked.
        response = self.client.post(
            reverse("login"), {"username": "agent1", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "Too many failed login attempts", status_code=429)

    def test_web_login_works_below_the_limit(self):
        self.client.post(reverse("login"), {"username": "agent1", "password": "nope"})
        response = self.client.post(
            reverse("login"), {"username": "agent1", "password": PASSWORD}
        )
        self.assertRedirects(response, reverse("customer_list"))
