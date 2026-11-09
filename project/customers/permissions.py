import logging

from rest_framework.permissions import BasePermission

from .models import Customer

logger = logging.getLogger(__name__)

# Must match User.ROLE_GROUPS, the data migration and the subscriptions app.
AGENT_GROUP = "Support Agent"

# ===  ISP-1 / ISP-93 - ISP-95    ===
# ==================================================
# ROLE CHECKS
# ==================================================

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


# ==================================================
# OWNERSHIP (IDOR prevention)
# ==================================================

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


def customers_for(user):
    """Customers this user may list (used by admin.py)."""
    # select_related fetches the agent in the same query.
    queryset = Customer.objects.select_related("assigned_agent")
    if is_admin(user):
        return queryset
    return queryset.filter(assigned_agent=user)

# ===  ISP-1 / ISP-94    ===
# ==================================================
# SHARED MIXIN (Cassidy and Khwezi reuse this)
# ==================================================

class AgentScopedMixin:
    """
    Put this BEFORE the ViewSet class:  class X(AgentScopedMixin, ModelViewSet)

    Set agent_field on the ViewSet to the ORM path of the owning agent:
      customers      -> "assigned_agent"
      subscriptions  -> "customer__assigned_agent"

    LIST (no id in the URL): agents only receive their own records, and
    search, filters and pagination run on top, so they can never widen it.

    DETAIL (id in the URL): the queryset is NOT filtered. The record is
    fetched first (unknown id -> 404), then check_object_permissions calls
    has_object_permission, which refuses another agent's record with 403.
    A filtered queryset alone would give 404, but the BRD requires 403.
    """

    agent_field = "assigned_agent"

    def get_queryset(self):
        queryset = super().get_queryset()
        # Documentation tools inspect the view without a real user.
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        user = self.request.user
        # "detail" is set by the router: True for /<id>/ routes and actions.
        if getattr(self, "detail", False) or is_admin(user):
            return queryset
        return queryset.filter(**{self.agent_field: user})


# ==================================================
# API PERMISSION CLASSES
# ==================================================

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


class IsAdminOnly(BasePermission):
    """Admin-only actions, e.g. the subscription status PATCH."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_active and is_admin(request.user))