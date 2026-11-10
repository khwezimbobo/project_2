# forms gives ModelForm, used for the admin validation.
from django import forms
from django.contrib import admin
# Django's own user admin, which we extend with the role field.
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Customer, User
from .permissions import is_admin, is_agent_or_admin, owns
from .serializers import clean_name, clean_phone_number


# --------------------------------------------------
# USER ADMIN (adds the role field)
# --------------------------------------------------
@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    # Show the role on the edit and add screens.
    fieldsets = DjangoUserAdmin.fieldsets + (("Role", {"fields": ("role",)}),)
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (("Role", {"fields": ("role",)}),)
    list_display = DjangoUserAdmin.list_display + ("role",)
    list_filter = DjangoUserAdmin.list_filter + ("role",)

    def save_related(self, request, form, formsets, change):
        # The admin saves the "groups" field AFTER User.save(), which can
        # overwrite the synced group. Re-sync once everything is saved.
        super().save_related(request, form, formsets, change)
        form.instance.sync_role_group()


# --------------------------------------------------
# CUSTOMER FORM (same rules as the API)
# --------------------------------------------------
class CustomerAdminForm(forms.ModelForm):
    class Meta:
        model = Customer     # build the form from the model
        fields = "__all__"   # every editable field

    # Django calls clean_<field>() while validating; the shared rules raise
    # Django's ValidationError, which the admin shows next to the field.
    def clean_first_name(self):
        return clean_name(self.cleaned_data["first_name"], "First name")

    def clean_last_name(self):
        return clean_name(self.cleaned_data["last_name"], "Last name")

    def clean_phone_number(self):
        return clean_phone_number(self.cleaned_data["phone_number"])

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        # Case-insensitive duplicate check (parameterised by the ORM).
        # exclude() lets an edited customer keep their own email.
        others = Customer.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if others.exists():
            raise forms.ValidationError("A customer with this email already exists.")
        return email

# ===  ISP-21 / ISP-24   ===
# --------------------------------------------------
# CUSTOMER ADMIN
# --------------------------------------------------
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    form = CustomerAdminForm   # use the validating form above

    list_display = ("last_name", "first_name", "email", "phone_number",
                    "assigned_agent", "created_at", "updated_at")
    list_filter = ("assigned_agent", "created_at")
    search_fields = ("first_name", "last_name", "email", "phone_number",
                     "assigned_agent__username")
    list_select_related = ("assigned_agent",)        # avoids one query per row
    readonly_fields = ("created_at", "updated_at")   # timestamps are automatic

    # ===  ISP-2 / ISP-91   ===
    # ===  ROW-LEVEL SECURITY (IDOR PREVENTION)  ===
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # Admins see everything; agents only their own customers.
        if is_admin(request.user):
            return queryset
        return queryset.filter(assigned_agent=request.user)

    def _owns(self, request, obj):
        # List and add pages have no object yet, so only records are checked.
        return obj is None or owns(request.user, obj)


# ===  ROLE-BASED PERMISSIONS   ===

    def has_module_permission(self, request):
        return is_agent_or_admin(request.user)

    def has_view_permission(self, request, obj=None):
        return is_agent_or_admin(request.user) and self._owns(request, obj)

    def has_add_permission(self, request):
        return is_agent_or_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_agent_or_admin(request.user) and self._owns(request, obj)

    def has_delete_permission(self, request, obj=None):
        # Only Admins may delete customers.
        return is_agent_or_admin(request.user) and is_admin(request.user)

# ===  FORM BEHAVIOUR   ===

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        # Agents cannot choose or change the owner.
        if not is_admin(request.user):
            readonly.append("assigned_agent")
        return readonly

    def save_model(self, request, obj, form, change):
        # A new customer made by an agent is assigned to that agent.
        if not change and not is_admin(request.user):
            obj.assigned_agent = request.user
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Only active Admins and Support Agents can own customers.
        # Filtered by role, which is always accurate (groups can lag behind).
        if db_field.name == "assigned_agent":
            kwargs["queryset"] = User.objects.filter(
                is_active=True,
                role__in=[User.Role.AGENT, User.Role.ADMIN],
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)