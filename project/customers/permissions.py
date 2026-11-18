# Role checks and IDOR prevention for the customers app.
# BRD s8.2 (role-based access), s15 (IDOR at queryset level), s18 (403 check).
import logging

from rest_framework.permissions import BasePermission

from .models import Customer

logger = logging.getLogger(__name__)

# Must match User.ROLE_GROUPS, migration 0002 and the other apps.
AGENT_GROUP = "Support Agent"


# ==================================================
# ROLE CHECKS (BRD s7: Admin and Support Agent)
# ==================================================
def is_admin(user):
    """True for Admins and superusers (one shared rule on User)."""
    return bool(user.is_authenticated and user.can_view_all)


def is_agent(user):
    """True for Support Agents: role "agent" OR in the Support Agent group.

    Checking the role as well as the group means an agent is not locked out
    if the group sync has not run yet.
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
# OWNERSHIP (BRD s15: IDOR prevention)
# ==================================================
def owner_id(obj, agent_field="assigned_agent"):
    """Return the id of the agent who owns obj, following the ORM path.

    "assigned_agent"           -> customer.assigned_agent_id
    "customer__assigned_agent" -> subscription.customer.assigned_agent_id
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
    queryset = Customer.objects.select_related("assigned_agent")
    if is_admin(user):
        return queryset
    return queryset.filter(assigned_agent=user)


# ==================================================
# SHARED MIXIN (BRD s15: filter in get_queryset(), reused by other apps)
# ==================================================
class AgentScopedMixin:
    """Limit what a Support Agent can see. Put it BEFORE the ViewSet class:

        class X(AgentScopedMixin, ModelViewSet)

    Set agent_field to the ORM path of the owning agent:
      customers      -> "assigned_agent"
      subscriptions  -> "customer__assigned_agent"

    LIST: agents only receive their own records. Search, filters and
    pagination run on top of that, so they cannot widen the result.

    DETAIL (id in the URL): the queryset is not filtered. An unknown id
    gives 404, and another agent's record gives 403 from
    has_object_permission. BRD s18 and test TC-04 require 403.
    """

    agent_field = "assigned_agent"

    def get_queryset(self):
        queryset = super().get_queryset()
        # Swagger builds the docs without a real user.
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        user = self.request.user
        # "detail" is True for /<id>/ routes and detail actions.
        if getattr(self, "detail", False) or is_admin(user):
            return queryset
        return queryset.filter(**{self.agent_field: user})


# ==================================================
# API PERMISSION CLASSES
# ==================================================
class IsAdminOrSupportAgent(BasePermission):
    """Admins and Support Agents may use the API. Agents cannot delete (BRD s7)."""

    def has_permission(self, request, view):
        if not is_agent_or_admin(request.user):
            return False
        if request.method == "DELETE" and not is_admin(request.user):
            return False
        return True

    def has_object_permission(self, request, view, obj):
        agent_field = getattr(view, "agent_field", "assigned_agent")
        allowed = owns(request.user, obj, agent_field)
        if not allowed:
            # Log agents reaching for another agent's record.
            logger.warning(
                "User id %s was blocked from %s %s.",
                request.user.pk, type(obj).__name__, obj.pk,
            )
        return allowed


class IsAdminOnly(BasePermission):
    """Admin-only actions, e.g. the subscription status PATCH (BRD s12)."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_active and is_admin(request.user))