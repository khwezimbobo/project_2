# ======================================================================
# CUSTOMERS APP URLS
# Mounted by api/urls.py with: path("", include("customers.urls"))
# so the routes below end up at /api/customers/ (ISP-6).
# Login, token refresh and Swagger are mounted in api/urls.py, not here.
# ======================================================================

from django.urls import include, path
# DefaultRouter builds the list and detail routes from a ViewSet.
from rest_framework.routers import DefaultRouter

from .views import CustomerViewSet

router = DefaultRouter()
# basename names the routes "customer-list" and "customer-detail".
router.register("customers", CustomerViewSet, basename="customer")

urlpatterns = [
    # No "api/" prefix: api/urls.py already provides it.
    path("", include(router.urls)),
]