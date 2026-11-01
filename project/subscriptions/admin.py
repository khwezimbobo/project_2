from django.contrib import admin

from .models import Subscription, SubscriptionAddOn, SubscriptionAuditLog


class SubscriptionAddOnInline(admin.TabularInline):    
    """Shows a subscription's add-ons inside the subscription page."""
    model = SubscriptionAddOn           
    extra = 0                           # No empty rows for new add-ons, because add-ons are added via the "Add Add-On" button, not by typing in a blank row.


@admin.register(Subscription)           # Registers the Subscription model with the Django Admin site, so staff can view and edit subscriptions.
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("customer", "package", "contract_term", "status",
                    "monthly_total", "contract_end_date")
    list_filter = ("status", "package", "contract_term")
    search_fields = ("customer__name", "customer__email")
    inlines = [SubscriptionAddOnInline]
    # Pricing is calculated by the system, so Admin can see it but not edit it.
    readonly_fields = ("base_amount", "add_on_total", "subtotal", "discount_name",
                       "discount_amount", "monthly_total", "installation_fee",
                       "first_month_total", "created_at", "updated_at")


@admin.register(SubscriptionAuditLog)
class SubscriptionAuditLogAdmin(admin.ModelAdmin):
    list_display = ("subscription", "old_status", "new_status", "changed_by", "timestamp")
    list_filter = ("new_status",)