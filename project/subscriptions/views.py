from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Subscription
from .permissions import IsAdminRole, is_admin
from .serializers import StatusUpdateSerializer, SubscriptionSerializer
from .services import change_status


class SubscriptionViewSet(mixins.CreateModelMixin,     # POST /api/subscriptions/
                          mixins.ListModelMixin,       # GET  /api/subscriptions/
                          mixins.RetrieveModelMixin,   # GET  /api/subscriptions/{id}/
                          viewsets.GenericViewSet):    # Base machinery; the mixins add the actions above
    """Subscriptions API.

    POST  /api/subscriptions/              - create (pricing calculated server-side)
    GET   /api/subscriptions/              - list
    GET   /api/subscriptions/{id}/         - one subscription with its full pricing breakdown
    PATCH /api/subscriptions/{id}/status/  - change status (Admin only), audit log written

    No PUT/PATCH/DELETE on the subscription itself: prices and dates never change after creation.
    """

    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]   # Must be logged in (FR-16)

    def get_queryset(self):
        # select/prefetch_related avoid one extra query per row (the "N+1" problem).
        queryset = (Subscription.objects
                    .select_related("customer", "package", "contract_term", "created_by")
                    .prefetch_related("subscription_add_ons__add_on"))
        # IDOR prevention at queryset level (BRD 15): agents only see their own customers'
        # subscriptions; admins see everything.
        user = self.request.user
        if is_admin(user):
            return queryset
        return queryset.filter(customer__assigned_agent=user)

    # @action adds an extra URL to the ViewSet: detail=True means it's for ONE subscription,
    # so the router creates /api/subscriptions/{id}/status/.
    @action(detail=True, methods=["patch"], url_path="status",
            permission_classes=[IsAuthenticated, IsAdminRole])   # Admin only (FR-08)
    def change_status(self, request, pk=None):
        """PATCH /api/subscriptions/{id}/status/  body: {"status": "Active", "notes": "..."}

        Admin only (FR-08). Invalid transitions return 400 (BRD 18).
        """
        subscription = self.get_object()   # 404 if it doesn't exist
        serializer = StatusUpdateSerializer(instance=subscription, data=request.data)
        serializer.is_valid(raise_exception=True)   # 400 with a clear message if not allowed

        # The service updates the status AND writes the audit log entry (FR-09).
        change_status(
            subscription,
            serializer.validated_data["status"],
            changed_by=request.user,
            notes=serializer.validated_data["notes"],
        )
        # Return the full, updated subscription.
        return Response(SubscriptionSerializer(subscription).data, status=status.HTTP_200_OK)