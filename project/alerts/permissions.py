# Copy to alerts/permissions.py
from rest_framework.permissions import BasePermission


class IsAlertAgentOrAdmin(BasePermission):
    """Admins see every alert; an agent only alerts for their own customers' subscriptions."""

    def has_object_permission(self, request, view, obj):
        customer = obj.subscription.customer
        return request.user.can_view_all or customer.assigned_agent_id == request.user.id