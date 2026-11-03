"""
Management command: create_groups

   Creates the two staff roles from the BRD (section 7) with their permissions:
     - Admin:         full access to all our apps and to user accounts
     - Support Agent: create and view customers and subscriptions, view the
                      catalogue, view and acknowledge alerts - but no deletes

   Run with:
       docker compose exec django python manage.py create_groups

   Safe to run more than once - it resets each group to exactly these permissions.
"""

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction

   # Our Django apps (the "app_label" part of each permission).
OUR_APPS = ["customers", "packages", "subscriptions", "alerts", "reports"]

   # Django auto-creates view_/add_/change_/delete_ permissions for every model.
   # Support Agents get no delete permissions (BRD section 7: "no delete").
SUPPORT_AGENT_PERMISSIONS = [
    "view_customer", "add_customer", "change_customer",
    "view_package", "view_contractterm", "view_addon",
    "view_subscription", "add_subscription",
    "view_subscriptionauditlog",
    "view_renewalalert", "change_renewalalert",  # change = acknowledge an alert
]


class Command(BaseCommand):
    help = "Create the Admin and Support Agent groups with their permissions."

    @transaction.atomic  # All or nothing.
    def handle(self, *args, **options):
        # Admin: every permission in our apps, plus managing users and groups ("auth").
        admin_group, _ = Group.objects.get_or_create(name="Admin")
        admin_perms = Permission.objects.filter(content_type__app_label__in=OUR_APPS + ["auth"])
        admin_group.permissions.set(admin_perms)  # set() replaces, so re-running stays in sync.

        # Support Agent: only the permissions listed above.
        agent_group, _ = Group.objects.get_or_create(name="Support Agent")
        agent_perms = Permission.objects.filter(
            content_type__app_label__in=OUR_APPS,
            codename__in=SUPPORT_AGENT_PERMISSIONS,
        )
        agent_group.permissions.set(agent_perms)

        self.stdout.write(self.style.SUCCESS(
            f"Admin group: {admin_perms.count()} permissions. "
            f"Support Agent group: {agent_perms.count()} permissions."
        ))