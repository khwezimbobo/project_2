from rest_framework.permissions import BasePermission


def is_admin(user):
    """True if the user is an Admin (BRD section 7): a superuser or in the "Admin" group.

    Kept in one place so every view checks roles the same way. If the team adds a
    shared helper (e.g. in api/permissions.py), switch to that one.
    """
    return user.is_superuser or user.groups.filter(name="Admin").exists()


class IsAdminGroup(BasePermission):
    """DRF permission: only Admins (Admin group or superuser) may use the endpoint.

    Anyone else gets 403 Forbidden with the message below.
    """

    message = "Only Admins can do this."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_admin(request.user))