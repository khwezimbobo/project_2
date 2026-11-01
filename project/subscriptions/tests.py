"""
Unit tests for the pricing and contract-date logic in subscriptions/services.py.
(BRD NFR: Testability).

Run with:
    docker compose exec django python manage.py test subscriptions --settings=project.settings.test
"""

from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

# Import the constants and functions being tested.
# Using the constants (e.g. LOYALTY) instead of retyping ("Loyalty", 0.15)
# means the tests stay correct if a name or rate is ever changed in services.py.
from subscriptions.services import (
    INSTALLATION_FEE, LOYALTY, MULTI_ADD_ON, NEW_CUSTOMER, NO_DISCOUNT,
    best_discount, calculate_contract_dates, calculate_pricing,
)

# Short alias so money values are easy to read: D("699.00") instead of Decimal("699.00").
# Values are written as strings so Decimal stores them exactly (no float rounding).
D = Decimal


# =============================================================================
# Discount selection
# =============================================================================

class BestDiscountTests(SimpleTestCase):
    """Only the highest eligible discount applies - no stacking (BRD 8.1)."""

    def test_loyalty_beats_everything(self):
        # Customer qualifies for ALL three discounts.
        # Loyalty (15%) is the highest, so it must be the only one applied.
        self.assertEqual(best_discount(is_new_customer=True, is_loyal_customer=True, add_on_count=3), LOYALTY)

    def test_new_customer_beats_multi_add_on(self):
        # Qualifies for New Customer (10%) and Multi Add-On (5%), but not Loyalty.
        # New Customer is higher, so it wins.
        self.assertEqual(best_discount(is_new_customer=True, is_loyal_customer=False, add_on_count=2), NEW_CUSTOMER)

    def test_multi_add_on_needs_two_add_ons(self):
        # Boundary test: Multi Add-On needs 2 or more add-ons (team decision D1).
        # Exactly 2 add-ons -> qualifies.
        self.assertEqual(best_discount(False, False, 2), MULTI_ADD_ON)
        # Only 1 add-on and no other discount -> no discount at all.
        self.assertEqual(best_discount(False, False, 1), NO_DISCOUNT)


# =============================================================================
# Pricing formula (BRD 8.1)
#   BaseAmount = Rate x Multiplier
#   Subtotal   = BaseAmount + AddOnTotal
#   Monthly    = Subtotal - Discount
#   FirstMonth = Monthly + R500 installation fee
# =============================================================================

class CalculatePricingTests(SimpleTestCase):

    def test_worked_example_from_erd(self):
        # The worked example documented in docs/erd.md, checked field by field.
        # New customer, Home Standard (R699), 12-Month (x1.00),
        # Static IP (R100) + Router Rental (R150).
        p = calculate_pricing(D("699.00"), D("1.00"), [D("100.00"), D("150.00")], NEW_CUSTOMER)
        self.assertEqual(p.base_amount, D("699.00"))         # 699 x 1.00
        self.assertEqual(p.add_on_total, D("250.00"))        # 100 + 150
        self.assertEqual(p.subtotal, D("949.00"))            # 699 + 250
        self.assertEqual(p.discount_name, "New Customer")    # Name saved on the subscription
        self.assertEqual(p.discount_amount, D("94.90"))      # 10% of 949
        self.assertEqual(p.monthly_total, D("854.10"))       # 949 - 94.90
        self.assertEqual(p.first_month_total, D("1354.10"))  # 854.10 + 500

    def test_month_to_month_multiplier_and_no_add_ons(self):
        # Checks the Month-to-Month multiplier (x1.15) and the "nothing extra" case:
        # Home Premium (R999), no add-ons, no discount.
        # 999 x 1.15 = 1148.85, no add-ons, no discount.
        p = calculate_pricing(D("999.00"), D("1.15"), [], NO_DISCOUNT)
        self.assertEqual(p.base_amount, D("1148.85"))
        self.assertEqual(p.add_on_total, D("0.00"))          # Empty add-on list totals 0, not an error
        self.assertEqual(p.discount_amount, D("0.00"))       # No discount -> R0.00
        self.assertEqual(p.monthly_total, D("1148.85"))      # Subtotal unchanged
        self.assertEqual(p.first_month_total, D("1648.85"))  # 1148.85 + 500

    def test_24_month_loyalty_rounds_to_cents(self):
        # Checks rounding: the discount works out to half a cent and must round UP.
        # Home Basic (R399), 24-Month (x0.90), LTE Failover SIM (R250), Loyalty (15%).
        # 399 x 0.90 = 359.10; + LTE 250 = 609.10; 15% = 91.365 -> 91.37.
        p = calculate_pricing(D("399.00"), D("0.90"), [D("250.00")], LOYALTY)
        self.assertEqual(p.subtotal, D("609.10"))
        self.assertEqual(p.discount_amount, D("91.37"))      # 91.365 rounded half-up to 2 decimals
        self.assertEqual(p.monthly_total, D("517.73"))       # 609.10 - 91.37
        self.assertEqual(p.installation_fee, INSTALLATION_FEE)  # Always R500


# =============================================================================
# Contract dates (BRD 8.2)
#   contract_start_date = installation_date
#   contract_end_date   = start + term duration (30 / 365 / 730 days)
# =============================================================================

class ContractDateTests(SimpleTestCase):

    def test_end_date_is_start_plus_duration(self):
        # Month-to-Month (30 days) installed on 1 Nov 2026.
        start, end = calculate_contract_dates(date(2026, 11, 1), 30)
        self.assertEqual(start, date(2026, 11, 1))   # Start = installation date
        self.assertEqual(end, date(2026, 12, 1))     # 1 Nov + 30 days = 1 Dec

    def test_24_month_contract(self):
        # 24-Month (730 days) installed on 1 Nov 2026.
        # The result is 31 Oct 2028, not 1 Nov, because 2028 is a leap year (366 days):
        # 730 days is one day short of two calendar years here.
        # "_" means we don't need the start date in this test.
        _, end = calculate_contract_dates(date(2026, 11, 1), 730)
        self.assertEqual(end, date(2028, 10, 31))