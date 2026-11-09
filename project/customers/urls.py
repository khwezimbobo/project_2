# ===  ISP-1 / ISP-53    ===
# ======================================================================
# CUSTOMERS APP URLS
# Included from the project urls.py with: path("", include("customers.urls"))
# ======================================================================

from django.urls import include, path
# DefaultRouter builds the list and detail routes from a ViewSet.
from rest_framework.routers import DefaultRouter
# simplejwt's ready-made views handle login and refresh.
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import CustomerViewSet

# ===  ISP-1 / ISP-56    ===
# One register() call creates every customer route.
router = DefaultRouter()
# basename names the routes "customer-list" and "customer-detail".
router.register("customers", CustomerViewSet, basename="customer")

urlpatterns = [
    # Public. POST {"username", "password"} -> {"access", "refresh"}.
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    # Public. POST {"refresh"} -> new {"access"}.
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # /api/customers/ and /api/customers/<uuid>/. JWT + Admin/Support Agent required.
    path("api/", include(router.urls)),
]