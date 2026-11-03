from rest_framework.permissions import BasePermission

class IsAdminGroup(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return u.is_superuser or u.groups.filter(name="Admin").exists() 