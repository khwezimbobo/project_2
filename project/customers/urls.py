# ======================================================================
# CUSTOMERS APP URLS
# Mounted by api/urls.py with: path("", include("customers.urls"))
# so the routes below end up at /api/customers/ (ISP-6).
# Login, token refresh and Swagger are mounted in api/urls.py, not here.
# ======================================================================

from django.urls import include, path
# SimpleRouter builds the same list and detail routes as DefaultRouter,
# but without the extra API root page.
from rest_framework.routers import SimpleRouter

from .views import CustomerViewSet

router = SimpleRouter()
# basename names the routes "customer-list" and "customer-detail".
router.register("customers", CustomerViewSet, basename="customer")

urlpatterns = [
    # No "api/" prefix: api/urls.py already provides it.
    path("", include(router.urls)),
]