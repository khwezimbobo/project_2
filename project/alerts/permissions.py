from rest_framework.permissions import BasePermission

class IsAlertAgentOrAdmin(BasePermission):
    """Admins see every alert; an agent only alerts for their own customers' subscriptions."""
    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj.subscription.customer.agent_id == request.user.id