from rest_framework.routers import DefaultRouter

from .views import SubscriptionViewSet

# Creates /subscriptions/ (list + create) and /subscriptions/<id>/ (retrieve).
router = DefaultRouter()
router.register("subscriptions", SubscriptionViewSet, basename="subscription")

urlpatterns = router.urls