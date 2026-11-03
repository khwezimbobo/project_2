"""
Pricing and contract-date logic for subscriptions (BRD 8.1 and 8.2).

All business rules live here - views and serializers call these functions
and never calculate prices themselves (BRD NFR: Maintainability).

The pure functions (best_discount, calculate_pricing, calculate_contract_dates)
need no database, so they can be unit-tested quickly without Docker.
"""

from dataclasses import dataclass                    
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from .models import Subscription, SubscriptionAddOn, SubscriptionAuditLog

# --- Business rules (BRD 8.1) ------------------------------------------------
INSTALLATION_FEE = Decimal("500.00")

# Discounts: (name, rate). Only the single highest eligible discount applies.
LOYALTY = ("Loyalty", Decimal("0.15"))
NEW_CUSTOMER = ("New Customer", Decimal("0.10"))
MULTI_ADD_ON = ("Multi Add-On", Decimal("0.05"))
NO_DISCOUNT = ("", Decimal("0.00"))

# Eligibility (team decision D1 in docs/erd.md).
LOYALTY_MIN_DAYS = 365   # customer for 12+ months
MULTI_ADD_ON_MIN = 2     # 2 or more add-ons

CENTS = Decimal("0.01")


def money(value):
    """Round a Decimal to 2 decimal places, halves rounded up (R0.005 -> R0.01)."""
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class PricingBreakdown:
    """The full price breakdown stored on every subscription (FR-06)."""
    base_amount: Decimal
    add_on_total: Decimal
    subtotal: Decimal
    discount_name: str
    discount_amount: Decimal
    monthly_total: Decimal
    installation_fee: Decimal
    first_month_total: Decimal

    def as_dict(self):
        """Field names match the Subscription model, so this can go straight into create()."""
        return self.__dict__.copy()


def best_discount(is_new_customer, is_loyal_customer, add_on_count):
    """Return (name, rate) of the single highest discount the customer qualifies for.

    Discounts never stack (BRD 8.1). Checked from highest to lowest rate.
    """
    if is_loyal_customer:
        return LOYALTY
    if is_new_customer:
        return NEW_CUSTOMER
    if add_on_count >= MULTI_ADD_ON_MIN:
        return MULTI_ADD_ON
    return NO_DISCOUNT


def calculate_pricing(monthly_rate, multiplier, add_on_rates, discount):
    """Apply the BRD pricing formula and return a PricingBreakdown.

    BaseAmount = Rate x Multiplier
    Subtotal   = BaseAmount + AddOnTotal
    Monthly    = Subtotal - Discount
    FirstMonth = Monthly + R500 installation fee
    """
    discount_name, discount_rate = discount

    base_amount = money(Decimal(monthly_rate) * Decimal(multiplier))
    add_on_total = money(sum((Decimal(r) for r in add_on_rates), Decimal("0")))
    subtotal = base_amount + add_on_total
    discount_amount = money(subtotal * discount_rate)
    monthly_total = subtotal - discount_amount
    first_month_total = monthly_total + INSTALLATION_FEE            

    return PricingBreakdown(
        base_amount=base_amount,
        add_on_total=add_on_total,
        subtotal=subtotal,
        discount_name=discount_name,
        discount_amount=discount_amount,
        monthly_total=monthly_total,
        installation_fee=INSTALLATION_FEE,              # Always R500, never calculated from the package or add-ons.
        first_month_total=first_month_total,
    )


def calculate_contract_dates(installation_date, duration_days):
    """Return (contract_start_date, contract_end_date) - BRD 8.2.

    The contract starts on the installation date and ends duration_days later
    (Month-to-Month 30, 12-Month 365, 24-Month 730).
    """
    start = installation_date
    end = start + timedelta(days=duration_days)
    return start, end


def price_subscription(customer, package, contract_term, add_ons, today=None):
    """Work out the discount for a real customer and price the subscription.

    Reads the customer's history from the database, then hands the numbers
    to calculate_pricing().
    """
    today = today or date.today()

    is_new_customer = not customer.subscriptions.exists()
    is_loyal_customer = (today - customer.created_at.date()).days >= LOYALTY_MIN_DAYS
    add_ons = list(add_ons)

    discount = best_discount(is_new_customer, is_loyal_customer, len(add_ons))
    return calculate_pricing(
        monthly_rate=package.monthly_rate,
        multiplier=contract_term.multiplier,
        add_on_rates=[a.monthly_rate for a in add_ons],
        discount=discount,
    )


# --- Creating a subscription ---------------------------------------------------

@transaction.atomic        
def create_subscription(*, customer, package, contract_term, add_ons, installation_date, created_by):
    """Create a fully priced subscription with its add-ons and first audit log entry.

    Everything happens in one database transaction: if any step fails, nothing is saved.
    Called by SubscriptionSerializer.create() - the API never calculates prices itself.
    """
    add_ons = list(add_ons)

    # 1. Price it. Must run BEFORE saving, so the customer's own new subscription
    #    doesn't count against the "New Customer" discount check.
    pricing = price_subscription(customer, package, contract_term, add_ons)

    # 2. Contract dates (BRD 8.2) - never taken from the client.
    start, end = calculate_contract_dates(installation_date, contract_term.duration_days)

    # 3. Save the subscription with the full pricing breakdown (FR-06, FR-07).
    subscription = Subscription.objects.create(
        customer=customer,
        package=package,
        contract_term=contract_term,
        installation_date=installation_date,
        contract_start_date=start,
        contract_end_date=end,
        created_by=created_by,
        **pricing.as_dict(),
    )

    # 4. Save each add-on with a copy of its current price.
    SubscriptionAddOn.objects.bulk_create([
        SubscriptionAddOn(subscription=subscription, add_on=add_on, monthly_rate=add_on.monthly_rate)
        for add_on in add_ons
    ])

    # 5. First audit log entry: created as Pending (FR-09).
    SubscriptionAuditLog.objects.create(
        subscription=subscription,
        changed_by=created_by,
        old_status="",
        new_status=subscription.status,
        notes="Subscription created",
    )
    return subscription