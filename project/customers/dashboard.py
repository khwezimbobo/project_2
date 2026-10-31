"""
Staff dashboard (MTV pattern).

Model    -> Customer / User queries below
Template -> customers/index.html
View     -> the dashboard() function in this file
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from .exceptions import DashboardAccessDenied
from .permissions import can_view_all, customers_for, is_agent_or_admin

User = get_user_model()


# --------------------------------------------------
# STAFF DASHBOARD VIEW
# --------------------------------------------------

@login_required
def dashboard(request):
    """
    Display the staff dashboard.

    Access requirements:
    1. User must be logged in.
    2. User must have Django staff access.
    3. User must be an agent, admin or superuser.
    """

    # Retrieve the currently logged-in user.
    user = request.user

    # Check whether the user has Django staff access.
    if not user.is_staff:
        raise DashboardAccessDenied("Staff access is required to view this dashboard.")

    # Allow only agents, admins and superusers.
    if not is_agent_or_admin(user):
        raise DashboardAccessDenied()

    # Customers this user is allowed to see (agents: own, admins: all).
    visible_customers = customers_for(user)

    now = timezone.now()
    context = {
        # KPI cards.
        "total_customers": visible_customers.count(),
        "new_this_week": visible_customers.filter(
            created_at__gte=now - timedelta(days=7)
        ).count(),
        "new_today": visible_customers.filter(
            created_at__date=timezone.localdate()
        ).count(),

        # Agent count is only meaningful to admins and superusers.
        "active_agents": (
            User.objects.filter(role=User.Role.AGENT, is_active=True).count()
            if can_view_all(user)
            else None
        ),

        # Latest customers for the table under the cards.
        "recent_customers": visible_customers.order_by("-created_at")[:5],
    }

    # Render the dashboard template and pass the KPI data.
    return render(request, "customers/index.html", context)
