"""Tests for the password reset flow."""
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .helpers import PASSWORD, make_user

User = get_user_model()


class PasswordResetTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.agent = make_user("agent1", role="agent")
        cls.agent.email = "agent1@example.com"
        cls.agent.save()

    def test_reset_request_sends_an_email_to_a_known_address(self):
        response = self.client.post(reverse("password_reset"), {"email": "agent1@example.com"})
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/password-reset/", mail.outbox[0].body)

    def test_unknown_address_looks_the_same_but_sends_nothing(self):
        # Same redirect for unknown emails, so attackers cannot discover accounts.
        response = self.client.post(reverse("password_reset"), {"email": "nobody@example.com"})
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_valid_link_lets_the_user_set_a_new_password(self):
        uid = urlsafe_base64_encode(force_bytes(self.agent.pk))
        token = default_token_generator.make_token(self.agent)

        # Django swaps the token for a session value and redirects to the form.
        response = self.client.get(
            reverse("password_reset_confirm", args=[uid, token]), follow=True
        )
        form_url = response.redirect_chain[-1][0]

        new_password = "N3w-Secure-Pass-2026"
        response = self.client.post(
            form_url, {"new_password1": new_password, "new_password2": new_password}
        )
        self.assertRedirects(response, reverse("password_reset_complete"))

        self.agent.refresh_from_db()
        self.assertTrue(self.agent.check_password(new_password))
        self.assertFalse(self.agent.check_password(PASSWORD))

    def test_invalid_link_shows_the_not_valid_page(self):
        response = self.client.get(
            reverse("password_reset_confirm", args=["bad", "bad-token"]), follow=True
        )
        self.assertContains(response, "Link not valid")
