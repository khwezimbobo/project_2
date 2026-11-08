from django.contrib import admin

from .models import Subscription, SubscriptionAddOn, SubscriptionAuditLog


class SubscriptionAddOnInline(admin.TabularInline):
    """Shows a subscription's add-ons as a table inside the subscription page."""
    model = SubscriptionAddOn
    # No blank add-on rows are shown by default; staff can still click
    # "Add another Subscription add on" to add one.
    extra = 0


@admin.register(Subscription)  # Makes subscriptions visible in Django Admin (FR-02).
class SubscriptionAdmin(admin.ModelAdmin):
    # Columns shown on the subscriptions list page.
    list_display = ("customer", "package", "contract_term", "status",
                    "monthly_total", "contract_end_date")
    # Filter sidebar on the right of the list page.
    list_filter = ("status", "package", "contract_term")
    # Search box: "__" follows the foreign key, so this searches the customer's name and email.
    search_fields = ("customer__first_name", "customer__last_name", "customer__email")
    # Show the subscription's add-ons inside its page.
    inlines = [SubscriptionAddOnInline]
    # Pricing is calculated by PricingService, so Admin can see it but not edit it.
    readonly_fields = ("base_amount", "add_on_total", "subtotal", "discount_name",
                       "discount_amount", "monthly_total", "installation_fee",
                       "first_month_total", "created_at", "updated_at")

    def has_add_permission(self, request):
        # Subscriptions must be created through the API (POST /api/subscriptions/),
        # where prices are calculated server-side. Creating one here would leave the
        # read-only pricing fields empty and fail. Existing ones can still be viewed.
        return False

    def has_change_permission(self, request, obj=None):
        # View-only: status changes must go through PATCH /api/subscriptions/{id}/status/,
        # which validates the transition and writes the audit log (FR-08, FR-09, BRD 18).
        return False


@admin.register(SubscriptionAuditLog)                 # Registers the SubscriptionAuditLog model with the Django Admin site, so staff can view the audit log of subscription status changes.
class SubscriptionAuditLogAdmin(admin.ModelAdmin):
    list_display = ("subscription", "old_status", "new_status", "changed_by", "timestamp")
    list_filter = ("new_status", "old_status")
    search_fields = ("subscription__customer__last_name",)

    # The audit log is a permanent history of status changes (FR-09):
    # Admin can view it, but nobody can add, edit or delete entries by hand.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False