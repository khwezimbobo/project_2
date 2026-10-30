"""
Management command: seed_data

Loads the package catalogue from the BRD (section 8.1) into the database:
4 internet packages, 3 contract terms and 3 add-ons.

Run with:
    docker compose exec django python manage.py seed_data

Safe to run more than once - existing rows are updated, never duplicated.
"""

from decimal import Decimal  

from django.core.management.base import BaseCommand  
from django.db import transaction  

from packages.models import AddOn, ContractTerm, Package

# -----------------------------------------------------------------------------
# Catalogue data from the BRD (section 8.1).
# Kept at the top of the file so prices can be changed in one place.
# Money and multipliers are written as strings so Decimal stores them exactly.
# -----------------------------------------------------------------------------

PACKAGES = [
    # name, monthly_rate, speed_mbps (speeds are our choice - not in the BRD)
    ("Home Basic", "399.00", 10),
    ("Home Standard", "699.00", 25),
    ("Home Premium", "999.00", 50),
    ("Business Fibre", "1499.00", 100),
]

CONTRACT_TERMS = [
    # name, multiplier, duration_days
    # multiplier: BaseAmount = package rate x multiplier
    # duration_days: used to calculate contract_end_date (BRD 8.2)
    ("Month-to-Month", "1.15", 30),
    ("12-Month", "1.00", 365),
    ("24-Month", "0.90", 730),
]

ADD_ONS = [
    # name, monthly_rate
    ("Static IP", "100.00"),
    ("Router Rental", "150.00"),
    ("LTE Failover SIM", "250.00"),
]


class Command(BaseCommand):
    # ("Command") run when "python manage.py seed_data" is called.

    # Shown when running: python manage.py help seed_data
    help = "Load the package catalogue (packages, contract terms, add-ons) from the BRD."

    # atomic = all or nothing: if any row fails, every change in this run is
    # rolled back, so the database never ends up with half a catalogue.
    @transaction.atomic
    def handle(self, *args, **options):

        # update_or_create looks up a row by "name":
        #   - found     -> updates it with the values in "defaults"
        #   - not found -> creates it with the name + defaults
        # This makes the command idempotent: running it twice gives the same result
        # and creates no duplicates (relies on name being unique=True in the models).
        for name, rate, speed in PACKAGES:
            Package.objects.update_or_create(
                name=name,
                defaults={"monthly_rate": Decimal(rate), "speed_mbps": speed, "is_active": True},
            )

        for name, multiplier, days in CONTRACT_TERMS:
            ContractTerm.objects.update_or_create(
                name=name,
                defaults={"multiplier": Decimal(multiplier), "duration_days": days},
            )

        for name, rate in ADD_ONS:
            AddOn.objects.update_or_create(
                name=name,
                defaults={"monthly_rate": Decimal(rate), "is_active": True},
            )

        # Success message with the real counts from the database, so it is easy to confirm nothing was duplicated.
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {Package.objects.count()} packages, "
            f"{ContractTerm.objects.count()} contract terms, {AddOn.objects.count()} add-ons."
        ))