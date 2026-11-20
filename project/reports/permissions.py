# Copy to reports/permissions.py (new file)
from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Only Admins (role "admin" or superuser) may use the endpoint. Everyone else gets a 403.

    The staff flag does not matter here: the role decides, through User.can_view_all.
    """

    message = "Only Admins can do this."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.can_view_all)
