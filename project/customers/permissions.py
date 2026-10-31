import logging
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from .models import Customer

logger = logging.getLogger(__name__)


# ==================================================
# ROLE CHECKS
# ==================================================

def has_agent_role(user):
    """Check whether a user has the Agent role."""
    return getattr(user, "role", None) == "agent"


def has_admin_role(user):
    """Check whether a user has the Admin role."""
    return getattr(user, "role", None) == "admin"


def is_agent_or_admin(user):
    """
    Allow authenticated staff Agents, Admins and superusers.
    """

    return bool(
        user
        and user.is_authenticated
        and getattr(user, "is_agent_or_admin", False)
    )


def can_view_all(user):
    """Admins and superusers may see every customer."""
    return bool(user.is_superuser or has_admin_role(user))


# ==================================================
# CUSTOMER OWNERSHIP
# ==================================================

def owns(user, obj):
    """
    Determine whether a customer belongs to the current user.

    Admins and superusers can access all customers.
    Agents can access only their assigned customers.
    """

    if can_view_all(user):
        return True

    return obj.assigned_agent_id == user.id


def customers_for(user):
    """
    The one shared rule for "which customers may this user list?".

    Used by the API, the HTML pages, the dashboard and the admin so the
    rule lives in one place.
    """

    queryset = Customer.objects.select_related("assigned_agent")

    if can_view_all(user):
        return queryset

    return queryset.filter(assigned_agent=user)


# ==================================================
# VIEW DECORATOR FOR HTML PAGES
# ==================================================

def agent_or_admin_required(view):
    """Require a logged-in Agent/Admin/superuser; anyone else gets a 403 page."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not is_agent_or_admin(request.user):
            logger.warning(
                "Blocked %s (user id %s) from %s: not an agent or admin.",
                request.user, request.user.pk, request.path,
            )
            raise PermissionDenied("Only agents and admins can use this page.")
        return view(request, *args, **kwargs)

    # login_required redirects anonymous visitors before the role check runs.
    return login_required(wrapper)


# ==================================================
# API PERMISSION CLASS
# ==================================================

class IsAuthenticatedAndAgent(BasePermission):

    """
    Protect customer endpoints.

    Only authenticated Agents and Admins may access them.
    Object-level permissions enforce customer ownership.
    """

    def has_permission(self, request, view):

        return is_agent_or_admin(request.user)

    def has_object_permission(self, request, view, obj):

        allowed = owns(request.user, obj)

        # Keep an audit trail of agents trying to reach another agent's record.
        if not allowed:
            logger.warning(
                "Agent id %s was blocked from customer %s owned by agent id %s.",
                request.user.pk, obj.pk, obj.assigned_agent_id,
            )

        return allowed
