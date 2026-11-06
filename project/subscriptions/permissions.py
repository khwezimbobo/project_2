from rest_framework.permissions import BasePermission


def is_admin(user):
    """True if the user is an Admin (BRD section 7).

    Uses Siseko's customers.User model: superusers and users with role "admin"
    (user.can_view_all). Kept in one place so every view checks roles the same way.
    """
    return bool(user and user.is_authenticated and user.can_view_all)


class IsAdminRole(BasePermission):
    """DRF permission: only Admins (role "admin" or superuser) may use the endpoint.

    Anyone else gets 403 Forbidden with the message below.
    """

    message = "Only Admins can do this."

    def has_permission(self, request, view):
        return is_admin(request.user)