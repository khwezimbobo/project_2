import logging

from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)

AGENT_GROUP = "Support Agent"

def is_admin(user):
    """True for Admins and superusers, via the one shared rule on User."""
    return bool(user.is_authenticated and user.can_view_all)


def is_agent(user):
    """True for Support Agents: role "agent" OR membership of the Support Agent group.

    Checking the role as well as the group means an agent is never locked out
    just because the group sync has not run yet.
    """
    return (
        getattr(user, "role", "") == "agent"
        or user.groups.filter(name=AGENT_GROUP).exists()
    )


def is_agent_or_admin(user):
    """Active, logged-in Admins and Support Agents only."""
    return bool(
        user and user.is_authenticated and user.is_active
        and (is_admin(user) or is_agent(user))
    )

def owner_id(obj, agent_field="assigned_agent"):
    """
    Return the id of the agent who owns obj, following the ORM path.

    "assigned_agent"           -> customer.assigned_agent_id
    "customer__assigned_agent" -> subscription.customer.assigned_agent_id
    Reading the *_id column avoids loading the agent row for the check.
    """
    parts = agent_field.split("__")
    parts[-1] += "_id"
    value = obj
    for part in parts:
        value = getattr(value, part)
    return value

def owns(user, obj, agent_field="assigned_agent"):
    """Admins reach every record; agents only the ones assigned to them."""
    if is_admin(user):
        return True
    return owner_id(obj, agent_field) == user.pk

class IsAdminOrSupportAgent(BasePermission):
    """Admins and Support Agents may use the API; agents cannot delete."""

    def has_permission(self, request, view):
        if not is_agent_or_admin(request.user):
            return False
        # Agents cannot delete: DELETE is refused with 403 for them.
        if request.method == "DELETE" and not is_admin(request.user):
            return False
        return True

    def has_object_permission(self, request, view, obj):
        agent_field = getattr(view, "agent_field", "assigned_agent")
        allowed = owns(request.user, obj, agent_field)
        if not allowed:
            # Audit trail of agents reaching for another agent's record.
            logger.warning(
                "User id %s was blocked from %s %s.",
                request.user.pk, type(obj).__name__, obj.pk,
            )
        return allowed