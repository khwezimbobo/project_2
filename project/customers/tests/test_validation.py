"""Tests for the shared phone and email validation rules."""
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from customers.validation import validate_phone_number, validate_unique_email

from .helpers import make_customer, make_user


class PhoneValidationTests(SimpleTestCase):

    def test_plain_ten_digit_number_is_valid(self):
        self.assertEqual(validate_phone_number("0821234567"), "0821234567")

    def test_formatted_international_number_is_valid(self):
        validate_phone_number("+27 (82) 123-4567")

    def test_nine_digits_is_too_short(self):
        with self.assertRaises(ValidationError):
            validate_phone_number("082123456")

    def test_sixteen_digits_is_too_long(self):
        with self.assertRaises(ValidationError):
            validate_phone_number("1234567890123456")

    def test_letters_are_rejected(self):
        with self.assertRaises(ValidationError):
            validate_phone_number("call me 0821234567")


class EmailValidationTests(TestCase):

    def test_duplicate_email_is_rejected_ignoring_case(self):
        make_customer(make_user("agent1", role="agent"), email="alice@example.com")
        with self.assertRaises(ValidationError):
            validate_unique_email("ALICE@example.com")

    def test_editing_a_customer_may_keep_its_own_email(self):
        customer = make_customer(make_user("agent1", role="agent"), email="alice@example.com")
        validate_unique_email("alice@example.com", instance=customer)
