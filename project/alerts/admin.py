from django.contrib import admin

from .models import RenewalAlert
# Register your models here.

@admin.register(RenewalAlert)
class RenewalAlertAdmin(admin.ModelAdmin):
    """Alerts are created by the Celery task and acknowledged through the API, so read-only here."""

    list_display = ("subscription", "days_until_expiry", "alert_date", "status", "acknowledged_by")
    list_filter = ("status",)
    readonly_fields = [f.name for f in RenewalAlert._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False