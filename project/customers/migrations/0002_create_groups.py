from django.db import migrations

# Must match User.ROLE_GROUPS in models.py and the subscriptions app.
GROUP_NAMES = ["Admin", "Support Agent"]


def create_groups(apps, schema_editor):
    # Data migrations must use the historical model, not a direct import.
    Group = apps.get_model("auth", "Group")
    for name in GROUP_NAMES:
        # get_or_create is safe to repeat, and safe if create_groups
        # or User.save() already made the group.
        Group.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    # customers.0001_initial already depends on auth, so Group exists.
    dependencies = [("customers", "0001_initial")]

    # The reverse is a no-op: never delete groups users may belong to.
    operations = [migrations.RunPython(create_groups, migrations.RunPython.noop)]