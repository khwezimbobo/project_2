# os reads SEED_PASSWORD from the environment; secrets makes a random one.
import os
import secrets

from django.core.management.base import BaseCommand

from customers.models import Customer, User

# (username, role) - saving with a role also adds the user to the right group.
SEED_USERS = [
    ("admin1", User.Role.ADMIN),
    ("agent1", User.Role.AGENT),
    ("agent2", User.Role.AGENT),
]

# (first_name, last_name, email, phone_number, address, agent username)
SEED_CUSTOMERS = [
    ("Arda", "Guler", "arda.guler@example.com", "0821234567", "1 Long St, Cape Town", "agent1"),
    ("Star", "Butterfly", "star.butterfly@example.com", "0827654321", "2 Short St, Durban", "agent1"),
    ("Finn", "Human", "finn.human@example.com", "+27 83 111 2222", "3 Main Rd, Pretoria", "agent1"),
    ("Nia", "Long", "nia.long@example.com", "0845551234", "4 Oak Ave, Johannesburg", "agent2"),
    ("Zoe", "Deutsch", "zoe.deutsch@example.com", "(011) 555-0199", "5 Park Lane, Soweto", "agent2"),
    ("Virgil", "van Dyk", "virgil.vandyk@example.com", "0791239876", "6 Vine St, Stellenbosch", "agent2"),
]


class Command(BaseCommand):
    """Usage: python manage.py seed_customers"""

    help = "Create demo staff users and customers (safe to run more than once)."

    def handle(self, *args, **options):
        # The password comes from the environment, or is generated and printed once.
        password = os.getenv("SEED_PASSWORD") or secrets.token_urlsafe(10)
        users = {}

        for username, role in SEED_USERS:
            # get_or_create: running the command again does not duplicate users.
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"role": role, "is_staff": True, "email": f"{username}@example.com"},
            )
            if created:
                user.set_password(password)   # hashes the password
                user.save()
                self.stdout.write(f"Created user {username} ({role})")
            users[username] = user

        for first, last, email, phone, address, agent in SEED_CUSTOMERS:
            # Keyed on the unique email.
            _, created = Customer.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first, "last_name": last,
                    "phone_number": phone, "address": address,
                    "assigned_agent": users[agent],
                },
            )
            if created:
                self.stdout.write(f"Created customer {first} {last}")

        self.stdout.write(self.style.SUCCESS(
            f"Seed complete. Staff password (new users only): {password}"
        ))