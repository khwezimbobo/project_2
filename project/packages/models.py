from django.db import models

# Package catalogue models (BRD section 13)
# These three tables hold the reference data used to price every subscription.
# They are filled by the seed_data management command, not by API users.
# =============================================================================


class Package(models.Model):
    """An internet package the ISP sells."""

    
    package_id = models.AutoField(primary_key=True)                                 # Primary key named to match the BRD data model.
    name = models.CharField(max_length=100, unique=True)                            # Unique so no two packages share a name; seed_data also uses it to find existing rows.
    monthly_rate = models.DecimalField(max_digits=10, decimal_places=2)             # Money is stored as an exact Decimal to avoid rounding errors in pricing.
    speed_mbps = models.PositiveIntegerField()                                      # Line speed in Mbps.
    description = models.TextField(blank=True)                                      # Added marketing text; blank=True allows it to be left empty.
    is_active = models.BooleanField(default=True)                                   # Soft on/off switch: inactive packages are hidden from the API but kept so existing subscriptions that use them are not broken.

    class Meta:
        db_table = "packages"               # Table name matches the BRD.
        ordering = ["monthly_rate"]         # Lists return cheapest package first.

    def __str__(self):
        return self.name


class ContractTerm(models.Model):
    """A contract length and its price multiplier."""

    contract_term_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50, unique=True)
    # Applied to the package rate: BaseAmount = monthly_rate x multiplier.
    # Month-to-Month 1.15, 12-Month 1.00, 24-Month 0.90 (BRD 8.1).
    multiplier = models.DecimalField(max_digits=4, decimal_places=2)
    # Used to calculate contract_end_date from the installation date
    # (30, 365 or 730 days - BRD 8.2).
    duration_days = models.PositiveIntegerField()
    description = models.TextField(blank=True)

    class Meta:
        db_table = "contract_terms"
        ordering = ["duration_days"]       #Shortest contract first.

    def __str__(self):
        return self.name


class AddOn(models.Model):
    """An optional monthly extra, e.g. Static IP at R100/month."""

    add_on_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    monthly_rate = models.DecimalField(max_digits=10, decimal_places=2)             # Added to the subtotal for each add-on the customer selects.
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "add_ons"
        ordering = ["name"]           # Alphabetical order.

    def __str__(self):
        return self.name