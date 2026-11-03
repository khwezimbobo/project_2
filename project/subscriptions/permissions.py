def is_admin(user):
    """True if the user is an Admin (BRD section 7): a superuser or in the "Admin" group.

    Kept in one place so every view checks roles the same way. If the team adds a
    shared helper (e.g. in api/permissions.py), switch to that one.
    """
    return user.is_superuser or user.groups.filter(name="Admin").exists()