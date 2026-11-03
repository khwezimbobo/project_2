from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Subscription
from .permissions import is_admin                               # Shared "is this user an Admin?" check (Admin group or superuser)
from .serializers import SubscriptionSerializer                 # Converts subscriptions to/from JSON and validates input


class SubscriptionViewSet(mixins.CreateModelMixin,              # Handles POST /api/subscriptions/ to create a new subscription.
                          mixins.ListModelMixin,                # Handles GET /api/subscriptions/ to list all subscriptions the user is allowed to see. 
                          mixins.RetrieveModelMixin,            # Handles GET /api/subscriptions/{id}/ to retrieve one subscription with its full pricing breakdown.
                          viewsets.GenericViewSet):             # A viewset is a collection of views that share the same URL prefix and permission classes. This one is for subscriptions, and it only allows creating, listing, and retrieving subscriptions.
                                                                # The base class: provides the shared machinery (get_queryset, get_object, serializer handling)
                                                                # but no actions of its own. The mixins above add exactly the actions we want,
                                                                # so update and delete are simply not available (they return 405 Method Not Allowed).
    
    """Subscriptions API.

    POST /api/subscriptions/       - create (pricing calculated server-side)
    GET  /api/subscriptions/       - list
    GET  /api/subscriptions/{id}/  - one subscription with its full pricing breakdown

    No PUT/PATCH/DELETE here: status changes get their own endpoint
    (PATCH /api/subscriptions/{id}/status/) in a later story.
    """

    # Every action uses this serializer: it validates the 5 input fields on create and returns the full pricing breakdown in every response. 
    serializer_class = SubscriptionSerializer

     # Only logged-in users can use this API. Anyone else gets 401/403 (FR-16).
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # select_related joins the one-to-one/foreign-key tables (customer, package, term, user) into the same SQL query; 
        # prefetch_related loads all the add-ons in one extra query.
        # Without these, Django would run a separate query for every row in the list (the "N+1" problem).
        queryset = (Subscription.objects
                    .select_related("customer", "package", "contract_term", "created_by")
                    .prefetch_related("subscription_add_ons__add_on"))
        
        # IDOR prevention at queryset level (BRD 15): agents only ever see
        # subscriptions for their own customers; admins see everything.
        user = self.request.user
        if is_admin(user):
            return queryset
        return queryset.filter(customer__agent=user)