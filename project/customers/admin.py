from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Customer, User
from .permissions import can_view_all, is_agent_or_admin, owns


# --------------------------------------------------
# USER ADMIN (adds the role field)
# --------------------------------------------------
@admin.register(User)
class UserAdmin(DjangoUserAdmin):

    # Show the role when editing or creating a user.
    fieldsets = DjangoUserAdmin.fieldsets + (("Role", {"fields": ("role",)}),)
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (("Role", {"fields": ("role",)}),)

    list_display = DjangoUserAdmin.list_display + ("role",)
    list_filter = DjangoUserAdmin.list_filter + ("role",)


# --------------------------------------------------
# CUSTOMER ADMIN
# --------------------------------------------------
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):

    # Columns displayed on the customer list page.
    list_display = (
        "first_name",
        "last_name",
        "email",
        "phone",
        "assigned_agent",
        "created_at",
        "updated_at",
    )

    # Filters available in Django Admin.
    list_filter = (
        "assigned_agent",
        "created_at",
        "updated_at",
    )

    # Search customers by name, email and phone.
    search_fields = (
        "first_name",
        "last_name",
        "email",
        "phone",
        "assigned_agent__username",
    )

    # Reduce extra database queries when displaying agents.
    list_select_related = ("assigned_agent",)

    # Timestamps cannot be manually edited.
    readonly_fields = ("created_at", "updated_at")

    # --------------------------------------------------
    # ROW-LEVEL SECURITY
    # --------------------------------------------------
    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        # Admins and superusers can see all customer records.
        if can_view_all(request.user):
            return queryset

        # Agents can only see their own customers.
        return queryset.filter(assigned_agent=request.user)

    def _can_access(self, request, obj):
        """Check whether the user can access this customer."""

        # Allow normal permission checks for new records and list pages.
        if obj is None:
            return True

        return owns(request.user, obj)

    # Prevent unauthorized viewing.
    def has_view_permission(self, request, obj=None):
        return (
            self._can_access(request, obj)
            and super().has_view_permission(request, obj)
        )

    # Prevent unauthorized editing.
    def has_change_permission(self, request, obj=None):
        return (
            self._can_access(request, obj)
            and super().has_change_permission(request, obj)
        )

    # Prevent unauthorized deletion.
    def has_delete_permission(self, request, obj=None):
        return (
            self._can_access(request, obj)
            and super().has_delete_permission(request, obj)
        )

    # --------------------------------------------------
    # ADD CUSTOMER PERMISSION
    # --------------------------------------------------
    def has_add_permission(self, request):
        return (
            is_agent_or_admin(request.user)
            and super().has_add_permission(request)
        )

    def has_module_permission(self, request):
        return (
            is_agent_or_admin(request.user)
            and super().has_module_permission(request)
        )

    # --------------------------------------------------
    # SAVE CUSTOMER
    # --------------------------------------------------
    def save_model(self, request, obj, form, change):

        # Automatically assign new customers to the logged-in agent.
        if not change and not can_view_all(request.user):
            obj.assigned_agent = request.user

        # Save the customer record.
        super().save_model(request, obj, form, change)

    # --------------------------------------------------
    # LIMIT THE AGENT DROPDOWN TO AGENTS AND ADMINS
    # --------------------------------------------------
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "assigned_agent":
            kwargs["queryset"] = User.objects.filter(
                role__in=[User.Role.AGENT, User.Role.ADMIN], is_active=True
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # --------------------------------------------------
    # READ-ONLY FIELDS
    # --------------------------------------------------
    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))

        # Agents cannot change the assigned agent.
        if not can_view_all(request.user):
            readonly.append("assigned_agent")

        return readonly

    # --------------------------------------------------
    # CUSTOMIZE ADMIN FOR AGENTS
    # --------------------------------------------------
    def get_list_display(self, request):
        if can_view_all(request.user):
            return self.list_display

        # Agents do not need to see the assigned-agent column.
        return tuple(
            column for column in self.list_display
            if column != "assigned_agent"
        )

    def get_list_filter(self, request):
        if can_view_all(request.user):
            return self.list_filter

        # Agents only see their own records, so this filter is unnecessary.
        return tuple(
            field for field in self.list_filter
            if field != "assigned_agent"
        )

    def get_search_fields(self, request):
        if can_view_all(request.user):
            return self.search_fields

        # Agents cannot search by other users' usernames.
        return tuple(
            field for field in self.search_fields
            if not field.startswith("assigned_agent__")
        )
