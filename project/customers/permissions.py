# import logging

# from rest_framework.permissions import BasePermission

# from .models import Customer

# logger = logging.getLogger(__name__)

# # Group names. "Admin" matches the subscriptions app exactly.
# ADMIN_GROUP = "Admin"
# AGENT_GROUP = "Support Agent"


# # ==================================================
# # ROLE CHECKS
# # ==================================================

# def is_admin(user):
#     """True if the user is an Admin (BRD section 7): a superuser or in the "Admin" group.

#     Same rule as the subscriptions app, so every app treats roles alike.
#     """
#     return user.is_superuser or user.groups.filter(name=ADMIN_GROUP).exists()


# def is_agent(user):
#     """True if the user is in the "Support Agent" group."""
#     return user.groups.filter(name=AGENT_GROUP).exists()


# def is_agent_or_admin(user):
#     """Active, logged-in Admins and Support Agents only."""
#     return bool(
#         user
#         and user.is_authenticated
#         and user.is_active
#         and (is_admin(user) or is_agent(user))
#     )


# # ==================================================
# # CUSTOMER OWNERSHIP (IDOR prevention)
# # ==================================================

# def owns(user, customer):
#     """Admins reach every customer; agents only the ones assigned to them."""
#     if is_admin(user):
#         return True
#     # Compare ids so the agent row is not loaded just for this check.
#     return customer.assigned_agent_id == user.pk


# def customers_for(user):
#     """The one rule for "which customers may this user list?"."""
#     # select_related fetches the agent in the same query.
#     queryset = Customer.objects.select_related("assigned_agent")
#     if is_admin(user):
#         return queryset
#     return queryset.filter(assigned_agent=user)


# # ==================================================
# # API PERMISSION CLASS
# # ==================================================

# class IsAdminOrSupportAgent(BasePermission):
#     """Only Admins and Support Agents may use the customer API."""

#     def has_permission(self, request, view):
#         # Runs on every request; a user in neither group gets 403.
#         return is_agent_or_admin(request.user)

#     def has_object_permission(self, request, view, obj):
#         # Runs on single-record requests; False becomes 403.
#         allowed = owns(request.user, obj)
#         if not allowed:
#             logger.warning(
#                 "User id %s was blocked from customer %s owned by user id %s.",
#                 request.user.pk, obj.pk, obj.assigned_agent_id,
#             )
#         return allowed