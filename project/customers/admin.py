# # Admin is added later.from django import forms
# from django.contrib import admin
# from django.contrib.admin import forms
# from .models import Customer, User

# from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
# # To avoid name clash with our User model, we import the base class as DjangoUserAdmin.



# # --------------------------------------------------
# # USER ADMIN
# # Roles come from Groups ("Admin", "Support Agent"), which the default
# # user screens already let you assign.
# # --------------------------------------------------
# @admin.register(User)
# class UserAdmin(DjangoUserAdmin):
#     list_display = DjangoUserAdmin.list_display + ("is_active",)


# # --------------------------------------------------
# # CUSTOMER FORM (same rules as the API)
# # --------------------------------------------------
# class CustomerAdminForm(forms.ModelForm):
    
#     class Meta:
#         model = Customer
#         fields = "__all__"

# # Add a custom validation method to ensure that the assigned agent is either an admin or the current user.
#     def clean_first_name(self):
#         pass
    
#     def clean_last_name(self):
#         pass

#     def clean_phone_number(self):
#         pass
        
#     def clean_email(self):
#         pass
# # --------------------------------------------------
# # CUSTOMER ADMIN
# # --------------------------------------------------
# @admin.register(Customer)
# class CustomerAdmin(admin.ModelAdmin):
#     form = CustomerAdminForm

#     list_display = ("last_name", "first_name", "email", "phone_number",
#                     "assigned_agent", "created_at", "updated_at")
#     list_filter = ("assigned_agent", "created_at")
#     search_fields = ("first_name", "last_name", "email", "phone_number",
#                      "assigned_agent__username")
#     list_select_related = ("assigned_agent",)
#     readonly_fields = ("created_at", "updated_at")
    
# # --------------------------------------------------
# # row-level security (IDOR prevention)
# # --------------------------------------------------

#     def get_queryset(self, request):
#         queryset = super().get_queryset(request)
#         if is_admin(request.user):
#             return queryset
#         return queryset.filter(assigned_agent=request.user)

#     def _owns(self, request, obj):
#         # List and add pages have no object yet.
#         return obj is None or owns(request.user, obj)

# # --------------------------------------------------
# # ROLE-BASED PERMISSIONS (GROUP BASED)
# # --------------------------------------------------

#     def has_module_permission(self, request):
#         return is_agent_or_admin(request.user)

# # --------------------------------------------------
# # FORM BEHAVIORS
# # --------------------------------------------------
