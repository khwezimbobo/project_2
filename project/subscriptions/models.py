import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

# Shared settings for every money field, stored as exact decimals.
MONEY = {"max_digits": 10, "decimal_places": 2}


class SubscriptionStatus(models.TextChoices):
    """The only allowed subscription statuses (BRD 8.1).
    Imported this everywhere instead of typing "Active" etc. by hand."""
    PENDING = "Pending", "Pending"
    ACTIVE = "Active", "Active"
    SUSPENDED = "Suspended", "Suspended"
    CANCELLED = "Cancelled", "Cancelled"


class Subscription(models.Model):
    """A customer's internet subscription, with the full pricing breakdown
    stored at the moment it was created (BRD 13)."""

    subscription_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)        # UUID so IDs can't be guessed by changing a number in the URL.

    # Links to other apps use "app.Model" strings to avoid circular imports.
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="subscriptions"                # PROTECT: a customer/package/term can't be deleted while a subscription uses it.
    )
    package = models.ForeignKey(
        "packages.Package", on_delete=models.PROTECT, related_name="subscriptions"
    )

    contract_term = models.ForeignKey(
        "packages.ContractTerm", on_delete=models.PROTECT, related_name="subscriptions"
    )

    # Many add-ons per subscription; the "through" table stores the price at sign-up.
    add_ons = models.ManyToManyField(
        "packages.AddOn", through="SubscriptionAddOn", related_name="subscriptions", blank=True
    )

    # Dates (BRD 8.2): the client only sends installation_date.
    # The service layer sets start = installation date and end = start + term duration.
    installation_date = models.DateField()
    contract_start_date = models.DateField()
    contract_end_date = models.DateField(db_index=True)  # Indexed for expiry queries.

    # Pricing breakdown: always calculated on the server, never accepted from the client.
    base_amount = models.DecimalField(**MONEY)                                  # package rate x term multiplier
    add_on_total = models.DecimalField(**MONEY, default=Decimal("0.00"))
    subtotal = models.DecimalField(**MONEY)                                     # base + add-ons
    discount_name = models.CharField(max_length=50, blank=True)
    discount_amount = models.DecimalField(**MONEY, default=Decimal("0.00"))
    monthly_total = models.DecimalField(**MONEY)                                # subtotal - discount
    installation_fee = models.DecimalField(**MONEY, default=Decimal("500.00"))
    first_month_total = models.DecimalField(**MONEY)                            # monthly + installation fee

    # Indexed because list filters and both Celery tasks search by status.
    status = models.CharField(
        max_length=10,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.PENDING,
        db_index=True,
    )

    # The staff user who created it.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="subscriptions_created"
    )

    created_at = models.DateTimeField(auto_now_add=True)        # Timestamp of creation, set once and never changed.
    updated_at = models.DateTimeField(auto_now=True)            # Timestamp of last update, set automatically whenever the row is saved.

    class Meta:
        db_table = "subscriptions"
        ordering = ["-created_at"]  # Newest first.
        indexes = [
            # Both Celery tasks filter on status AND contract_end_date together.
            models.Index(fields=["status", "contract_end_date"], name="idx_sub_status_end"),
        ]

    def __str__(self):  
        return f"{self.customer} - {self.package} ({self.status})"      


class SubscriptionAddOn(models.Model): 
    """Link table: which add-ons a subscription has, and what each cost at sign-up.""" 

    # CASCADE: deleting a subscription deletes its add-on rows too.
    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="subscription_add_ons"         # PROTECT: a subscription can't be deleted while an add-on row uses it.
    )

    add_on = models.ForeignKey("packages.AddOn", on_delete=models.PROTECT)                  # PROTECT: an add-on can't be deleted while a subscription uses it.

    # Copy of the rate at sign-up, so later price changes don't alter old subscriptions.
    monthly_rate = models.DecimalField(**MONEY)

    class Meta:
        db_table = "subscription_add_ons"
        constraints = [
            # The same add-on can't be added twice to one subscription.
            models.UniqueConstraint(fields=["subscription", "add_on"], name="uniq_sub_add_on"),
        ]

    def __str__(self):
        return f"{self.subscription_id} + {self.add_on}"


class SubscriptionAuditLog(models.Model):
    """One row for every status change (FR-09), e.g. Active -> Suspended."""

    log_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="audit_logs"
    )
    # Nullable: Celery auto-suspension runs with no logged-in user (null = "System").
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,    
        related_name="subscription_changes",
    )
    
    # Blank on the very first entry (creation -> Pending).
    old_status = models.CharField(max_length=10, choices=SubscriptionStatus.choices, blank=True)
    new_status = models.CharField(max_length=10, choices=SubscriptionStatus.choices)
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "subscription_audit_logs"
        ordering = ["-timestamp"]  # Most recent change first.

    def __str__(self):
        return f"{self.subscription_id}: {self.old_status or '-'} -> {self.new_status}"