from django.contrib import admin

from .models import AddOn, ContractTerm, Package


# Register the catalogue models so Admins can view and edit them in Django Admin (FR-02).

@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ("name", "monthly_rate", "speed_mbps", "is_active")  # Columns in the list view
    list_filter = ("is_active",)                                        # Filter sidebar
    search_fields = ("name",)                                           # Search box


@admin.register(ContractTerm)
class ContractTermAdmin(admin.ModelAdmin):
    list_display = ("name", "multiplier", "duration_days")


@admin.register(AddOn)
class AddOnAdmin(admin.ModelAdmin):
    list_display = ("name", "monthly_rate", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)