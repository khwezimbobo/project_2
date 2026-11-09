from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView

# Khwezi's reports service calculates every dashboard number with ORM aggregates (ISP-26).
# Reusing it means the dashboard and /api/reports/expiring/ always agree.
from reports.services import get_dashboard_data


class DashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Staff dashboard at /dashboard/ (BRD FR-13, Django MTV).

    Access (BRD section 12: "Admin (session)"):
      - not logged in        -> redirected to /accounts/login/
      - logged in, not Admin -> 403 Forbidden
      - Admin                -> the dashboard

    "Admin" uses the same rule as the API: role "admin" or superuser (user.can_view_all).
    """

    template_name = "dashboard/index.html"

    def test_func(self):
        # Only Admins may see the dashboard. Logged-in non-Admins get 403.
        return self.request.user.can_view_all

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Adds: active_count, monthly_revenue, pending_alerts,
        # expiring_subscriptions (each with .days_left) and expiry_window_days.
        context.update(get_dashboard_data())
        return context